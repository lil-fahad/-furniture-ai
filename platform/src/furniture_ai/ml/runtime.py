import gc
import hashlib
import sys

import cv2
import numpy as np
import torch
from PIL import Image
from torch.nn import functional as F

from furniture_ai.ml.common import image_b64, image_from_base64, layout_inputs, load_checkpoint
from furniture_ai.ml.networks import RANK_FEATURES, FloorplanNet, LayoutTransformer, PairwiseRanker


class ModelRuntime:
    """One request at a time per replica. Keep at most one model family resident."""

    def __init__(self, settings):
        self.settings = settings
        self.device = torch.device(settings.device)
        self.loaded_name, self.loaded = None, None

    def load(self, name, build):
        if self.loaded_name != name:
            self.loaded_name = None
            self.loaded = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.loaded = build()
            self.loaded_name = name
        return self.loaded

    def pretrained(self, alias, model_class, processor_class, *, dtype=None, **processor_options):
        path, revision = self.settings.model_path(alias)
        processor = processor_class.from_pretrained(
            path, local_files_only=True, trust_remote_code=False, **processor_options
        )
        model = (
            model_class.from_pretrained(
                path,
                local_files_only=True,
                use_safetensors=True,
                trust_remote_code=False,
                **({"torch_dtype": dtype} if dtype is not None else {}),
            )
            .eval()
            .to(self.device)
        )
        return model, processor, revision

    @torch.inference_mode()
    def chat(self, request):
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        from furniture_ai.ml.vlm_protocol import message_parts, structured_response

        messages, encoded_images = message_parts(request)
        images = [image_from_base64(value) for value in encoded_images]
        dtype = torch.float32
        if self.device.type == "cuda":
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        model, processor, _ = self.load(
            "evaluator",
            lambda: self.pretrained(
                "evaluator",
                Qwen2_5_VLForConditionalGeneration,
                AutoProcessor,
                dtype=dtype,
                max_pixels=768 * 28 * 28,
            ),
        )
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[prompt], images=images, return_tensors="pt").to(self.device)
        length = inputs.input_ids.shape[1]
        if length > 8192:
            raise ValueError("Vision prompt exceeds the local context limit")
        # Greedy output is reproducible and does not need platform-specific sampling kernels.
        output = model.generate(**inputs, max_new_tokens=request.max_tokens, do_sample=False)
        generated = output[0, length:]
        eos = model.generation_config.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        if len(generated) >= request.max_tokens and int(generated[-1]) not in eos:
            raise ValueError("Vision output reached the token limit; no partial analysis is accepted")
        text = processor.batch_decode([generated], skip_special_tokens=True)[0]
        return structured_response(text, request.structured_outputs.json_schema)

    @torch.inference_mode()
    def perceive(self, request):
        image = image_from_base64(request.image)
        if request.kind == "floor_plan":
            return self.floorplan(image)
        detections, dino_revision = self.detect(image)
        mask, overlay, objects, sam_revision = self.segment(image, detections)
        depth, depth_revision = self.depth(image)
        return {
            "objects": objects,
            "mask": image_b64(mask),
            "segmentation": image_b64(overlay),
            "depth": image_b64(depth),
            "depth_kind": "relative_inverse_depth_visualization",
            "metric_scale_known": False,
            "models": {
                "grounding_dino": dino_revision,
                "sam2": sam_revision,
                "depth_anything_v2_small": depth_revision,
            },
        }

    def detect(self, image):
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        model, processor, revision = self.load(
            "grounding_dino",
            lambda: self.pretrained("grounding_dino", AutoModelForZeroShotObjectDetection, AutoProcessor),
        )
        labels = "sofa. armchair. chair. bed. table. cabinet. lamp. floor. window. door."
        inputs = processor(images=image, text=labels, return_tensors="pt").to(self.device)
        output = model(**inputs)
        results = processor.post_process_grounded_object_detection(
            output, inputs.input_ids, threshold=0.3, text_threshold=0.25, target_sizes=[image.size[::-1]]
        )[0]
        detections = []
        labels = results.get("text_labels", results.get("labels", []))
        for coords, score, label in zip(results["boxes"], results["scores"], labels, strict=True):
            x1, y1, x2, y2 = coords.cpu().tolist()
            bbox = [
                max(0, min(image.width, x1)),
                max(0, min(image.height, y1)),
                max(0, min(image.width, x2)),
                max(0, min(image.height, y2)),
            ]
            if bbox[2] - bbox[0] >= 2 and bbox[3] - bbox[1] >= 2:
                detections.append({"box": bbox, "score": float(score), "label": str(label)})
        detections.sort(key=lambda d: -d["score"])
        from furniture_ai.ml.metrics import box_iou

        selected = []
        for detection in detections:
            if not any(
                detection["label"] == other["label"] and box_iou(detection["box"], other["box"]) > 0.6
                for other in selected
            ):
                selected.append(detection)
            if len(selected) == self.settings.max_detections:
                break
        return selected, revision

    def segment(self, image, detections):
        from transformers import Sam2Model, Sam2Processor

        model, processor, revision = self.load(
            "sam2", lambda: self.pretrained("sam2", Sam2Model, Sam2Processor)
        )
        union = np.zeros((image.height, image.width), dtype=np.uint8)
        protected = np.zeros_like(union)
        overlay = np.asarray(image).copy()
        objects = []
        if detections:
            inputs = processor(
                images=image, input_boxes=[[d["box"] for d in detections]], return_tensors="pt"
            ).to(self.device)
            output = model(**inputs, multimask_output=False)
            masks = processor.post_process_masks(output.pred_masks.cpu(), inputs["original_sizes"].cpu())[0]
            masks = masks[:, 0].numpy().astype(bool)
            for i, (detection, mask) in enumerate(zip(detections, masks, strict=True)):
                if "window" in detection["label"] or "door" in detection["label"]:
                    protected[mask] = 255
                else:
                    union[mask] = 255
                color = np.array([(53 + i * 67) % 255, (151 + i * 43) % 255, (170 + i * 31) % 255])
                overlay[mask] = (overlay[mask] * 0.5 + color * 0.5).astype("uint8")
                contours, _ = cv2.findContours(
                    mask.astype("uint8"), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                polygons = []
                for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
                    approx = cv2.approxPolyDP(contour, 0.01 * cv2.arcLength(contour, True), True)
                    if len(approx) >= 3:
                        polygons.append(approx[:, 0].tolist())
                objects.append({**detection, "polygons_px": polygons, "area_fraction": float(mask.mean())})
        union[protected > 0] = 0
        return Image.fromarray(union), Image.fromarray(overlay), objects, revision

    def depth(self, image):
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        model, processor, revision = self.load(
            "depth",
            lambda: self.pretrained("depth_anything", AutoModelForDepthEstimation, AutoImageProcessor),
        )
        inputs = processor(images=image, return_tensors="pt").to(self.device)
        output = model(**inputs).predicted_depth
        depth = (
            F.interpolate(
                output.unsqueeze(1), size=(image.height, image.width), mode="bicubic", align_corners=False
            )[0, 0]
            .cpu()
            .numpy()
        )
        lower, upper = np.quantile(depth, [0.02, 0.98])
        normalized = np.clip((depth - lower) / max(float(upper - lower), 1e-6), 0, 1)
        return Image.fromarray((normalized * 255).astype("uint8")), revision

    def floorplan(self, image):
        backend = self.settings.floorplan_backend
        if backend == "vlm":
            return {
                "floorplan_backend": "vision_language",
                "metric_scale_known": False,
                "models": {},
                "note": "VLM observations require a user-confirmed boundary. "
                "Configure a licensed floorplan checkpoint to add dense segmentation.",
            }
        if backend == "cubicasa_research":
            model, revision = self.load("cubicasa", self.load_cubicasa)
            classes_offset = 21
        else:
            if not self.settings.floorplan_checkpoint:
                raise ValueError("FLOORPLAN_CHECKPOINT is required")

            def build():
                model, meta = load_checkpoint(FloorplanNet(), self.settings.floorplan_checkpoint, "floorplan")
                if not meta.get("commercial_use") and not self.settings.research_only:
                    raise ValueError("Floorplan training rights do not permit commercial use")
                return model.eval().to(self.device), meta["sha256"]

            model, revision = self.load("floorplan", build)
            classes_offset = 0
        resized = image.resize((512, 512), Image.Resampling.BILINEAR)
        x = (
            torch.from_numpy(np.asarray(resized).copy()).permute(2, 0, 1).float()[None].to(self.device)
            / 127.5
            - 1
        )
        output = model(x)
        rooms = output[:, classes_offset : classes_offset + 12].argmax(1)[0].cpu().numpy().astype("uint8")
        icons = (
            output[:, classes_offset + 12 : classes_offset + 23].argmax(1)[0].cpu().numpy().astype("uint8")
        )
        palette = np.array(
            [
                [242, 238, 231],
                [214, 232, 223],
                [48, 61, 57],
                [207, 176, 141],
                [139, 177, 160],
                [146, 167, 184],
                [159, 190, 204],
                [202, 190, 168],
                [183, 161, 143],
                [189, 189, 165],
                [151, 151, 151],
                [220, 204, 187],
            ],
            dtype="uint8",
        )
        visualization = palette[rooms]
        visualization[icons == 1] = [78, 139, 179]
        visualization[icons == 2] = [204, 100, 86]
        visual = Image.fromarray(visualization).resize(image.size, Image.Resampling.NEAREST)
        regions = []
        for category in range(3, 12):
            count, labels, stats, _ = cv2.connectedComponentsWithStats((rooms == category).astype("uint8"))
            for i in range(1, count):
                if stats[i, cv2.CC_STAT_AREA] < 64:
                    continue
                contours, _ = cv2.findContours(
                    (labels == i).astype("uint8"), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                contour = max(contours, key=cv2.contourArea)
                poly = cv2.approxPolyDP(contour, 0.01 * cv2.arcLength(contour, True), True)[:, 0].astype(
                    float
                )
                poly[:, 0] *= image.width / 512
                poly[:, 1] *= image.height / 512
                regions.append({"room_class": category, "polygon_px": poly.tolist()})
        return {
            "floorplan": image_b64(visual),
            "regions": regions[:64],
            "floorplan_backend": backend,
            "metric_scale_known": False,
            "models": {backend: revision},
        }

    def load_cubicasa(self):
        s = self.settings
        if not s.research_only or not s.cubicasa_code_dir or not s.cubicasa_checkpoint:
            raise ValueError("CubiCasa5K is isolated to explicitly configured noncommercial research")
        with s.cubicasa_checkpoint.open("rb") as f:
            revision = hashlib.file_digest(f, "sha256").hexdigest()
        if len(s.cubicasa_sha256) != 64 or revision != s.cubicasa_sha256:
            raise ValueError("CubiCasa checkpoint SHA-256 mismatch")
        sys.path.insert(0, str(s.cubicasa_code_dir.resolve()))
        from floortrans.models import get_model

        model = get_model("hg_furukawa_original", 51)
        model.conv4_ = torch.nn.Conv2d(256, 44, kernel_size=1, bias=True)
        model.upsample = torch.nn.ConvTranspose2d(44, 44, kernel_size=4, stride=4)
        # Reject checkpoints requiring arbitrary pickle object deserialization.
        checkpoint = torch.load(s.cubicasa_checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(checkpoint["model_state"], strict=True)
        return model.eval().to(self.device), revision

    @torch.inference_mode()
    def similarity(self, request):
        from transformers import AutoModel, AutoProcessor

        model, processor, revision = self.load(
            "siglip", lambda: self.pretrained("siglip", AutoModel, AutoProcessor)
        )
        image = image_from_base64(request.image)
        inputs = processor(
            text=["This is a photo of " + request.text],
            images=image,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        outputs = model(**inputs)
        cosine = F.cosine_similarity(outputs.image_embeds.float(), outputs.text_embeds.float())[0].item()
        return {
            "score": (cosine + 1) / 2,
            "cosine": cosine,
            "revision": revision,
            "score_type": "rescaled_cosine_not_probability",
        }

    @torch.inference_mode()
    def layout(self, request):
        if not self.settings.layout_checkpoint:
            raise ValueError("Train and configure LAYOUT_CHECKPOINT before choosing transformer mode")

        def build():
            model, metadata = load_checkpoint(LayoutTransformer(), self.settings.layout_checkpoint, "layout")
            if not metadata.get("commercial_use") and not self.settings.research_only:
                raise ValueError("Checkpoint requires commercial training rights")
            return model.eval().to(self.device), metadata

        model, metadata = self.load("layout", build)
        pieces = [p.model_dump() for p in request.pieces]
        raster, categories, dims, bounds = layout_inputs(request.geometry.model_dump(), pieces)
        output = model(
            raster[None].to(self.device), categories[None].to(self.device), dims[None].to(self.device)
        )
        centers = output["centers"][0].cpu().tolist()
        rotations = output["rotation_logits"][0].argmax(-1).cpu().tolist()
        minx, miny, width, depth = bounds
        targets = []
        for p, center, rotate in zip(pieces, centers, rotations, strict=True):
            w, d = (p["depth_m"], p["width_m"]) if rotate else (p["width_m"], p["depth_m"])
            targets.append(
                {
                    "id": p["id"],
                    "x": minx + center[0] * width - w / 2,
                    "y": miny + center[1] * depth - d / 2,
                    "rotation": rotate * 90,
                }
            )
        return {"targets": targets, "revision": metadata["sha256"]}

    @torch.inference_mode()
    def rank(self, request):
        if not self.settings.rank_checkpoint:
            raise ValueError("Train and configure RANK_CHECKPOINT before choosing learned ranking")

        def build():
            model, metadata = load_checkpoint(PairwiseRanker(), self.settings.rank_checkpoint, "ranker")
            if not metadata.get("commercial_use") and not self.settings.research_only:
                raise ValueError("Checkpoint requires commercial training rights")
            if metadata.get("features") != RANK_FEATURES:
                raise ValueError("Ranking feature contract mismatch")
            return model.eval().to(self.device), metadata

        model, metadata = self.load("ranker", build)
        score = (
            model(torch.tensor([request.features], dtype=torch.float32, device=self.device)).sigmoid().item()
        )
        return {"score": score, "revision": metadata["sha256"], "score_type": "preference_not_probability"}

    def diffusion(self, photo):
        from diffusers import (
            AutoencoderKL,
            ControlNetModel,
            StableDiffusionXLControlNetInpaintPipeline,
            StableDiffusionXLControlNetPipeline,
        )

        dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        canny, _ = self.settings.model_path("controlnet_canny")
        depth, _ = self.settings.model_path("controlnet_depth")
        vae_path, _ = self.settings.model_path("vae")
        base, revision = self.settings.model_path("sdxl")
        controlnets = [
            ControlNetModel.from_pretrained(
                canny, torch_dtype=dtype, use_safetensors=True, local_files_only=True
            )
        ]
        if photo:
            controlnets.append(
                ControlNetModel.from_pretrained(
                    depth, torch_dtype=dtype, use_safetensors=True, local_files_only=True
                )
            )
        vae = AutoencoderKL.from_pretrained(
            vae_path, torch_dtype=dtype, use_safetensors=True, local_files_only=True
        )
        cls = StableDiffusionXLControlNetInpaintPipeline if photo else StableDiffusionXLControlNetPipeline
        pipe = cls.from_pretrained(
            base,
            controlnet=controlnets if photo else controlnets[0],
            vae=vae,
            torch_dtype=dtype,
            use_safetensors=True,
            local_files_only=True,
            add_watermarker=False,
        )
        if self.settings.sdxl_lora:
            lora_path, lora_revision = self.settings.model_path("sdxl_lora")
            pipe.load_lora_weights(lora_path, local_files_only=True, use_safetensors=True)
            revision += "+lora:" + lora_revision
        pipe.enable_vae_tiling()
        if self.settings.cpu_offload and self.device.type == "cuda":
            pipe.enable_model_cpu_offload(device=self.device)
        else:
            pipe.to(self.device)
        pipe.set_progress_bar_config(disable=True)
        return pipe, revision

    @torch.inference_mode()
    def generate(self, request):
        photo = request.kind == "photo"
        pipe, revision = self.load(
            "diffusion-photo" if photo else "diffusion-plan", lambda: self.diffusion(photo)
        )
        source = image_from_base64(request.image)
        original_size = source.size
        scale = 1024 / max(source.size)
        width, height = [max(256, round(v * scale / 64) * 64) for v in source.size]
        resized = source.resize((width, height), Image.Resampling.LANCZOS)
        edges = cv2.Canny(np.asarray(resized), 100, 200)
        generator = torch.Generator(device="cpu").manual_seed(request.seed)
        common = {
            "prompt": (
                "Interior design photography, "
                if photo
                else "Top-down orthographic interior rendering of a furnished room, preserve the exact room outline, "
            )
            + request.prompt,
            "negative_prompt": "text, watermark, distorted furniture, extra doors, impossible geometry, blurry",
            "width": width,
            "height": height,
            "num_inference_steps": request.steps,
            "guidance_scale": 6.0,
            "generator": generator,
        }
        if photo:
            if request.mask is None or request.depth is None:
                raise ValueError("Photo inpainting requires both an edit mask and relative depth")
            original_mask = image_from_base64(request.mask).convert("L")
            if original_mask.size != original_size:
                raise ValueError("Mask/image dimensions mismatch")
            original_mask = original_mask.point(lambda x: 255 if x >= 128 else 0)
            if not np.asarray(original_mask).any():
                raise ValueError("Edit mask is empty")
            mask = original_mask.resize((width, height), Image.Resampling.NEAREST)
            mask_array = np.asarray(mask)
            edges[mask_array > 0] = 0
            depth = (
                image_from_base64(request.depth)
                .convert("L")
                .resize((width, height), Image.Resampling.BILINEAR)
            )
            smooth_depth = cv2.inpaint(np.asarray(depth), mask_array, 5, cv2.INPAINT_TELEA)
            controls = [Image.fromarray(edges).convert("RGB"), Image.fromarray(smooth_depth).convert("RGB")]
            output = pipe(
                **common,
                image=resized,
                mask_image=mask,
                control_image=controls,
                controlnet_conditioning_scale=[0.65, 0.5],
                strength=0.92,
            ).images[0]
            # Exact unedited pixel preservation at the sanitized source resolution.
            output = Image.composite(
                output.resize(original_size, Image.Resampling.LANCZOS), source, original_mask
            )
        else:
            output = pipe(
                **common, image=Image.fromarray(edges).convert("RGB"), controlnet_conditioning_scale=0.85
            ).images[0]
        return {
            "image": image_b64(output),
            "metadata": {
                "model": "SDXL",
                "revision": revision,
                "seed": request.seed,
                "steps": request.steps,
                "mask_preservation": photo,
                "controls": ["canny", "relative_depth"] if photo else ["canny"],
                "view": "perspective_concept" if photo else "top_down_concept",
            },
        }
