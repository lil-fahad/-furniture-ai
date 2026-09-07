import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image

from furniture_ai.ml.data import read_jsonl
from furniture_ai.ml.dataset_io import grouped_splits, open_zip
from furniture_ai.ml.import_coco import export_records, inspect_annotations
from furniture_ai.ml.import_spatiallm import RejectedLayout, convert_layout, parse_layout


@pytest.mark.parametrize("name", ["../escape.jpg", "/escape.jpg", "C:/escape.jpg", "images\\escape.jpg"])
def test_archive_paths_cannot_escape_dataset(name):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as archive:
        archive.writestr(name, b"untrusted")
    memory.seek(0)
    with pytest.raises(ValueError):
        open_zip(memory)


def test_product_views_and_cross_product_exact_copies_do_not_leak():
    rows = [
        {"id": "sku1-en", "group_id": "sku1", "sha256": "a", "proposed_split": "train"},
        {"id": "sku1-ar", "group_id": "sku1", "sha256": "b", "proposed_split": "train"},
        {"id": "sku2-ko", "group_id": "sku2", "sha256": "b", "proposed_split": "test"},
        {"id": "sku3-zh", "group_id": "sku3", "sha256": "c", "proposed_split": "validation"},
    ]
    splits = grouped_splits(rows)
    assert not splits["train"]
    assert {row["id"] for row in splits["test"]} == {"sku1-en", "sku1-ar", "sku2-ko"}
    assert len({row["split_group"] for row in splits["test"]}) == 1
    assert splits["validation"][0]["id"] == "sku3-zh"


def test_multilingual_manifests_use_utf8_on_windows(tmp_path):
    path = tmp_path / "captions.jsonl"
    caption = "كرسي · 椅子 · 의자"
    path.write_bytes((json.dumps({"caption": caption}, ensure_ascii=False) + "\n").encode("utf-8"))
    assert list(read_jsonl(path))[0]["caption"] == caption


@pytest.mark.parametrize(
    "payload",
    [
        "x = __import__('os').system('bad')",
        "import os",
        "x = Bbox(chair, 1+1, 1, 1, 0, 1, 1, 1)",
        "x = Bbox(chair, float('nan'), 1, 1, 0, 1, 1, 1)",
        "x = Bbox(chair, 1e100, 1, 1, 0, 1, 1, 1)",
    ],
)
def test_spatiallm_labels_are_data_not_executable_python(payload):
    with pytest.raises(RejectedLayout):
        parse_layout(payload)


ROOM = """wall_0 = Wall(0,0,0,5,0,0,3,0.1)
wall_1 = Wall(5,0,0,5,4,0,3,0.1)
wall_2 = Wall(5,4,0,0,4,0,3,0.1)
wall_3 = Wall(0,4,0,0,0,0,3,0.1)
bbox_0 = Bbox(chair,1,1,0.5,0,0.6,0.7,1)
"""


def test_spatiallm_preserves_metres_and_quarantines_publisher_test():
    source = {"id": "scene_000001_00_0", "scene_id": "scene_000001", "split": "test", "room_type": "bedroom"}
    row = convert_layout(ROOM, source)
    assert row["pieces"][0]["width_m"] == 0.6
    assert row["placements"][0]["x"] == 0.7
    assert row["proposed_split"] == "reserved"
    assert row["commercial_use"] is False
    assert row["conversion"]["source_style_label_available"] is False
    with pytest.raises(RejectedLayout, match="heterogeneous_sizes"):
        convert_layout(ROOM + "bbox_1 = Bbox(chair,3,1,0.5,0,0.9,0.7,1)\n", source)


def test_coco_selects_licensed_images_and_exports_source_polygon(tmp_path):
    pytest.importorskip("ijson")
    pytest.importorskip("pycocotools")
    archive_path = tmp_path / "annotations.zip"
    categories = [
        {"id": i, "name": name}
        for i, name in [(62, "chair"), (63, "couch"), (65, "bed"), (67, "dining table")]
    ]
    license_record = {
        "id": 4,
        "name": "Attribution License",
        "url": "http://creativecommons.org/licenses/by/2.0/",
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        for split, offset in [("train2017", 0), ("val2017", 10)]:
            images = [
                {
                    "id": offset + i,
                    "file_name": f"{offset + i:012d}.jpg",
                    "width": 16,
                    "height": 12,
                    "license": license_id,
                    "flickr_url": "https://flickr.com/test",
                }
                for i, license_id in [(1, 4), (2, 2)]
            ]
            annotations = [
                {
                    "id": offset + i,
                    "image_id": offset + i,
                    "category_id": 67,
                    "bbox": [2, 2, 8, 8],
                    "iscrowd": 0,
                    "segmentation": [[2, 2, 10, 2, 2, 10]],
                }
                for i in (1, 2)
            ]
            data = {
                "images": images,
                "annotations": annotations,
                "categories": categories,
                "licenses": [
                    license_record,
                    {
                        "id": 2,
                        "name": "Noncommercial",
                        "url": "https://creativecommons.org/licenses/by-nc/2.0/",
                    },
                ],
            }
            archive.writestr(f"annotations/instances_{split}.json", json.dumps(data))
    rows, report = inspect_annotations(archive_path)
    assert len(rows) == 2 and report["image_bytes_in_attachment"] is False
    research, _ = inspect_annotations(archive_path, research=True)
    assert len(research) == 4
    for row in rows:
        row["download"] = ("image.jpg", "same-image-bytes", 100)
    result = export_records(rows, tmp_path / "derived")
    assert result["exported_records"]["dino"]["train"] == 0
    assert result["exported_records"]["dino"]["test"] == 2  # Official holdout wins for exact duplicates.
    records = [json.loads(line) for line in (tmp_path / "derived/dino/test.jsonl").read_text().splitlines()]
    assert records[0]["categories"][3] == "dining table"
    assert records[0]["boxes"][0]["category_id"] == 3
    mask = np.asarray(Image.open(tmp_path / "derived/masks/train2017/1.png"))
    assert mask.shape == (12, 16) and 0 < np.count_nonzero(mask) < 8 * 8
    assert mask[3, 3] == 255 and mask[9, 9] == 0  # Polygon, not a fabricated rectangular mask.


def test_gpu_doctor_reports_cpu_without_claiming_cuda(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    from furniture_ai.ml import gpu_doctor

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(gpu_doctor.shutil, "which", lambda _: None)
    report = gpu_doctor.inspect_gpu()
    assert report["kernel_check"] is False and report["devices"] == [] and report["errors"]
