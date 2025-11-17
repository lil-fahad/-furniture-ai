from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Furniture(Base):
    """Simple SQLAlchemy model for furniture records."""

    __tablename__ = "furniture"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=True)


__all__ = ["Base", "Furniture"]
