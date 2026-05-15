"""
FurnitureAI — نقطة الدخول الموحدة
====================================
يشغّل خادم FastAPI الرئيسي مباشرةً.

التشغيل:
    uvicorn main:app --reload --port 8000

أو عبر Python:
    python main.py
"""

import uvicorn
from backend.main import app  # noqa: F401  — re-export for uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
