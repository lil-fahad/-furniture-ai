from copy import deepcopy

import pytest

from furniture_ai.errors import DomainError
from furniture_ai.layout import plan_layouts, validate_layout
from furniture_ai.schemas import Geometry, Preferences


def test_plans_satisfy_geometry_and_are_reproducible(geometry):
    g, prefs = Geometry.model_validate(geometry), Preferences(variants=2)
    result = plan_layouts(g, prefs)
    assert result and result == plan_layouts(g, prefs)
    for plan in result:
        validate_layout(g, plan["pieces"], prefs)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "shrunken", "outside", "nan", "overlap"])
def test_rejects_invalid_neural_or_evaluated_layout(geometry, fault):
    g, prefs = Geometry.model_validate(geometry), Preferences(variants=1)
    poses = deepcopy(plan_layouts(g, prefs)[0]["pieces"])
    if fault == "missing":
        poses.pop()
    elif fault == "duplicate":
        poses[1] = poses[0]
    elif fault == "shrunken":
        poses[0]["width_m"] /= 2
    elif fault == "outside":
        poses[0]["x"] = 100
    elif fault == "nan":
        poses[0]["y"] = float("nan")
    else:
        poses[1].update(x=poses[0]["x"], y=poses[0]["y"])
    with pytest.raises(DomainError):
        validate_layout(g, poses, prefs)


def test_reserved_zone_and_walkway(geometry):
    geometry["keepouts"] = [
        {
            "kind": "door",
            "label": "Door swing",
            "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1}],
        }
    ]
    geometry["access_points"] = [{"x": 0.6, "y": 0.6}, {"x": 4.4, "y": 3.4}]
    g = Geometry.model_validate(geometry)
    prefs = Preferences(requirements=[{"category": "sofa"}], variants=1)
    result = plan_layouts(g, prefs)
    validate_layout(g, result[0]["pieces"], prefs)
    assert result[0]["access_checked"]
