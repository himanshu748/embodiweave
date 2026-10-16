from copy import deepcopy

import pytest

from ew.recipes import RECIPES
from ew.rehearsal_study import comparison, development_suites, protocol
from ew.scenarios import SUITES


def test_rehearsal_is_the_only_changed_training_setting():
    changed = {k: v for k, v in RECIPES["ppo-rehearsal-v1"].items() if RECIPES["ppo-r1"].get(k) != v}
    assert changed == {"training_families": ["open", "static", "crossing", "static_crossing"]}


def test_recovery_development_uses_fresh_disjoint_seeds():
    suites = development_suites(protocol())
    assert sum(len(s.seeds) for s in suites) == 180
    assert all(s.role == "validation" and s.suite_id not in SUITES for s in suites)
    previous = {seed for suite in SUITES.values() for seed in suite.seeds}
    fresh = [seed for suite in suites for seed in suite.seeds]
    assert len(fresh) == len(set(fresh)) and not previous.intersection(fresh)


def test_development_comparison_rejects_regression_or_a_stationary_robot():
    parent = {f: {"episodes": 40, "success": 38, "collision": 2, "timeout": 0}
              for f in ("open", "static", "crossing", "static_crossing")}
    child = {f: {"episodes": 40, "success": 39, "collision": 1, "timeout": 0} for f in parent}
    assert comparison(parent, parent, child)["accepted_for_further_study"]
    bad = deepcopy(child)
    bad["crossing"] = {"episodes": 40, "success": 37, "collision": 3, "timeout": 0}
    assert not comparison(parent, parent, bad)["accepted_for_further_study"]
    for row in bad.values():
        row.update(success=0, collision=0, timeout=40)
    assert not comparison(parent, parent, bad)["accepted_for_further_study"]
    assert not comparison(parent, parent, parent)["accepted_for_further_study"]
    with pytest.raises(ValueError, match="All four"):
        comparison(parent, parent, {})
