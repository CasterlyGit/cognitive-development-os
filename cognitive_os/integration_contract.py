from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Dict, Optional, Tuple


class IntegrationContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class KrishHandoffProposal:
    contract_version: str
    handoff_id: str
    idempotency_key: str
    intent_id: str
    plan_id: str
    plan_digest: str
    target_system: str
    target_project: str
    action: str
    outcome: str
    owned_paths: Tuple[str, ...]
    acceptance_criteria: Tuple[str, ...]
    exclusions: Tuple[str, ...]
    evidence_contract: Tuple[str, ...]
    risk: str
    permission_class: str
    approval_receipt_id: Optional[str]
    required_merge_policy: str

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "KrishHandoffProposal":
        try:
            return cls(
                contract_version=value["contract_version"],
                handoff_id=value["handoff_id"],
                idempotency_key=value["idempotency_key"],
                intent_id=value["intent_id"],
                plan_id=value["plan_id"],
                plan_digest=value["plan_digest"],
                target_system=value["target_system"],
                target_project=value["target_project"],
                action=value["action"],
                outcome=value["outcome"],
                owned_paths=tuple(value["owned_paths"]),
                acceptance_criteria=tuple(value["acceptance_criteria"]),
                exclusions=tuple(value["exclusions"]),
                evidence_contract=tuple(value["evidence_contract"]),
                risk=value["risk"],
                permission_class=value["permission_class"],
                approval_receipt_id=value.get("approval_receipt_id"),
                required_merge_policy=value["required_merge_policy"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationContractError("invalid handoff proposal: %s" % exc) from exc

    def effect_payload(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "handoff_id": self.handoff_id,
            "intent_id": self.intent_id,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "target_system": self.target_system,
            "target_project": self.target_project,
            "action": self.action,
            "outcome": self.outcome,
            "owned_paths": list(self.owned_paths),
            "acceptance_criteria": list(self.acceptance_criteria),
            "exclusions": list(self.exclusions),
            "evidence_contract": list(self.evidence_contract),
            "risk": self.risk,
            "permission_class": self.permission_class,
            "approval_receipt_id": self.approval_receipt_id,
            "required_merge_policy": self.required_merge_policy,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"idempotency_key": self.idempotency_key, **self.effect_payload()}


@dataclass(frozen=True)
class KrishCapabilities:
    accepted_contract_major: int
    merge_policy: str
    issue_creation_separate_from_queueing: bool
    supports_idempotency: bool
    supports_state_reconciliation: bool
    os_merge_capability_exposed: bool
    human_authorized_live_integration: bool

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "KrishCapabilities":
        try:
            return cls(
                accepted_contract_major=int(value["accepted_contract_major"]),
                merge_policy=value["merge_policy"],
                issue_creation_separate_from_queueing=bool(
                    value["issue_creation_separate_from_queueing"]
                ),
                supports_idempotency=bool(value["supports_idempotency"]),
                supports_state_reconciliation=bool(
                    value["supports_state_reconciliation"]
                ),
                os_merge_capability_exposed=bool(value["os_merge_capability_exposed"]),
                human_authorized_live_integration=bool(
                    value["human_authorized_live_integration"]
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationContractError("invalid capability snapshot: %s" % exc) from exc


@dataclass(frozen=True)
class IntegrationReadiness:
    contract_valid: bool
    live_enabled: bool
    blockers: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_valid": self.contract_valid,
            "live_enabled": self.live_enabled,
            "blockers": list(self.blockers),
        }


def compute_idempotency_key(proposal: KrishHandoffProposal) -> str:
    encoded = json.dumps(
        proposal.effect_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:%s" % hashlib.sha256(encoded).hexdigest()


def validate_draft_proposal(proposal: KrishHandoffProposal) -> Tuple[str, ...]:
    issues = []
    if proposal.contract_version.split(".", 1)[0] != "1":
        issues.append("unsupported contract major version")
    if proposal.target_system != "krish":
        issues.append("target_system must be krish")
    if proposal.action != "draft_issue_proposal":
        issues.append("draft contract cannot request a live action")
    if proposal.permission_class != "P1_draft_only":
        issues.append("draft proposal must remain P1_draft_only")
    if proposal.approval_receipt_id is not None:
        issues.append("draft proposal must not carry a live approval receipt")
    if proposal.required_merge_policy != "human_only":
        issues.append("required merge policy must be human_only")
    required_text = (
        proposal.handoff_id,
        proposal.intent_id,
        proposal.plan_id,
        proposal.plan_digest,
        proposal.target_project,
        proposal.outcome,
    )
    if any(not value.strip() for value in required_text):
        issues.append("required identifiers and outcome must be non-empty")
    if not proposal.owned_paths:
        issues.append("owned_paths must be explicit")
    for path in proposal.owned_paths:
        parsed = PurePosixPath(path)
        if (
            not path.strip()
            or parsed.is_absolute()
            or ".." in parsed.parts
            or "\\" in path
            or any(character in path for character in "*?[]")
        ):
            issues.append("unsafe owned path: %s" % path)
    if not proposal.acceptance_criteria or not proposal.evidence_contract:
        issues.append("acceptance and evidence contracts are required")
    if proposal.idempotency_key != compute_idempotency_key(proposal):
        issues.append("idempotency key does not match canonical effect payload")
    return tuple(issues)


def assess_live_readiness(
    proposal: KrishHandoffProposal, capabilities: KrishCapabilities
) -> IntegrationReadiness:
    blockers = list(validate_draft_proposal(proposal))
    if capabilities.accepted_contract_major != 1:
        blockers.append("Krish does not accept contract major version 1")
    if capabilities.merge_policy != "human_only":
        blockers.append("Krish merge policy is not mechanically human_only")
    if not capabilities.issue_creation_separate_from_queueing:
        blockers.append("issue creation and executor queueing are not separate")
    if not capabilities.supports_idempotency:
        blockers.append("Krish does not advertise idempotent handoffs")
    if not capabilities.supports_state_reconciliation:
        blockers.append("Krish does not advertise external-state reconciliation")
    if capabilities.os_merge_capability_exposed:
        blockers.append("OS integration identity can access a merge capability")
    if not capabilities.human_authorized_live_integration:
        blockers.append("no new explicit human authorization for live integration")
    blockers.append("this repository contains no live Krish adapter")
    return IntegrationReadiness(
        contract_valid=not validate_draft_proposal(proposal),
        live_enabled=False,
        blockers=tuple(dict.fromkeys(blockers)),
    )
