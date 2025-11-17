from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Furniture(Base):
    __tablename__ = "furniture"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    style = Column(String(50), nullable=False, default="modern")
    materials = Column(String(255), nullable=False, default="")

    def material_list(self) -> list[str]:
        return [material for material in self.materials.split(",") if material]

    def __repr__(self) -> str:  # pragma: no cover - representation only
        return f"<Furniture id={self.id} name={self.name} style={self.style}>"
