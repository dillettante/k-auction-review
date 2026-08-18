#!/usr/bin/env python3
"""Validate a Korean court-auction case JSON before report rendering.

This tool validates structure and traceability only. It never decides whether a
right is extinguished, assumed, or legally effective.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"root value must be an object: {path}")
    return value


def legal_rule_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {
        match.lower().replace("-", "_")
        for match in re.findall(r"^### (LR-[A-Z0-9-]+)", text, flags=re.MULTILINE)
    }


def case_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"^\| (SC-[A-Z0-9-]+) \|", text, flags=re.MULTILINE))


def legal_gates(path: Path) -> dict[str, dict[str, Any]]:
    value = load_json(path)
    gates = value.get("gates")
    if value.get("schema_version") != "0.1.0" or not isinstance(gates, list):
        raise ValueError(f"unsupported legal gate catalog: {path}")
    output: dict[str, dict[str, Any]] = {}
    for gate in gates:
        if not isinstance(gate, dict) or not isinstance(gate.get("gate_id"), str):
            raise ValueError(f"invalid gate in catalog: {path}")
        if gate["gate_id"] in output:
            raise ValueError(f"duplicate gate_id {gate['gate_id']} in {path}")
        output[gate["gate_id"]] = gate
    return output


def validate_schema(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        return ["missing dependency: install jsonschema to validate the case schema"]

    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance),
        key=lambda error: list(error.path),
    )
    output: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.path) or "<root>"
        output.append(f"schema {location}: {error.message}")
    return output


def validate_references(
    case: dict[str, Any], rules: set[str], cases: set[str], gates: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    document_ids = {item["document_id"] for item in case.get("documents", [])}
    evidence_ids = {item["evidence_id"] for item in case.get("evidence", [])}

    for evidence in case.get("evidence", []):
        if evidence["document_id"] not in document_ids:
            errors.append(
                f"evidence {evidence['evidence_id']}: unknown document_id {evidence['document_id']}"
            )

    for finding in case.get("findings", []):
        finding_id = finding["finding_id"]
        missing_evidence = set(finding["evidence_ids"]) - evidence_ids
        missing_rules = set(finding["legal_rule_ids"]) - rules
        if missing_evidence:
            errors.append(f"finding {finding_id}: unknown evidence IDs {sorted(missing_evidence)}")
        if missing_rules:
            errors.append(f"finding {finding_id}: unknown legal rule IDs {sorted(missing_rules)}")
        if finding["conclusion_status"] == "confirmed" and finding.get("assumptions"):
            errors.append(f"finding {finding_id}: confirmed finding must not contain assumptions")

    def validate_support_item(label: str, item: dict[str, Any]) -> None:
        missing_evidence = set(item.get("evidence_ids", [])) - evidence_ids
        missing_rules = set(item.get("legal_rule_ids", [])) - rules
        if missing_evidence:
            errors.append(f"{label}: unknown evidence IDs {sorted(missing_evidence)}")
        if missing_rules:
            errors.append(f"{label}: unknown legal rule IDs {sorted(missing_rules)}")
        missing_cases = set(item.get("case_ids", [])) - cases
        if missing_cases:
            errors.append(f"{label}: unknown case IDs {sorted(missing_cases)}")

    decision = case.get("decision_support")
    if decision:
        for field in ("positive_signals", "blocking_risks", "special_rights"):
            for index, item in enumerate(decision.get(field, []), start=1):
                validate_support_item(f"decision_support.{field}[{index}]", item)
        for item in decision.get("pre_bid_actions", []):
            validate_support_item(f"pre_bid_action {item['action_id']}", item)

    reviewed_gate_ids: set[str] = set()
    blocking_gate_labels: list[str] = []
    for index, review in enumerate(case.get("legal_gate_reviews", []), start=1):
        label = f"legal_gate_reviews[{index}]"
        gate_id = review["gate_id"]
        if gate_id in reviewed_gate_ids:
            errors.append(f"{label}: duplicate gate_id {gate_id}")
            continue
        reviewed_gate_ids.add(gate_id)
        gate = gates.get(gate_id)
        if not gate:
            errors.append(f"{label}: unknown gate_id {gate_id}")
            continue
        validate_support_item(label, review)
        declared_rules = set(gate.get("legal_rule_ids", []))
        review_rules = set(review.get("legal_rule_ids", []))
        if not review_rules & declared_rules:
            errors.append(f"{label}: must cite at least one rule assigned to {gate_id}")
        required_facts = set(gate.get("required_fact_ids", []))
        confirmed_facts = set(review.get("confirmed_fact_ids", []))
        missing_facts = set(review.get("missing_fact_ids", []))
        unknown_facts = (confirmed_facts | missing_facts) - required_facts
        if unknown_facts:
            errors.append(f"{label}: unknown fact IDs for {gate_id}: {sorted(unknown_facts)}")
        overlap = confirmed_facts & missing_facts
        if overlap:
            errors.append(f"{label}: facts cannot be both confirmed and missing: {sorted(overlap)}")
        status = review["status"]
        if status == "facts_incomplete" and not missing_facts:
            errors.append(f"{label}: facts_incomplete requires missing_fact_ids")
        if status in {"facts_incomplete", "expert_review_required"} and not review.get("next_action"):
            errors.append(f"{label}: {status} requires next_action")
        if status == "record_ready_for_review":
            if missing_facts:
                errors.append(f"{label}: record_ready_for_review cannot retain missing facts")
            missing_required = required_facts - confirmed_facts
            if missing_required:
                errors.append(f"{label}: record_ready_for_review lacks required facts: {sorted(missing_required)}")
            if not review.get("evidence_ids"):
                errors.append(f"{label}: record_ready_for_review requires evidence")

        if gate.get("blocks_preliminary_bid") and status != "not_triggered":
            blocking_gate_labels.append(str(gate.get("label") or gate_id))

    if blocking_gate_labels:
        decision_status = (case.get("decision_support") or {}).get("decision_status")
        if decision_status == "conditional_candidate":
            errors.append(
                "decision_support: conditional_candidate is not allowed while unresolved blocking gates exist: "
                + ", ".join(blocking_gate_labels)
            )
        brief_verdict = (case.get("buyer_brief") or {}).get("verdict")
        if brief_verdict == "preliminary_bid_candidate":
            errors.append(
                "buyer_brief: preliminary_bid_candidate is not allowed while unresolved blocking gates exist: "
                + ", ".join(blocking_gate_labels)
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("--schema", type=Path, default=Path("case.schema.json"))
    parser.add_argument(
        "--rule-register",
        type=Path,
        default=Path("research/legal/LEGAL_RULE_REGISTER.md"),
    )
    parser.add_argument(
        "--case-register",
        type=Path,
        default=Path("research/legal/CASE_REGISTER.md"),
    )
    parser.add_argument(
        "--gate-catalog",
        type=Path,
        default=Path("research/legal/LEGAL_GATE_CATALOG.json"),
    )
    args = parser.parse_args()

    try:
        case = load_json(args.case_json)
        schema = load_json(args.schema)
        rules = legal_rule_ids(args.rule_register)
        cases = case_ids(args.case_register)
        gates = legal_gates(args.gate_catalog)
    except (OSError, ValueError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2

    errors = validate_schema(case, schema) + validate_references(case, rules, cases, gates)
    if errors:
        print("validation: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "validation: PASS "
        f"documents={len(case['documents'])} evidence={len(case['evidence'])} "
        f"findings={len(case['findings'])} rules={len(rules)} cases={len(cases)} gates={len(gates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
