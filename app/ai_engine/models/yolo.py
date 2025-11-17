class YOLODetector:
    """Placeholder YOLO model wrapper."""

    def detect(self) -> list[dict[str, str]]:
        """Return canned detection results for development demos."""
        return [
            {"label": "chair", "confidence": "0.87"},
            {"label": "table", "confidence": "0.82"},
        ]
