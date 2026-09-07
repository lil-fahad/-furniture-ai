# Model selection and improvements

The following choices preserve the requested stack while making adaptations
measurable. They are deployment baselines, not an assertion that newer or larger
models are always inferior. Commit revisions, not moving Hub branches, are the
source of truth in `models.lock.json`.

| Component | Exact model ID / code | Weight status and terms |
|---|---|---|
| Detector | `IDEA-Research/grounding-dino-base` | Apache-2.0 model card; local safetensors |
| Segmenter | `facebook/sam2.1-hiera-small` | SAM 2.1 / Apache-2.0 |
| Depth | `depth-anything/Depth-Anything-V2-Small-hf` | Apache-2.0 Small variant; larger original variants have different restrictions |
| Floor-plan research | `CubiCasa/CubiCasa5k`, `hg_furukawa_original` | CC-BY-NC-4.0 research data/code/checkpoint path; never silently used commercially |
| Floor-plan production training | `FurnitureFloorplanNet` in `ml/networks.py` | Independent U-Net, 12 room + 11 icon classes; no pretrained custom weights supplied |
| Layout | `FurnitureLayoutTransformer` in `ml/networks.py` | Independent room/item transformer; no pretrained custom weights supplied |
| Generator | `stabilityai/stable-diffusion-xl-base-1.0` | OpenRAIL++; deployment must follow the model terms |
| Controls | `diffusers/controlnet-canny-sdxl-1.0`, `diffusers/controlnet-depth-sdxl-1.0` | SDXL-compatible pretrained ControlNets; model-card terms apply |
| VAE | `madebyollin/sdxl-vae-fp16-fix` | MIT model card; fp16-compatible VAE |
| Similarity | `google/siglip2-base-patch16-224` | Apache-2.0; replaces the older CLIP/SigLIP baseline |
| Visual evaluator | `Qwen/Qwen2.5-VL-7B-Instruct` | Apache-2.0; served privately with vLLM |
| Ranker | `FurniturePreferenceRanker` (`PairwiseRanker`) | Seven-input MLP trained from opt-in preference pairs |

## What changes in the models

Grounding DINO is fine-tunable against domain box/category annotations. Serving
clips boxes, limits detections, and suppresses duplicate same-label boxes at IoU
0.6. Tune detector thresholds using validation data; a fixed threshold is not a
universal confidence guarantee.

SAM 2.1 training freezes the image encoder and adapts trainable prompt/mask
components using binary cross entropy plus Dice. Evaluate thin legs, occlusion,
mirrors, dark upholstery and room openings separately. Automatic masks remain
editable by a user; a detector miss cannot be assumed safe.

Depth Anything training uses scale/shift-normalized inverse metric-depth targets
and masked gradients at three resolutions. This improves the objective's focus
on room boundaries without inventing metric scale from monocular inputs.

FurnitureFloorplanNet uses room/icon heads, cross entropy and class-balanced soft
Dice for sparse icons. It shares an annotation taxonomy with the research adapter,
not CubiCasa's copyrighted checkpoint implementation. Train it only on datasets
whose rights support the intended use. CubiCasa5K is a dataset, not itself the
name of a foundation model.

The layout network tokenizes a 3-channel 32×32 room/keepout/access raster and up to
16 furniture categories/dimensions. Position regression, orientation classification
and soft overlap/boundary penalties guide training. Inference always goes through
the independent geometric validator; gradients do not replace hard constraints.

SDXL receives domain LoRA adapters and separately fine-tuned ControlNets via the
vendored upstream training scripts. The implemented photo pipeline uses the base
4-channel UNet with ControlNet inpainting and exact final mask compositing.
It does not claim to load an incompatible 9-channel checkpoint as the same model.

SigLIP 2 uses identity-aware positives so two views of the same annotated concept
or item are not trained as negatives. Use distinct identities in each batch.
Cosine similarity rescaled to 0–1 is labelled as similarity, not calibrated probability.

Qwen LoRA trains only assistant answer tokens against reviewed schema-valid labels.
User/prompt/image tokens and padding are masked from the loss. Use independent
human evaluation to measure score agreement and unsupported dimension claims.
Do not train/evaluate solely on the same model's self-generated judgments.

The ranker minimizes `softplus(-(score(winner)-score(loser)))`. Its ordered features
are style alignment, visual quality, requirement match, structural consistency,
SigLIP similarity, clipped layout heuristic score, and access-check presence.
Retain position of displayed proposals in future feedback logging before learning
from implicit clicks; current explicit pairwise labels avoid claiming that a click
is a confirmed purchase preference.

## Official references

* [Grounding DINO model](https://huggingface.co/IDEA-Research/grounding-dino-base)
* [SAM 2 official repository](https://github.com/facebookresearch/sam2)
* [Depth Anything V2 Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf)
* [CubiCasa5K repository and license](https://github.com/CubiCasa/CubiCasa5k)
* [SigLIP 2 model](https://huggingface.co/google/siglip2-base-patch16-224)
* [Qwen2.5-VL model](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct)
* [SDXL model](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
* [SDXL ControlNet pipeline documentation](https://huggingface.co/docs/diffusers/api/pipelines/controlnet_sdxl)
* [vLLM structured outputs](https://docs.vllm.ai/en/stable/features/structured_outputs/)

Source/model license checks inform deployment configuration; they are not a legal
opinion about a particular dataset acquisition agreement or generated image.
