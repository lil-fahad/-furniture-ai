from pathlib import Path
import json
import csv


def train(catalog_path: Path = Path("datasets/furniture.csv")) -> Path:
    model_dir = Path("models/recommender")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "model.pt"
    report_path = model_dir / "report.json"

    prices = []
    if catalog_path.exists():
        with catalog_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    prices.append(float(row.get("price", 0)))
                except Exception:
                    pass
    avg_price = sum(prices) / len(prices) if prices else 0.0
    metrics = {"items": len(prices), "avg_price": avg_price, "top_k": 3}

    model_path.write_text("dummy recommender weights")
    report_path.write_text(json.dumps(metrics, indent=2))
    print(f"[train_recommender] saved model to {model_path}")
    print(f"[train_recommender] report: {report_path}")
    return model_path


if __name__ == "__main__":
    train()
