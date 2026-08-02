from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .compiler import CompilerError
from .graph import GraphError
from .intents import IntentLifecycleError
from .pipeline import DryRunControlPlane, DryRunError, DryRunManifest
from .project_decision_loop import (
    DecisionLoopError,
    ProjectDecisionLoop,
    ProjectDecisionManifest,
    RelationshipDecision,
)
from .store import AppendOnlyEventStore, StoreError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cognitive-os",
        description="Compile conversational intent into local dry-run review artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run a versioned dry-run manifest")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--store", type=Path, required=True)
    mvp = subparsers.add_parser(
        "mvp", help="run the local-only two-project decision loop"
    )
    mvp.add_argument("--manifest", type=Path, required=True)
    mvp.add_argument("--store", type=Path, required=True)
    mvp.add_argument("--decision", choices=("accept", "reject"), required=True)
    mvp.add_argument("--human-actor", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest_value = json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.command == "mvp":
            manifest = ProjectDecisionManifest.from_dict(manifest_value)
            result = ProjectDecisionLoop(AppendOnlyEventStore(args.store)).run(
                manifest,
                RelationshipDecision(args.decision),
                human_actor=args.human_actor,
            )
        else:
            manifest = DryRunManifest.from_dict(manifest_value)
            result = DryRunControlPlane(AppendOnlyEventStore(args.store)).run(manifest)
    except (
        OSError,
        json.JSONDecodeError,
        DryRunError,
        StoreError,
        CompilerError,
        GraphError,
        IntentLifecycleError,
        DecisionLoopError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(json.dumps({"error": str(exc), "external_effects": False}), file=sys.stderr)
        return 2
    value = result if isinstance(result, dict) else result.to_dict()
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
