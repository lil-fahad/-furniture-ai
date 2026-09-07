# Evaluation and model release

Report the pretrained baseline and candidate on the same held-out properties,
seeds, prompts and hardware. Do not claim an improvement from training loss,
self-judgment, or this repository's synthetic unit tests. Keep a final property
test set separate from hyperparameter selection and annotate error slices.

## Metrics and provisional gates

Thresholds below are **proposed acceptance targets**, not achieved results. Tune
them with the product owner and an independent reference set before deployment.
Use meaningful sample sizes per room type, lighting, occlusion, plan style and
language. Bootstrap confidence intervals at property/group level outside the
per-record average; do not count correlated crops as independent properties.

| Model / system | Metrics implemented | Example gate |
|---|---|---|
| DINO | AP50, 101-point class-averaged interpolated precision | AP50 ≥ 0.65; ≥200 images |
| SAM 2 | Binary IoU, Dice with explicit empty-mask convention | IoU ≥0.80; ≥200 masks |
| Depth | Affine-aligned inverse-depth relative error | ≤0.15; ≥200 aligned depth maps |
| FloorplanNet | Room-class mIoU excluding label 255 | ≥0.75; ≥200 plans |
| Layout | Piece identity/dimensions, containment, keepout, clearance and connectivity pass rate | 1.0; ≥200 rooms |
| SigLIP 2 | Recall@10, NDCG@10, hit rate@10 | Recall@10 ≥0.85; ≥500 queries |
| Ranker | Held-out explicit pair preference accuracy | ≥0.65; ≥500 independent pairs |
| Qwen | JSON schema validity; MAE against human scores; unsupported dimensions | Validity ≥0.99; dimension rate ≤0.01 |
| SDXL | Unedited pixel MAE; blinded human candidate-vs-baseline preference | Pixel MAE=0; win rate ≥0.55 across ≥200 reviewed pairs |
| Serving | Per-request latency and p95 | Set from measured hardware and target SLO |

The provided AP implementation is AP50, **not** COCO AP@[.50:.95]. The depth metric
is for relative inverse depth, **not** metric-depth AbsRel. Current FloorplanNet
release scoring covers room classes; add reviewed icon/topology metrics to a
floor-plan product acceptance study. Access connectivity only checks the supplied
interior points, not every possible exit or statutory accessibility requirement.

## Generate predictions using actual weights

```bash
python -m furniture_ai.ml.predict --task ranker \
  --manifest data/ranker/test.jsonl --root data/raw \
  --model-path checkpoints/ranker/epoch-0020/model \
  --output data/eval/ranker-candidate --device cpu
python -m furniture_ai.ml.evaluate \
  --predictions data/eval/ranker-candidate/predictions.jsonl --root data/eval/ranker-candidate \
  --gates examples/gates-ranker.json --model-dir checkpoints/ranker/epoch-0020/model \
  --output data/eval/ranker-report.json
```

Replace the selected epoch with the actual `best.json` path. The prediction command
supports DINO, SAM 2, depth, FloorplanNet, layout and SigLIP with their manifest
schemas. SAM evaluation derives a box prompt from the annotated object mask and
therefore measures prompted segmentation; evaluate detector-to-mask errors in
the end-to-end room study as well. DINO AP prediction retains low-score detections
for ranking metrics; production has a higher operating threshold plus NMS.

SigLIP query captions retrieve images from the held-out gallery; `product_id`
groups equivalent positive views. Limit each invocation to 10,000 evaluation
records. Prediction artifacts contain private data and belong in the private
evaluation store, never in the Git repository.

## Evaluate rendering and visual judgment

Run full design jobs on a staging copy of the production model configuration.
Export results via the authenticated job JSON endpoint. Record independent human
labels with these evaluator-compatible JSONL fields:

* `evaluation_prediction`, `evaluation_target`: predicted and independently
  annotated `VisualEvaluation` objects; report validity and numeric score MAE.
* `analysis_prediction`, `dimension_labels_present`: analysis and a human boolean
  label identifying whether metric labels really occur in the source.
* `original_path`, `render_path`, `edit_mask_path`: aligned source, result and
  binary mask for exact unedited-pixel preservation.
* `human_prefers_candidate`: blinded reviewer boolean for candidate vs baseline.
* `latency_seconds`: measured end-to-end duration, with warm/cold runs separated.

All file paths are relative to `--root`. Never infer human preference from the
evaluator's own score. Preserve masks and independent labels alongside each
reviewed result so the evaluation can be reproduced. Schema-invalid examples
reduce the validity rate and do not silently count as successful scoring.

`ml.evaluate` refuses missing required metrics and insufficient sample counts.
Any failed gate exits nonzero. A report can bind to an inference folder using its
full file inventory SHA-256; it records the prediction-file digest and gate rules.

## Register and activate evaluated weights

```bash
python -m furniture_ai.ml.register --alias ranker \
  --source checkpoints/ranker/epoch-0020/model --report data/eval/ranker-report.json \
  --models-dir data/models --lock models.lock.json --output-lock models.release-002.json
```

The returned immutable path is the rank checkpoint. Configure
`FURNITURE_ML_RANK_CHECKPOINT=/models/ranker__DIGEST_PREFIX` on scoring replicas,
and `FURNITURE_RANKING_MODE=learned` on API/workers. For layout and floorplan use
their matching checkpoint variables, `FURNITURE_LAYOUT_MODE=transformer`, and
`FURNITURE_ML_FLOORPLAN_BACKEND=trained`.

For foundation aliases (`grounding_dino`, `sam2`, `depth_anything`, `siglip`,
`controlnet_canny`, `controlnet_depth`), set the new model lock on the corresponding
service. ModelSettings resolves each immutable local directory from that lock.
Register SDXL adapters under `sdxl_lora` and set `FURNITURE_ML_SDXL_LORA=true`.
Supply the new lock path via `FURNITURE_ML_LOCK_PATH` or replace its read-only mount
with the new release file. `ml.install --lock ... --verify` checks restored models.

Promotion checks artifact binding and rights; human governance still owns whether
the selected gates are sufficient. Run a canary, compare failure rates and quality,
then expand. Drain in-flight jobs before changing revisions. Roll back by restoring
the previous image, environment/checkpoint paths and lock together.
