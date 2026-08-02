"""Compile a synthetic graph cut into dry-run review artifacts."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.compiler import CompileRequest, PRCompiler, RiskLevel
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import AtomKind, AtomState, IntentAtom
from cognitive_os.store import AppendOnlyEventStore


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "layer4_compile.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        graph = IntentGraph(
            fixture["graph_id"],
            AppendOnlyEventStore(Path(directory) / "events.jsonl"),
        )
        for value in fixture["atoms"]:
            graph.add_atom(
                IntentAtom(
                    atom_id=value["atom_id"],
                    source_id="src_demo_layer4",
                    kind=AtomKind(value["kind"]),
                    statement=value["statement"],
                    source_start=0,
                    source_end=len(value["statement"]),
                    state=AtomState(value["state"]),
                    requires_human_confirmation=value["kind"] == "actionable",
                )
            )
        for dependent, prerequisite in fixture["dependencies"]:
            graph.add_dependency(dependent, prerequisite)
        for first, second in fixture["conflicts"]:
            graph.add_conflict(first, second)
        cluster = fixture["cluster"]
        graph.define_cluster(
            cluster["cluster_id"], cluster["label"], cluster["members"]
        )
        request_value = fixture["request"]
        request = CompileRequest(
            title=request_value["title"],
            outcome=request_value["outcome"],
            target_atom_ids=tuple(request_value["target_atom_ids"]),
            owned_paths=tuple(request_value["owned_paths"]),
            acceptance_criteria=tuple(request_value["acceptance_criteria"]),
            verification_steps=tuple(request_value["verification_steps"]),
            explicit_exclusions=tuple(request_value["explicit_exclusions"]),
            risk=RiskLevel(request_value["risk"]),
            max_atoms=request_value["max_atoms"],
        )
        proposal = PRCompiler().compile(graph.snapshot(), request)
        print(json.dumps(proposal.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
