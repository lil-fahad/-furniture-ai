# Real data preparation and measured layout training — 2026-09-07

The source material is the user's `annotations_trainval2017.zip` plus the previously acquired ABO furniture and SpatialLM layout archives. No supplier integration was added. Source metadata, input digests, exact-duplicate grouping and separate research permissions travel with the derived rows.

| Dataset | Verified preparation | Partitions |
|---|---|---|
| ABO furniture | 56,751 unchanged ≤256px images; 12,022 products; 158,050 image/caption pairs | 41,816 train; 19,181 validation; 97,053 test |
| SpatialLM | 2,247 accepted rooms from 54,775 unique source rooms / 216,536 label records | 1,375 train; 371 validation; 314 test; 187 publisher holdouts reserved |
| User COCO archive | 4,149 candidate images / 11,725 selected furniture annotations before crowd/mask checks | Full acquisition incomplete |
| Actually downloaded COCO | 132 JPEGs, 22,018,677 image bytes; 348 original polygon masks | DINO: 116 train / 16 validation / 0 test; SAM: 309 train / 39 validation / 0 test |

The COCO downloader stopped when the execution environment's network policy blocked the public S3 image bucket. Candidate counts are not download counts. The partial dataset is explicitly not ready for a full training run; neither official held-out image evaluation nor pretrained DINO/SAM fine-tuning was completed here.

ABO assignments keep all product views and language variants together. Connected components created by exact shared image bytes retain held-out membership, producing a large test partition. These are measured final counts, not a claim of a 70/15/15 sample ratio. Near-duplicate visual auditing across products remains separate.

SpatialLM accepts only closed polygons and supported floor furniture that pass the application's actual dimensions, 0/90-degree rotation, piece-count and clearance requirements. Unsupported floor objects become fixed obstacles. 52,528 rooms are rejected with recorded reasons, including invalid geometry, missing supported pieces, collisions and unsupported annotations. Door keepout is a 15cm threshold proxy: hinges and swing arcs were not supplied. Existing publisher validation/test/reserved scenes remain quarantined. The style value is an application default, not a source style annotation.

## Actual training experiment

`FurnitureLayoutTransformer`, seed 42, five predeclared epochs, batch 16, accumulation 1, AdamW learning rate 0.0001, CPU float32, PyTorch 2.8.0+cpu. The local environment exposes no CUDA GPU. The best epoch is chosen only by validation mean batch loss. Evaluation compares that checkpoint against the identical architecture and original seed before optimizer updates, on 314 untouched test rooms containing 418 furniture pieces.

| Held-out metric | Initial weights | Trained epoch 5 |
|---|---:|---:|
| Mean room loss | 0.184202 | 0.159424 |
| Mean center distance, metres | 1.606642 | 1.520187 |
| Median center distance, metres | 1.205209 | 1.090529 |
| Rotation accuracy | 57.89% | 59.33% |
| Mean footprint IoU | 0.169562 | 0.163143 |
| Raw geometric pass rate | 26.11% | 26.43% |

Position and loss improve slightly; footprint IoU declines, and most raw layouts still fail geometric checks. This experiment does not establish production quality or better human design preference. No solver repair is applied during these measurements. All resulting weights remain noncommercial and are not promoted into serving.

Reproduce preparation and the measured experiment from `platform`:

```bash
python -m pip install --require-hashes -r requirements-test.lock
python -m pip install --no-deps -e .
python -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install accelerate==1.12.0 safetensors==0.7.0 huggingface-hub==0.36.2
python -m pip install --require-hashes -r requirements-data.lock
python -m furniture_ai.ml.import_abo --archive /path/FurnitureAI-ABO-furniture.zip --output data/abo
python -m furniture_ai.ml.import_spatiallm --archive /path/FurnitureAI-SpatialLM-layouts-research.zip --output data/spatiallm --research
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 ACCELERATE_USE_CPU=true python -m furniture_ai.ml.train --task layout --train data/spatiallm/train.jsonl --validation data/spatiallm/validation.jsonl --root data/spatiallm --output checkpoints/spatiallm-research-20260907 --epochs 5 --batch-size 16 --gradient-accumulation 1 --learning-rate 0.0001 --mixed-precision no --seed 42
OMP_NUM_THREADS=4 python -m furniture_ai.ml.evaluate_layout_run --run-dir checkpoints/spatiallm-research-20260907 --data-root data/spatiallm --output checkpoints/spatiallm-research-20260907/heldout-report.json
```

The Windows launcher is documented separately in [README-WINDOWS-AR.md](../README-WINDOWS-AR.md). Windows CI exercises installation and real Transformers forward/backward interfaces on CPU; a successful local CUDA preflight on the user's device remains required for GPU execution.

## Evidence

Machine-readable cards, the held-out report, loss history and actual-input interface checks are in `docs/evidence/20260907`. DINO and SAM interface checks use **small random Transformers configurations**, including original COCO image/mask inputs. They validate collate/forward/backward compatibility; they are not pretrained model accuracy results. The checked-in foundation test fixtures never become production checkpoints.

The trained weight digest is `35077c865254023c7ac2f4221a240dbbcde4c8a8e1e8cb1e79914a3fb59b5391`; train+validation manifest digest is `74743e1c0031cbfa56a94dbc7a5fb824218793680b6cee6860eb6b8c45d3ad58`.
