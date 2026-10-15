"""Evaluate an exported checkpoint without a worker, database, or API key."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate", help="Reload model and normalization, then evaluate fixed suite seeds")
    evaluate.add_argument("--policy-dir", type=Path, required=True)
    evaluate.add_argument("--suite", default="val-target-v1")
    evaluate.add_argument("--episodes", type=int, help="Smoke subset, reported as incomplete evidence")
    evaluate.add_argument("--output", type=Path)
    args = parser.parse_args()
    from . import artifacts, rl
    from .scenarios import SUITES
    if args.suite not in SUITES or SUITES[args.suite].role != "validation":
        parser.error("choose a versioned validation suite; protected final tests are excluded")
    suite = SUITES[args.suite]
    if args.episodes is not None and not 1 <= args.episodes <= len(suite.seeds):
        parser.error("episodes must be within the suite's declared size")
    artifacts.verify_directory(args.policy_dir)
    manifest = json.loads((args.policy_dir / "manifest.json").read_text())
    seeds = suite.seeds[:args.episodes] if args.episodes else suite.seeds
    result = rl.evaluate_policy(manifest["policy_id"], suite.family, seeds, policy_path=args.policy_dir)
    result.update(suite_id=suite.suite_id, suite_version=suite.version,
                  complete_suite=len(seeds) == len(suite.seeds))
    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
