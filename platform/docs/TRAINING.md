# Data and training

## Dataset strategy

Acquire first-party consented room images, licensed interiors, measured furniture
dimensions, annotated floor plans and human design preferences. Record acquisition
source, permitted training use, commercial use, retention/deletion requirements,
and annotator agreement. A license string is provenance, not automatic permission.
Do not scrape supplier imagery and assume permission; suppliers are a later phase.

Keep original private data in an encrypted versioned dataset store. Manifests use
relative paths. Group all photos, plans, crops, renderings and preference pairs of
the same home/design into one `group_id`. Separate client, property, geography,
room type, style and capture conditions across held-out slices. Use independent
property groups for tests and preserve a final release test set from tuning.

`ml.data` validates provenance/consent and file bounds, verifies image SHA-256,
groups exact and conservative perceptual duplicates, and writes deterministic
70/15/15 group splits. It refuses fewer than three independent groups. Its dHash
check is a useful additional safeguard, not a substitute for explicit identity
grouping; semantically similar, mirrored and heavily cropped scenes need review.

Every manifest row includes:

```json
{"id":"scene-001-view-a","group_id":"property-001","source":"licensed-first-party",
 "license":"documented-contract-id","training_use":true,"commercial_use":true,
 "consent":true,"image_path":"images/room-001.jpg"}
```

The example values describe a schema; they are not supplied training data or
evidence of a real license. Task-specific fields:

| Task | Additional fields |
|---|---|
| DINO | `categories:["sofa","chair"]`; `boxes:[{"xywh":[x,y,width,height],"category_id":0}]` in source pixels |
| SAM 2 | `mask_path` to a matching binary PNG; one nonempty object per record |
| Depth | `depth_path` to a finite metric-depth `.npy`; zero means invalid; aligned with source image |
| FloorplanNet | `labels_path` to `.npz` containing `rooms` (0–11) and `icons` (0–10); 255 is ignored |
| Layout | `geometry`, `preferences`, `pieces`, `placements`; canonical piece IDs, metric positions, rotations 0 or 90 |
| SigLIP 2 | `caption`; stable `product_id` or concept identity for multiple positive views |
| Ranker | `winner`, `loser`: ordered arrays of seven finite features in [0,1]; an image is not required |
| SDXL LoRA | `image_path`, `caption`; reviewed target interiors |
| ControlNet | `image_path`, `conditioning_image_path`, `caption`; aligned reviewed target/control pairs |
| Qwen analysis | `task:"analysis"`, `image_path`, `prompt`, `answer` matching `RoomAnalysis` |
| Qwen evaluator | `task:"evaluation"`, `image_path`, `generated_image_path`, `prompt`, `answer` matching `VisualEvaluation` |

Store labels with clear ownership. Floorplan class definitions must stay consistent
between annotation, training and release; changing IDs requires a new model contract.
For ranking, export consented pairs with `furniture export-feedback --tenant-id ID
--output data/raw/preferences.jsonl`. Exported records contain numeric features,
not room photographs. Revoke/delete downstream training copies according to the
dataset deletion ledger; deleting a project cannot untrain an already released model.

## Install and prepare

Run from `platform/` in a Python 3.12 environment. GPU training uses the separately
pinned PyTorch/Transformers/Diffusers dependencies; vLLM is a separate container.

```bash
python -m pip install -r requirements-ml.lock
python -m furniture_ai.ml.install --group all --output data/models
python -m furniture_ai.ml.data data/raw/manifest.jsonl \
  --root data/raw --output data/splits --seed 42
```

Prepare a separate manifest/split directory for each task. Supply real paths to
your licensed data; this repository intentionally contains no fabricated corpus.

## Train perception, layout, similarity and ranking

The common trainer supports Accelerate/DDP, gradient accumulation, mixed precision,
clipping, AdamW, cosine scheduling, deterministic seeds, finite-loss checks, complete
epoch checkpoint state, and validation-based checkpoint selection. Metrics are
written to JSONL. Checkpoints use safetensors for inference. Resume state is a
trusted local training artifact; never load an arbitrary downloaded resume folder.

```bash
accelerate launch --num_processes 1 -m furniture_ai.ml.train \
  --task layout --train data/layout/train.jsonl --validation data/layout/validation.jsonl \
  --root data/raw --output checkpoints/layout --epochs 30 --batch-size 16 \
  --gradient-accumulation 2 --learning-rate 0.0001 --mixed-precision bf16

accelerate launch --num_processes 1 -m furniture_ai.ml.train \
  --task ranker --train data/ranker/train.jsonl --validation data/ranker/validation.jsonl \
  --root data/raw --output checkpoints/ranker --epochs 20 --batch-size 64 \
  --gradient-accumulation 1 --learning-rate 0.001

accelerate launch --num_processes 1 -m furniture_ai.ml.train \
  --task floorplan --train data/floorplan/train.jsonl --validation data/floorplan/validation.jsonl \
  --root data/raw --output checkpoints/floorplan --epochs 50 --batch-size 4 \
  --gradient-accumulation 4 --learning-rate 0.0001 --mixed-precision bf16
```

Foundation adaptations use the same command with these substitutions:

| `--task` | `--model-path` | Initial learning rate | Batch size |
|---|---|---|---|
| `dino` | `data/models/grounding_dino` | `0.00001` | 2 |
| `sam2` | `data/models/sam2` | `0.00001` | 2 |
| `depth` | `data/models/depth_anything` | `0.000005` | 2 |
| `siglip` | `data/models/siglip` | `0.000005` | 16 |

These are starting hyperparameters, not validated optima or guaranteed memory fits.
Use different group identities in each SigLIP batch. Increase effective batch size
via gradient accumulation; contrastive negatives still come from the microbatch.

```bash
accelerate launch --num_processes 1 -m furniture_ai.ml.train \
  --task siglip --model-path data/models/siglip \
  --train data/siglip/train.jsonl --validation data/siglip/validation.jsonl \
  --root data/raw --output checkpoints/siglip --epochs 10 --batch-size 16 \
  --gradient-accumulation 2 --learning-rate 0.000005 --mixed-precision bf16
```

Resume an interrupted run by repeating its original command with
`--resume checkpoints/siglip/epoch-0003`. Keep the dataset, total epochs, batch,
accumulation, learning rate, precision, seed and world size unchanged. Remove only
an incomplete next epoch directory after inspecting it; completed epoch directories
are immutable. `best.json` points to the selected inference folder. Validation
loss is a model-selection signal; the held-out task metrics determine release.

## SDXL LoRA and ControlNet

The unchanged upstream trainers are pinned in `third_party/diffusers/NOTICE.md`.
They execute real optimization and provide resume/checkpoint support. Commands
below keep uploads disabled and log to local TensorBoard.

```bash
python -m furniture_ai.ml.export_diffusion_data --manifest data/sdxl/train.jsonl \
  --root data/raw --output data/sdxl-imagefolder
accelerate launch --num_processes 1 third_party/diffusers/train_text_to_image_lora_sdxl.py \
  --pretrained_model_name_or_path data/models/sdxl \
  --pretrained_vae_model_name_or_path data/models/vae \
  --train_data_dir data/sdxl-imagefolder --image_column image --caption_column text \
  --resolution 1024 --center_crop --train_batch_size 1 --gradient_accumulation_steps 4 \
  --learning_rate 0.00001 --max_train_steps 4000 --checkpointing_steps 500 \
  --rank 16 --mixed_precision bf16 --gradient_checkpointing \
  --output_dir checkpoints/sdxl-lora --report_to tensorboard --seed 42

python -m furniture_ai.ml.export_diffusion_data --manifest data/controlnet/train.jsonl \
  --root data/raw --output data/controlnet-parquet --controlnet
accelerate launch --num_processes 1 third_party/diffusers/train_controlnet_sdxl.py \
  --pretrained_model_name_or_path data/models/sdxl \
  --pretrained_vae_model_name_or_path data/models/vae \
  --controlnet_model_name_or_path data/models/controlnet_canny \
  --train_data_dir data/controlnet-parquet --image_column image \
  --conditioning_image_column conditioning_image --caption_column text \
  --resolution 1024 --train_batch_size 1 --gradient_accumulation_steps 4 \
  --learning_rate 0.000005 --max_train_steps 5000 --checkpointing_steps 500 \
  --mixed_precision bf16 --gradient_checkpointing \
  --output_dir checkpoints/controlnet-canny --report_to tensorboard --seed 42
```

For depth ControlNet, use `data/models/controlnet_depth`, aligned normalized
inverse-depth control images and a distinct output/split directory. Controls must
correspond to the same crop/orientation as the target. Do not augment only one
image of a conditioning pair. Mask behavior is tested at inference, including
unchanged source pixels, since the LoRA trains the shared base SDXL UNet.

After training, record the data provenance beside inference weights:

```bash
python -m furniture_ai.ml.training_metadata --kind sdxl_lora \
  --train data/sdxl/train.jsonl --validation data/sdxl/validation.jsonl \
  --model-dir checkpoints/sdxl-lora
```

For promotion, copy only the exported LoRA `.safetensors` and `metadata.json` into
a clean inference directory. Do not promote optimizer/resume files. For ControlNet,
use the exported config, diffusion safetensors and matching metadata.

## Qwen visual supervision

```bash
accelerate launch --num_processes 1 -m furniture_ai.ml.train_vlm \
  --model-path data/models/evaluator --train data/vlm/train.jsonl \
  --validation data/vlm/validation.jsonl --root data/raw \
  --output checkpoints/qwen-vlm --epochs 3 --merge
```

The merged safetensors folder can be deployed in a new private vLLM replica after
evaluation. Update both the model lock/served artifact and `FURNITURE_VISION_REVISION`
to its immutable revision. Keep the served model alias equal to the configured
API name. Merging requires sufficient memory; the adapter is also retained.

## CubiCasa research pathway

The CubiCasa adapter is opt-in and separate because of its noncommercial terms.
The production floorplan trainer above does not depend on CubiCasa. If the use is
authorized research, install the official repository at an audited commit and its
requirements in a separate research environment. Export the official SVG/text
split format with `python -m furniture_ai.ml.export_cubicasa --help`; the exporter
requires explicit research acknowledgment and writes noncommercial provenance.
Configure `FURNITURE_ML_FLOORPLAN_BACKEND=cubicasa_research`,
`FURNITURE_ML_RESEARCH_ONLY=true`, the code directory, checkpoint path and exact
SHA-256. The adapter verifies the checksum and loads weights with `weights_only=True`.
Do not promote the resulting weights through the commercial release workflow.

## Promotion

Run held-out prediction/evaluation before deployment. The register command copies
safe inference files into an immutable directory and writes a **new** model lock;
it refuses noncommercial training metadata and reports for different weights.
See [EVALUATION.md](EVALUATION.md). Keep previous locks and directories for rollback.
