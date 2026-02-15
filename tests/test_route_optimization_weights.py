"""
Tests for route optimization weights and mode modifiers (ROUTE_OPTIMIZATION_ENGINE).
"""
import pytest

from services.route_optimization.weights import (
    MODE_WEIGHTS,
    get_weights,
    mode_modifier,
)


class TestModeWeights:
    def test_all_modes_sum_to_one(self):
        for mode, (a, b, g) in MODE_WEIGHTS.items():
            assert abs(a + b + g - 1.0) < 1e-9, f"{mode}: alpha+beta+gamma != 1"

    def test_commute_commuter_same(self):
        assert get_weights("commute") == get_weights("commuter")

    def test_jogger_jog_same(self):
        assert get_weights("jogger") == get_weights("jog")

    def test_cyclist_cycle_same(self):
        assert get_weights("cyclist") == get_weights("cycle")

    def test_unknown_mode_defaults_to_commute(self):
        assert get_weights("unknown") == MODE_WEIGHTS["commute"]
        assert get_weights(None) == MODE_WEIGHTS["commute"]
        assert get_weights("") == MODE_WEIGHTS["commute"]

    def test_jogger_has_high_exposure_weight(self):
        a, _, _ = get_weights("jogger")
        assert a > 0.5

    def test_commute_has_balanced_distance_time(self):
        _, b, g = get_weights("commute")
        assert abs(b - g) < 0.01


class TestModeModifier:
    def test_neutral_default(self):
        assert mode_modifier({}, "commute") == 1.0
        assert mode_modifier({"highway": "residential"}, "cyclist") == 1.0

    def test_jogger_penalty_motorway(self):
        m = mode_modifier({"highway": "motorway"}, "jogger")
        assert m == 2.0

    def test_jogger_penalty_trunk(self):
        assert mode_modifier({"highway": "trunk"}, "jogger") == 2.0

    def test_jogger_bonus_footway(self):
        m = mode_modifier({"highway": "footway"}, "jogger")
        assert m == 0.5

    def test_jogger_bonus_park(self):
        m = mode_modifier({"leisure": "park"}, "jogger")
        assert m == 0.5

    def test_cyclist_bonus_cycleway(self):
        m = mode_modifier({"cycleway": "lane"}, "cyclist")
        assert m == 0.7

    def test_cyclist_penalty_motorway(self):
        m = mode_modifier({"highway": "motorway"}, "cyclist")
        assert m == 1.5

    def test_commuter_penalty_footway(self):
        m = mode_modifier({"highway": "footway"}, "commute")
        assert m == 1.2

    def test_commuter_no_penalty_footway_with_access(self):
        m = mode_modifier({"highway": "footway", "access": "yes"}, "commute")
        assert m == 1.0

    def test_highway_list_takes_first(self):
        # Implementation takes first element when highway is a list (see weights.py)
        m = mode_modifier({"highway": ["motorway", "primary"]}, "jogger")
        assert m == 2.0

    def test_modifier_clamped(self):
        # Multiple penalties could exceed 5.0
        m = mode_modifier({"highway": "motorway", "leisure": "park"}, "jogger")
        assert 0.1 <= m <= 5.0
