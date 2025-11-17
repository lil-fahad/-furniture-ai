from app.ai_engine.models.yolo import YOLODetector


def run_training() -> str:
    """Simulate a training workflow for the detection model."""

    detector = YOLODetector()
    _ = detector.detect()
    return "Training pipeline initialized"


if __name__ == "__main__":
    print(run_training())
