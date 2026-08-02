from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.compiler import (
    CompileRequest,
    CompilerError,
    PermissionClass,
    PRCompiler,
    RiskLevel,
)
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import AtomKind, AtomState, IntentAtom
from cognitive_os.store import AppendOnlyEventStore


def atom(atom_id, state=AtomState.CONFIRMED, kind=AtomKind.ACTIONABLE):
    return IntentAtom(
        atom_id=atom_id,
        source_id="src_%s" % atom_id,
        kind=kind,
        statement="Work item %s." % atom_id,
        source_start=0,
        source_end=12,
        state=state,
        requires_human_confirmation=kind == AtomKind.ACTIONABLE,
    )


class PRCompilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        store = AppendOnlyEventStore(Path(self.temp.name) / "events.jsonl")
        graph = IntentGraph("graph_compile", store)
        for item in (
            atom("foundation"),
            atom("target"),
            atom("alternative"),
            atom("constraint", state=AtomState.PROPOSED, kind=AtomKind.CONSTRAINT),
        ):
            graph.add_atom(item)
        graph.add_dependency("target", "foundation")
        graph.add_conflict("target", "alternative")
        graph.define_cluster(
            "compiler", "Compiler", ["foundation", "target", "constraint"]
        )
        self.snapshot = graph.snapshot()
        self.compiler = PRCompiler()
        self.request = CompileRequest(
            title="Add a dry-run compiler",
            outcome="Produce a reviewable plan and execution brief.",
            target_atom_ids=("target",),
            owned_paths=("cognitive_os/compiler.py", "tests/test_compiler.py"),
            acceptance_criteria=("Dependency closure is preserved.",),
            verification_steps=("python3 -m unittest -v tests.test_compiler",),
            explicit_exclusions=("Do not create a real pull request.",),
            risk=RiskLevel.LOW,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_compiles_dependency_closed_topological_cut(self):
        proposal = self.compiler.compile(self.snapshot, self.request)
        self.assertEqual(("foundation", "target"), proposal.plan.selected_atom_ids)
        self.assertEqual(("foundation",), proposal.plan.dependency_map["target"])
        self.assertEqual(PermissionClass.DRAFT_ONLY, proposal.plan.permission_class)
        self.assertTrue(proposal.plan.dry_run)

    def test_brief_is_deep_bounded_and_routes_to_terra_high(self):
        brief = self.compiler.compile(self.snapshot, self.request).brief
        self.assertEqual("terra", brief.executor)
        self.assertEqual("high", brief.reasoning_effort)
        self.assertEqual(self.request.owned_paths, brief.owned_paths)
        self.assertTrue(brief.verification_steps)
        self.assertEqual(4, len(brief.stop_conditions))
        self.assertIn("P1 draft only", brief.permission_boundary)

    def test_relevant_constraint_and_external_conflict_become_exclusions(self):
        proposal = self.compiler.compile(self.snapshot, self.request)
        self.assertEqual(("Work item constraint.",), proposal.plan.constraints)
        self.assertTrue(
            any("alternative" in value for value in proposal.plan.exclusions)
        )
        self.assertIn("Work item constraint.", proposal.brief.explicit_exclusions)

    def test_ids_are_deterministic_for_same_graph_cut(self):
        first = self.compiler.compile(self.snapshot, self.request)
        second = self.compiler.compile(self.snapshot, self.request)
        self.assertEqual(first.plan.plan_id, second.plan.plan_id)
        self.assertEqual(first.brief.brief_id, second.brief.brief_id)

    def test_unconfirmed_target_or_dependency_is_rejected(self):
        pending_graph = IntentGraph(
            "pending", AppendOnlyEventStore(Path(self.temp.name) / "pending.jsonl")
        )
        pending_graph.add_atom(atom("pending", state=AtomState.AWAITING_CONFIRMATION))
        pending_request = CompileRequest(
            **{
                **self.request.__dict__,
                "target_atom_ids": ("pending",),
            }
        )
        with self.assertRaisesRegex(CompilerError, "unconfirmed"):
            self.compiler.compile(pending_graph.snapshot(), pending_request)

    def test_non_actionable_dependency_is_rejected(self):
        graph = IntentGraph(
            "non_action", AppendOnlyEventStore(Path(self.temp.name) / "non_action.jsonl")
        )
        graph.add_atom(atom("action"))
        graph.add_atom(atom("question", state=AtomState.PROPOSED, kind=AtomKind.EXPLORATION))
        graph.add_dependency("action", "question")
        request = CompileRequest(
            **{**self.request.__dict__, "target_atom_ids": ("action",)}
        )
        with self.assertRaisesRegex(CompilerError, "non-actionable"):
            self.compiler.compile(graph.snapshot(), request)

    def test_internal_conflict_is_rejected(self):
        request = CompileRequest(
            **{
                **self.request.__dict__,
                "target_atom_ids": ("target", "alternative"),
            }
        )
        with self.assertRaisesRegex(CompilerError, "contains conflict"):
            self.compiler.compile(self.snapshot, request)

    def test_oversized_cut_is_rejected(self):
        request = CompileRequest(**{**self.request.__dict__, "max_atoms": 1})
        with self.assertRaisesRegex(CompilerError, "above max_atoms"):
            self.compiler.compile(self.snapshot, request)

    def test_unsafe_owned_paths_are_rejected(self):
        for unsafe in ("/tmp/output", "../escape", "src/*.py", "src\\file.py"):
            request = CompileRequest(
                **{**self.request.__dict__, "owned_paths": (unsafe,)}
            )
            with self.subTest(path=unsafe):
                with self.assertRaisesRegex(CompilerError, "unsafe owned path"):
                    self.compiler.compile(self.snapshot, request)

    def test_missing_evidence_contract_is_rejected(self):
        request = CompileRequest(
            **{**self.request.__dict__, "verification_steps": ()}
        )
        with self.assertRaisesRegex(CompilerError, "verification"):
            self.compiler.compile(self.snapshot, request)


if __name__ == "__main__":
    unittest.main()
