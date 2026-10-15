"""Scenario families and versioned suites.

Scenario families are authored inputs. They are NOT a training order: any checkpoint may be
trained or evaluated on any family. Suites bind a family to a fixed seed list and a data role
(train / validation / final_test). Final-test suites are protected: the planner and agent
code paths refuse to read their outcomes (see ew.graph.queries and ew.agent.tools).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace

import numpy as np

WORLD = 10.0  # square arena side, metres


@dataclass(frozen=True)
class Family:
    name: str
    n_static: int = 0
    mover: bool = False
    mover_speed: tuple = (0.6, 1.0)   # m/s, uniform range
    mover_radius: float = 0.5
    static_radius: tuple = (0.35, 0.6)
    static_offset_sd: float = 0.5      # perpendicular offset from the start-goal line
    max_steps: int = 250

    def fid(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True).encode()
        return f"{self.name}@{hashlib.sha256(blob).hexdigest()[:8]}"


FAMILIES = {
    "open": Family("open"),
    "static": Family("static", n_static=3),
    "crossing": Family("crossing", mover=True),
    "static_crossing": Family("static_crossing", n_static=2, mover=True),
}


def with_controls(base: Family, n_static: int | None = None, mover_speed: float | None = None,
                  mover_radius: float | None = None) -> Family:
    """Apply the studio's scenario controls. Returns a new, distinctly identified family."""
    kw = {}
    if n_static is not None:
        if not 0 <= n_static <= 4:
            raise ValueError("n_static must be 0..4")
        kw["n_static"] = int(n_static)
    if mover_speed is not None:
        if not 0.2 <= mover_speed <= 1.5:
            raise ValueError("mover_speed must be 0.2..1.5 m/s")
        kw["mover_speed"] = (float(mover_speed), float(mover_speed))
        kw["mover"] = True
    if mover_radius is not None:
        if not 0.2 <= mover_radius <= 0.8:
            raise ValueError("mover_radius must be 0.2..0.8 m")
        kw["mover_radius"] = float(mover_radius)
    if not kw:
        return base
    return replace(base, name=f"{base.name}+custom", **kw)


def generate_layout(fam: Family, rng: np.random.Generator) -> dict:
    """Deterministic given rng state. Returns start, goal, static and moving obstacles."""
    for _ in range(200):
        sy, gy = rng.uniform(1.0, 9.0, size=2)
        start = np.array([rng.uniform(0.8, 1.8), sy])
        goal = np.array([rng.uniform(8.2, 9.2), gy])
        line = goal - start
        D = float(np.linalg.norm(line))
        u = line / D
        n = np.array([-u[1], u[0]])
        theta = math.atan2(u[1], u[0]) + rng.uniform(-math.pi / 3, math.pi / 3)

        statics = []
        ok = True
        if fam.n_static:
            fracs = np.linspace(0.25, 0.75, fam.n_static) + rng.uniform(-0.06, 0.06, fam.n_static)
            for f in fracs:
                r = rng.uniform(*fam.static_radius)
                c = start + u * f * D + n * rng.normal(0, fam.static_offset_sd)
                if (np.linalg.norm(c - start) < r + 0.8 or np.linalg.norm(c - goal) < r + 0.8
                        or not (r < c[0] < WORLD - r and r < c[1] < WORLD - r)):
                    ok = False
                    break
                statics.append([float(c[0]), float(c[1]), float(r)])
        if not ok:
            continue

        movers = []
        if fam.mover:
            f = rng.uniform(0.35, 0.65)
            cpt = start + u * f * D
            spd = rng.uniform(*fam.mover_speed)
            t_arr = f * D / 0.8  # nominal robot arrival time at 0.8 m/s
            back = spd * t_arr * rng.uniform(0.7, 1.3)
            side = rng.choice([-1.0, 1.0])
            p = cpt - side * n * back
            rr = fam.mover_radius
            p = np.clip(p, rr + 0.05, WORLD - rr - 0.05)
            vel = side * n * spd
            if np.linalg.norm(p - start) < rr + 1.0 or np.linalg.norm(p - goal) < rr + 0.6:
                continue
            movers.append([float(p[0]), float(p[1]), float(vel[0]), float(vel[1]), float(rr)])

        return {"start": [float(start[0]), float(start[1]), float(theta)],
                "goal": [float(goal[0]), float(goal[1])],
                "statics": statics, "movers": movers}
    raise RuntimeError("could not generate a valid layout")


@dataclass(frozen=True)
class Suite:
    suite_id: str
    version: str
    role: str            # validation | final_test
    family: Family
    seeds: tuple
    competency: str

    def to_record(self) -> dict:
        return {"suite_id": self.suite_id, "version": self.version, "role": self.role,
                "family": self.family.name, "family_id": self.family.fid(),
                "seeds": list(self.seeds), "episodes": len(self.seeds), "competency": self.competency}


def _seeds(base: int, n: int) -> tuple:
    return tuple(range(base, base + n))


# Validation and final-test seed ranges never overlap and never overlap training seeds
# (training draws from seeds < 1_000_000 via SB3's env seeding of base seed 0..999).
SUITES = {
    s.suite_id: s for s in [
        Suite("val-open-v1", "1", "validation", FAMILIES["open"], _seeds(1_000_000, 40), "reach_goal"),
        Suite("val-static-v1", "1", "validation", FAMILIES["static"], _seeds(1_100_000, 40), "avoid_static"),
        Suite("val-crossing-v1", "1", "validation", FAMILIES["crossing"], _seeds(1_200_000, 40), "yield_dynamic"),
        Suite("val-target-v1", "1", "validation", FAMILIES["static_crossing"], _seeds(1_300_000, 60), "static_crossing_mission"),
        Suite("test-target-v1", "1", "final_test", FAMILIES["static_crossing"], _seeds(9_000_000, 100), "static_crossing_mission"),
        # Added 2026-10-15 after exp-1 spent test-target-v1; disjoint seeds, same family and size.
        Suite("test-target-v2", "1", "final_test", FAMILIES["static_crossing"], _seeds(9_100_000, 100), "static_crossing_mission"),
        # Added 2026-10-15 after exp-2 spent test-target-v2.
        Suite("test-target-v3", "1", "final_test", FAMILIES["static_crossing"], _seeds(9_200_000, 100), "static_crossing_mission"),
    ]
}

# A final-test suite is spent once an experiment has reported on it. Only that experiment may evaluate on it again
# (to reproduce its own numbers); any changed method needs a fresh suite.
SPENT_FINAL_TESTS = {"test-target-v1": "exp-1", "test-target-v2": "exp-2", "test-target-v3": "exp-3"}

PROTECTED_ROLES = {"final_test"}
