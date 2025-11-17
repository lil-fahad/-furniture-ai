from typing import List


class Recommender:
    def recommend(self, style: str, primary_material: str) -> List[str]:
        base_recommendations = {
            "modern": ["minimalist coffee table", "sleek floor lamp"],
            "industrial": ["exposed steel bookshelf", "edison bulb lamp"],
            "classic": ["tufted ottoman", "mahogany sideboard"],
        }
        matches = base_recommendations.get(style.lower(), ["accent pillow set", "wall art"])
        return [f"{item} ({primary_material})" for item in matches]
