import csv
from pathlib import Path

FURNITURE = [
    {"item_id": "chair-1", "name": "Modern Chair", "category": "chair", "price": 120.0},
    {"item_id": "sofa-1", "name": "Sectional Sofa", "category": "sofa", "price": 850.0},
    {"item_id": "table-1", "name": "Dining Table", "category": "table", "price": 400.0},
    {"item_id": "lamp-1", "name": "Arc Floor Lamp", "category": "lighting", "price": 90.0},
]


def build_catalog(output: Path = Path("datasets/furniture.csv")) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "name", "category", "price"])
        writer.writeheader()
        for row in FURNITURE:
            writer.writerow(row)
    print(f"[build_furniture] wrote catalog to {output}")


if __name__ == "__main__":
    build_catalog()
