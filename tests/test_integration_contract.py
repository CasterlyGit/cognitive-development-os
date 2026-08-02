from dataclasses import replace
import json
from pathlib import Path
import unittest

from cognitive_os.integration_contract import (
    KrishCapabilities,
    KrishHandoffProposal,
    assess_live_readiness,
    compute_idempotency_key,
    validate_draft_proposal,
)


ROOT = Path(__file__).parents[1]
PROPOSAL_PATH = ROOT / "examples" / "fixtures" / "layer6_krish_handoff_proposal.json"
CAPABILITIES_PATH = ROOT / "examples" / "fixtures" / "layer6_krish_capabilities.json"


def proposal():
    return KrishHandoffProposal.from_dict(
        json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    )


class KrishIntegrationProposalTests(unittest.TestCase):
    def test_synthetic_draft_matches_contract_invariants(self):
        self.assertEqual((), validate_draft_proposal(proposal()))

    def test_payload_change_invalidates_idempotency_key(self):
        changed = replace(proposal(), outcome="Changed synthetic outcome.")
        self.assertNotEqual(changed.idempotency_key, compute_idempotency_key(changed))
        self.assertIn(
            "idempotency key does not match canonical effect payload",
            validate_draft_proposal(changed),
        )

    def test_unknown_major_version_fails_closed(self):
        changed = replace(proposal(), contract_version="2.0")
        self.assertIn("unsupported contract major version", validate_draft_proposal(changed))

    def test_draft_cannot_smuggle_live_action_or_receipt(self):
        changed = replace(
            proposal(),
            action="queue_executor",
            permission_class="P3_external_change",
            approval_receipt_id="receipt_not_authorized",
        )
        issues = validate_draft_proposal(changed)
        self.assertIn("draft contract cannot request a live action", issues)
        self.assertIn("draft proposal must remain P1_draft_only", issues)
        self.assertIn("draft proposal must not carry a live approval receipt", issues)

    def test_auto_merge_policy_is_rejected(self):
        changed = replace(proposal(), required_merge_policy="automatic")
        self.assertIn(
            "required merge policy must be human_only",
            validate_draft_proposal(changed),
        )

    def test_unsafe_scope_is_rejected(self):
        for path in ("/tmp/escape", "../escape", "Sources/*.swift"):
            with self.subTest(path=path):
                changed = replace(proposal(), owned_paths=(path,))
                self.assertTrue(
                    any("unsafe owned path" in issue for issue in validate_draft_proposal(changed))
                )

    def test_json_schema_required_fields_cover_fixture(self):
        schema = json.loads(
            (ROOT / "contracts" / "krish-handoff-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        fixture = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), set(fixture))
        self.assertFalse(schema["additionalProperties"])

    def test_current_capabilities_keep_live_integration_blocked(self):
        capabilities = KrishCapabilities.from_dict(
            json.loads(CAPABILITIES_PATH.read_text(encoding="utf-8"))
        )
        readiness = assess_live_readiness(proposal(), capabilities)
        self.assertTrue(readiness.contract_valid)
        self.assertFalse(readiness.live_enabled)
        self.assertGreaterEqual(len(readiness.blockers), 6)
        self.assertTrue(any("human_only" in item for item in readiness.blockers))

    def test_even_ideal_claimed_capabilities_do_not_enable_an_adapter(self):
        capabilities = KrishCapabilities(
            accepted_contract_major=1,
            merge_policy="human_only",
            issue_creation_separate_from_queueing=True,
            supports_idempotency=True,
            supports_state_reconciliation=True,
            os_merge_capability_exposed=False,
            human_authorized_live_integration=True,
        )
        readiness = assess_live_readiness(proposal(), capabilities)
        self.assertFalse(readiness.live_enabled)
        self.assertEqual(("this repository contains no live Krish adapter",), readiness.blockers)


if __name__ == "__main__":
    unittest.main()
