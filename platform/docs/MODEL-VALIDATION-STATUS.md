# Model validation status

This inventory separates executable integration evidence from domain training and quality evidence. It records the current nine-component stack, including tasks for which the uploaded COCO archive does not provide the required supervision.

| Component | Executed evidence | Domain data and remaining evaluation |
|---|---|---|
| Grounding DINO Base | Actual Transformers processor, COCO boxes, forward/backward and finite gradients using a small local architecture fixture; an actual downloaded COCO JPEG also traversed this path | Four COCO furniture classes selected. Image acquisition is incomplete; pretrained base fine-tuning and held-out AP are pending |
| SAM 2.1 Hiera Small | Actual Transformers model/processor, source polygon masks, decoder gradients and frozen encoder verified with a small local fixture; actual COCO image/mask path checked | 348 actual masks available in the partial download. Full-data pretrained adaptation and test-mask IoU are pending |
| Depth Anything V2 Small | Actual DepthAnything model with a small DINOv2 backbone, aligned synthetic metric-depth fixture, scale/shift loss and finite gradients | COCO does not contain metric-depth labels. Licensed aligned depth supervision and a depth quality benchmark are required |
| FurnitureFloorplanNet | Full custom network forward/backward at its training resolution; both room and icon heads receive gradients | Independent licensed room/icon labels are required. The CubiCasa adapter remains research-only |
| FurnitureLayoutTransformer | Five real CPU training epochs on 1,375 SpatialLM rooms; validation selects epoch 5; 314 separate test rooms evaluated before solver repair | Noncommercial research checkpoint only. Mean center error improves from 1.607m to 1.520m, while footprint IoU declines; quality is below production acceptance |
| SDXL + ControlNet + inpainting | Existing versioned model adapters, dataset exporter, training instructions and evaluation gates | No GPU diffusion training or image-quality benchmark executed in this environment. Aligned training images/conditions/edit masks and held-out human review are needed |
| SigLIP 2 Base Patch16-224 | Actual fixed-resolution SiglipModel forward/backward with positive product groups; gradients reach text and image encoders | 56,751 ABO images / 158,050 caption pairs prepared. Pretrained weight fine-tuning and product retrieval metrics are pending |
| Qwen2.5-VL-7B-Instruct | Existing private inference adapter, assistant-only LoRA training path and schema/error checks | Full 7B training/inference was not executed here; independently reviewed multimodal answers and evaluator agreement data are needed |
| FurniturePreferenceRanker | Actual optimization learns synthetic test preferences; safetensors save/load, held-out prediction and exact epoch-resume equivalence checked | Genuine human preference pairs are still needed; test fixtures are not preference-training evidence |

The chosen Google SigLIP 2 fixed-resolution checkpoint uses the `SiglipModel` architecture; the `Siglip2Model` name is used by the NaFlex family. Loading through `AutoModel` preserves the checkpoint's own architecture. See the [publisher's configuration change](https://huggingface.co/google/siglip2-base-patch16-224/commit/aa61322bc96d855648e670bccee1a4bd70e16079).

Native Windows checks install platform-specific hashed dependency locks, launch the `.cmd` entry point and exercise CPU model contracts. The CUDA doctor and preflight must pass on the actual NVIDIA device before a GPU job starts. Model revisions are immutable, partial datasets fail readiness checks, failed metrics prevent promotion, and the runtime returns explicit dependency errors when required models are absent.

Recorded local verification: **49 tests passed; two PostgreSQL tests require CI**. The separate CI workflow also runs PostgreSQL, browser and container gates. This document does not label a model as production-approved merely because its code executed.
