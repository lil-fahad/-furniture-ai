from pathlib import Path
from typing import Iterable
from PIL import Image


def find_images(root: Path) -> Iterable[Path]:
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.svg"):
        yield from root.rglob(ext)


def convert_svg_to_png(svg_path: Path) -> Path:
    png_path = svg_path.with_suffix(".png")
    try:
        import cairosvg

        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        return png_path
    except Exception:
        return svg_path


def normalize_images(dataset_root: Path) -> None:
    processed_dir = dataset_root / "processed"
    images_dir = processed_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for img_path in find_images(dataset_root):
        if img_path.suffix.lower() == ".svg":
            img_path = convert_svg_to_png(img_path)
        try:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                target = images_dir / img_path.with_suffix(".png").name
                img.save(target)
                print(f"[preprocess] normalized {img_path} -> {target}")
        except Exception as exc:
            print(f"[preprocess] skip {img_path}: {exc}")


def export_dummy_yolo_labels(dataset_root: Path) -> None:
    processed_dir = dataset_root / "processed"
    labels_dir = processed_dir / "labels"
    images_dir = processed_dir / "images"
    labels_dir.mkdir(parents=True, exist_ok=True)

    for img in images_dir.glob("*.png"):
        label_path = labels_dir / f"{img.stem}.txt"
        label_path.write_text("0 0.5 0.5 1.0 1.0\n")

    print(f"[preprocess] generated YOLO labels in {labels_dir}")


def build_yolo_yaml(dataset_root: Path) -> Path:
    processed_dir = dataset_root / "processed"
    yaml_path = processed_dir / "data.yaml"
    yaml_content = "\n".join(
        [
            f"path: {processed_dir}",
            "train: images",
            "val: images",
            "names:",
            "  0: room",
            "",
        ]
    )

    yaml_path.write_text(yaml_content)
    print(f"[preprocess] wrote config {yaml_path}")
    return yaml_path


def preprocess_all(root: Path = Path("datasets")) -> None:
    for dataset in root.iterdir():
        if dataset.is_dir():
            print(f"[preprocess] processing {dataset.name}")
            normalize_images(dataset)
            export_dummy_yolo_labels(dataset)
            build_yolo_yaml(dataset)


if __name__ == "__main__":
    preprocess_all()
