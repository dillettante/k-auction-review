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


def validate_references(case: dict[str, Any], rules: set[str], cases: set[str]) -> list[str]:
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
    args = parser.parse_args()

    try:
        case = load_json(args.case_json)
        schema = load_json(args.schema)
        rules = legal_rule_ids(args.rule_register)
        cases = case_ids(args.case_register)
    except (OSError, ValueError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2

    errors = validate_schema(case, schema) + validate_references(case, rules, cases)
    if errors:
        print("validation: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "validation: PASS "
        f"documents={len(case['documents'])} evidence={len(case['evidence'])} "
        f"findings={len(case['findings'])} rules={len(rules)} cases={len(cases)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
