import hashlib
import io

import numpy as np
from PIL import Image

from furniture_ai.errors import DomainError
from furniture_ai.layout import pieces_for, plan_image, plan_layouts, plan_svg
from furniture_ai.providers import b64, decode_image
from furniture_ai.schemas import Geometry, Preferences


class Pipeline:
    def __init__(self, settings, storage, providers):
        self.settings, self.storage, self.providers = settings, storage, providers

    def run(self, job, save_stage):
        if job.input["vision_revision"] != self.settings.vision_revision:
            raise DomainError("MODEL_REVISION_CHANGED", "The evaluator revision changed. Submit a new job.")
        state = dict(job.checkpoint or {})
        prefix = f"tenants/{job.tenant_id}/projects/{job.project_id}/jobs/{job.id}/{job.lease_token}"

        def stage(name, operation):
            if name not in state:
                value = operation()
                save_stage(name, value)
                state[name] = value
            return state[name]

        def artifact(name, data, mime):
            key = prefix + "/" + name
            self.storage.put(key, data, mime)
            return {"key": key, "mime": mime, "sha256": hashlib.sha256(data).hexdigest()}

        source = self.storage.get(job.input["image_key"])
        prefs = Preferences.model_validate(job.input["preferences"])
        analysis = stage(
            "analysis", lambda: job.input.get("analysis") or self.providers.analyze(source, job.input["kind"])
        )

        def perceive():
            result = self.providers.model(
                "perception", "perceive", {"image": b64(source), "kind": job.input["kind"]}
            )
            blobs = {}
            for name in ["depth", "mask", "segmentation", "floorplan"]:
                if name in result:
                    raw = decode_image(result.pop(name))
                    blobs[name + ".png"] = artifact(name + ".png", raw, "image/png")
            result["artifacts"] = blobs
            return result

        perception = stage("perception", perceive)
        artifacts = dict(perception.get("artifacts", {}))
        base = {
            "analysis": analysis,
            "perception": {k: v for k, v in perception.items() if k != "artifacts"},
            "artifacts": artifacts,
            "supplier_status": "deferred",
            "vision_revision": job.input["vision_revision"],
        }
        if job.kind == "analyze":
            return base
        geometry = Geometry.model_validate(job.input["geometry"])

        def arrange():
            targets = None
            if job.input["layout_mode"] == "transformer":
                from dataclasses import asdict

                reply = self.providers.model(
                    "scoring",
                    "layout",
                    {
                        "geometry": geometry.model_dump(),
                        "pieces": [asdict(p) for p in pieces_for(prefs)],
                        "seed": prefs.seed,
                    },
                )
                targets = reply["targets"]
            return plan_layouts(geometry, prefs, targets)

        layouts = stage("layouts", arrange)
        mask_key = job.input.get("mask_key")
        if mask_key:
            mask = self.storage.get(mask_key)
        elif "mask.png" in artifacts:
            mask = self.storage.get(artifacts["mask.png"]["key"])
        else:
            mask = None
        if job.input["kind"] == "photo" and mask is None:
            raise DomainError("MASK_REQUIRED", "Upload a white-on-black edit mask for this photo.")
        if mask and not np.asarray(Image.open(io.BytesIO(mask)).convert("L")).any():
            raise DomainError(
                "EMPTY_MASK", "No editable furniture or floor region was found. Upload an edit mask."
            )
        variants = []
        for i, layout in enumerate(layouts):
            plan_name, png_name, render_name = f"plan-{i}.svg", f"plan-{i}.png", f"design-{i}.png"

            def generate(i=i, layout=layout, plan_name=plan_name, png_name=png_name, render_name=render_name):
                plan = plan_image(geometry, layout)
                local_artifacts = {
                    plan_name: artifact(plan_name, plan_svg(geometry, layout).encode(), "image/svg+xml"),
                    png_name: artifact(png_name, plan, "image/png"),
                }
                request = {
                    "image": b64(source if job.input["kind"] == "photo" else plan),
                    "kind": job.input["kind"],
                    "mask": b64(mask) if mask else None,
                    "depth": b64(self.storage.get(artifacts["depth.png"]["key"]))
                    if "depth.png" in artifacts
                    else None,
                    "prompt": f"{prefs.style} {prefs.room_type.replace('_', ' ')}. "
                    + ", ".join(f"{r.quantity} {r.category.replace('_', ' ')}" for r in prefs.requirements)
                    + ". "
                    + prefs.prompt,
                    "seed": prefs.seed + i,
                    "steps": 30,
                }
                response = self.providers.model("generation", "generate", request)
                generated = decode_image(response["image"])
                local_artifacts[render_name] = artifact(render_name, generated, "image/png")
                return {"artifacts": local_artifacts, "generation": response.get("metadata", {})}

            generation = stage(f"generation-{i}", generate)
            artifacts.update(generation["artifacts"])
            generated = self.storage.get(artifacts[render_name]["key"])
            evaluation = stage(
                f"evaluation-{i}",
                lambda generated=generated: self.providers.evaluate(source, generated, prefs.model_dump()),
            )
            similarity = stage(
                f"similarity-{i}",
                lambda generated=generated: self.providers.model(
                    "scoring",
                    "similarity",
                    {
                        "image": b64(generated),
                        "text": f"{prefs.style} {prefs.room_type.replace('_', ' ')}. {prefs.prompt}",
                    },
                ),
            )
            features = [
                evaluation[k]
                for k in ["style_alignment", "visual_quality", "requirement_match", "structural_consistency"]
            ] + [float(similarity["score"]), min(1, layout["layout_score"]), float(layout["access_checked"])]
            if not all(np.isfinite(x) for x in features):
                raise DomainError("INVALID_SCORE", "Evaluator returned non-finite scores.", 502)
            if job.input["ranking_mode"] == "learned":
                ranking = stage(
                    f"ranking-{i}",
                    lambda features=features: self.providers.model("scoring", "rank", {"features": features}),
                )
                score = float(ranking["score"])
            else:
                score = sum(
                    x * w for x, w in zip(features, [0.2, 0.15, 0.2, 0.2, 0.1, 0.1, 0.05], strict=True)
                )
                ranking = {"revision": "weighted-v1", "score": score}
            if not np.isfinite(score):
                raise DomainError("INVALID_SCORE", "Ranker returned a non-finite score.", 502)
            variants.append(
                {
                    "index": i,
                    "layout": layout,
                    "evaluation": evaluation,
                    "features": features,
                    "similarity": similarity,
                    "ranking": ranking,
                    "score": round(score, 5),
                    "render": render_name,
                    "plan": plan_name,
                    "generation": generation["generation"],
                }
            )
        variants.sort(key=lambda v: -v["score"])
        return {
            **base,
            "variants": variants,
            "artifacts": artifacts,
            "geometry": geometry.model_dump(),
            "layout_mode": job.input["layout_mode"],
            "ranking_mode": job.input["ranking_mode"],
            "notes": [
                "Furniture dimensions are concept assumptions unless entered by the user.",
                "Generated photos are visual interpretations; the measured plan is the geometry reference.",
                "No prices, supplier stock or purchasability claims are issued in this release.",
            ],
        }
