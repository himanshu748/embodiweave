# MuJoCo transfer protocol v1

This is a **sim-to-sim transfer test**, not MuJoCo training, a new promotion
gate, or a real-world safety claim. All three PPO checkpoints were trained in
the original 2D kinematic simulator. Their model files and normalization
statistics are loaded unchanged, verified by SHA-256, and frozen for evaluation.
No transfer outcome is used to select, retrain or deploy a checkpoint.

## Interface mapping

The adapter is `sim/mujoco/environment.py`. The original contract remains
`ew-contract-1:2f013b6f4849`; this identifies the reused tensor semantics, **not
equivalent dynamics**. The separate physics/protocol fingerprint identifies the
transfer domain. The original environment, suite definitions and promo-1 code
are unchanged.

| Item | Original meaning and MuJoCo adapter |
|---|---|
| World | 10 m square. Same `generate_layout` function; every checkpoint gets the same saved layouts. |
| Control | 0.1 s; 20 contact-dynamics substeps of 0.005 s. Maximum 250 control steps, or 25 simulated seconds. A collision stops early at its actual substep. |
| Action | Clip both components to [-1, 1]. `v=(a[0]+1)/2` m/s, `w=2*a[1]` rad/s. No reverse body command. |
| Wheels | Radius 0.09 m, track 0.30 m. Left `(v-w*track/2)/radius`, right `(v+w*track/2)/radius`, rad/s. Wheel velocity servos have gain 0.5 and torque limits +/-3 Nm. Actual body velocity is not commanded or overwritten. |
| Pose | Robot free joint under gravity, floor friction and obstacle contacts. Project body position to XY; extract yaw from its body rotation matrix. |
| Frame[0:3] | Goal distance / 10 clipped to 1.5; cosine and sine of robot-relative goal bearing, identical formulas. |
| Frame[3:5] | Previous **commanded** v and w / their maxima, not measured wheel or body velocities. |
| Frame[5:17] | Twelve real MuJoCo rangefinder sensors, body-relative angles 0, 30, ...330 degrees CCW. Local +Z site axes point horizontally at reset. |
| Free range | Sensors originate above the robot centre, 0.42 m above the ground at reset. Subtract the 0.20 m robot radius from centre-to-surface distance and clip to [0,4] m, then divide by 4. No-hit (-1) maps to 4 m. Sensor cutoff is 4.2 m centre distance. |
| History | Three 17-float frames, newest first, float32 length 51. Reset fills all three slots with the same first frame. |
| Normalization | The checkpoint's own saved `VecNormalize`, `training=False`, `norm_reward=False`; no statistic updates. Deterministic PPO inference. |
| Terminal | Actual penetrating robot-obstacle/wall contact has priority over goal distance <0.30 m. Floor and self contacts are excluded from collision outcomes. Timeout at 250 steps. |

## Known mismatches, declared before measurement

- Original motion is an exact unicycle arc with instantaneous command tracking.
  MuJoCo has gravity 9.81 m/s², finite mass, inertia, torque, acceleration, slip,
  roll and pitch. The wheel servos can lag or saturate. No dynamics parameters
  are fitted to checkpoint success rates.
- The physical chassis is a 0.20 m radius cylinder with two wheels and two
  low-friction spherical caster approximations. The casters slide rather than
  swivel. Its contact footprint and mass distribution are approximations of an
  authored robot, not a calibrated real robot. Visual wheel trim also has mass.
- Default contact friction is sliding 1, torsional 0.005, rolling 0.0001;
  caster sliding friction is 0.01, with priority 1 so it overrides the floor's
  friction at caster contacts, and three-dimensional contact constraints.
  Joint damping 0.02, armature 0.002. Soft
  contacts use `solref=.01 1`, `solimp=.95 .99 .001`. These parameters are fixed
  for all candidates. The solver uses `implicitfast` with 50 iterations.
- Original collisions are 2D overlap tests at control-step endpoints. Here
  physical contacts are checked every 5 ms, including contacts between control
  samples. Capsule pedestrians have a 0.50 m horizontal radius. Statics are
  cylinders with the original radii; arena walls' inner faces remain at 0/10 m.
- Pedestrians are mocap capsules with infinite effective mass, following the
  original linear velocities and boundary reflection rule. They advance every
  physics substep rather than once after each robot control step. They are
  scripted obstacles, not simulated humans or learned pedestrian agents.
- Original rays intersect 2D circles from the robot centre. MuJoCo rangefinders
  intersect 3D surfaces at sensor height; robot tilt changes their directions.
  At level reset the observations match, including radius subtraction. Raised
  geometry, tilt and contact deformation can change later readings. No sensor
  noise is added in either simulator; this is not realistic lidar noise.
- Goal information uses ground-truth simulator pose, not localization. Rewards
  are not used for learning here. The adapter reports progress and terminal
  rewards only; no MuJoCo optimization occurs.

## Measurement and replay

`python -m sim.mujoco.evaluate` freezes `evidence/mujoco-v1/protocol.json`
before any checkpoint episode. It records source hashes, software version,
artifact hashes and four **fresh** 40-seed suites: open, static, crossing and
static_crossing. Seeds start at 5100000, 5101000, 5102000 and 5103000. These
are not validation or held-out suites. No final-test access is needed.

Every episode records outcome, contact type, steps, actual physics duration,
layout, model XML checksum and a compressed trajectory. Trajectories contain
real simulated joint positions at approximately 30 Hz, exact sample times,
pedestrian mocap positions, ranges and policy actions. Rendering replays these
recorded states without interpolating or animating robot poses. A slower replay
repeats recorded frames; cameras, trails, rays and titles are visual overlays.

The filming rule is frozen too: show a deployed collision in a pedestrian
suite, preferring a seed where the rehearsal checkpoint reaches the goal.
That is a selected illustrative episode; the complete suite aggregates remain
visible. It is not an estimate from one attractive replay.

`python -m ew.graph.transfer` verifies evidence checksums and appends Suite
nodes (`role='sim2sim'`, `physics='mujoco'`), exact-artifact Evaluation nodes
and collision Failure nodes. Rebuild imports the same immutable evidence. No
Threshold, Decision or Promotion is created from these outcomes. Existing
selection and gate queries explicitly require validation suites.

## Running locally

Install the main CPU requirements, then the optional pinned
`requirements-mujoco.txt`. Run `python -m pytest tests/test_mujoco.py` before
measurement. Evaluation is CPU only and needs no graphics context. Rendering
uses MuJoCo's offscreen renderer; on Linux use `MUJOCO_GL=egl` or
`MUJOCO_GL=osmesa` with the corresponding system library. macOS uses its
native CGL offscreen context. Rendering backends do not change the CPU physics.

Reference: [MuJoCo rangefinder semantics](https://mujoco.readthedocs.io/en/3.3.7/XMLreference.html#sensor-rangefinder).
