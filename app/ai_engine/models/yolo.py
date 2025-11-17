from typing import List


class YOLODetector:
    def detect(self, image_url: str) -> List[dict]:
        # Placeholder implementation for object detection
        return [
            {"object": "chair", "confidence": 0.93, "source": image_url},
            {"object": "table", "confidence": 0.88, "source": image_url},
        ]
