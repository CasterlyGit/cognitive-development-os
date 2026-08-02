"""Validate the offline proposal and prove live integration stays disabled."""

import json
from pathlib import Path

from cognitive_os.integration_contract import (
    KrishCapabilities,
    KrishHandoffProposal,
    assess_live_readiness,
    validate_draft_proposal,
)


def main() -> None:
    fixture_dir = Path(__file__).parent / "fixtures"
    proposal = KrishHandoffProposal.from_dict(
        json.loads(
            (fixture_dir / "layer6_krish_handoff_proposal.json").read_text(
                encoding="utf-8"
            )
        )
    )
    capabilities = KrishCapabilities.from_dict(
        json.loads(
            (fixture_dir / "layer6_krish_capabilities.json").read_text(
                encoding="utf-8"
            )
        )
    )
    readiness = assess_live_readiness(proposal, capabilities)
    print(
        json.dumps(
            {
                "draft_contract_issues": list(validate_draft_proposal(proposal)),
                "readiness": readiness.to_dict(),
                "krish_accessed": False,
                "external_effects": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
