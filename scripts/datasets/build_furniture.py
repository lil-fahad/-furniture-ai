import csv
from pathlib import Path

FURNITURE = [
    {"item_id": "chair-1", "name": "Modern Accent Chair", "category": "chair", "price": 120.0},
    {"item_id": "chair-2", "name": "Ergonomic Office Chair", "category": "chair", "price": 240.0},
    {"item_id": "chair-3", "name": "Wooden Dining Chair", "category": "chair", "price": 75.0},
    {"item_id": "sofa-1", "name": "Sectional Velvet Sofa", "category": "sofa", "price": 850.0},
    {"item_id": "sofa-2", "name": "Two-Seat Linen Sofa", "category": "sofa", "price": 620.0},
    {"item_id": "sofa-3", "name": "Convertible Sleeper Sofa", "category": "sofa", "price": 980.0},
    {"item_id": "table-1", "name": "Oak Dining Table", "category": "table", "price": 400.0},
    {"item_id": "table-2", "name": "Marble Coffee Table", "category": "table", "price": 320.0},
    {"item_id": "table-3", "name": "Walnut Side Table", "category": "table", "price": 150.0},
    {"item_id": "lamp-1", "name": "Arc Floor Lamp", "category": "lighting", "price": 90.0},
    {"item_id": "lamp-2", "name": "Brass Pendant Light", "category": "lighting", "price": 140.0},
    {"item_id": "lamp-3", "name": "LED Desk Lamp", "category": "lighting", "price": 55.0},
    {"item_id": "bed-1", "name": "King Platform Bed", "category": "bed", "price": 1200.0},
    {"item_id": "bed-2", "name": "Queen Upholstered Bed", "category": "bed", "price": 880.0},
    {"item_id": "shelf-1", "name": "Industrial Bookshelf", "category": "storage", "price": 260.0},
    {"item_id": "shelf-2", "name": "Modular Wall Shelf", "category": "storage", "price": 190.0},
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
