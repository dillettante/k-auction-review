#!/usr/bin/env python3
"""Calculate a transparent reference bid ceiling only after safety gates pass.

This is not an appraisal, investment recommendation, or bid instruction.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def nonnegative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative KRW amount")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--market-comparables", required=True, type=Path)
    parser.add_argument("--acquisition-cost", required=True, type=nonnegative)
    parser.add_argument("--eviction-cost", required=True, type=nonnegative)
    parser.add_argument("--repair-cost", required=True, type=nonnegative)
    parser.add_argument("--finance-and-holding-cost", required=True, type=nonnegative)
    parser.add_argument("--rights-risk-reserve", required=True, type=nonnegative)
    parser.add_argument("--minimum-margin", required=True, type=nonnegative)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        market = json.loads(args.market_comparables.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"bid-ceiling error: cannot read input: {exc}", file=sys.stderr)
        return 2
    decision = case.get("decision_support", {})
    if decision.get("decision_status") != "conditional_candidate":
        print("bid-ceiling blocked: rights review must be conditional_candidate; do not calculate while bidding is on hold", file=sys.stderr)
        return 3
    tier = market.get("selection", {}).get("tier")
    if tier != "same_complex_similar_area":
        print("bid-ceiling blocked: a confirmed same-complex similar-area comparable set is required", file=sys.stderr)
        return 3
    anchor = market.get("summary", {}).get("median_krw")
    if not isinstance(anchor, int) or anchor <= 0:
        print("bid-ceiling blocked: market median is missing", file=sys.stderr)
        return 3
    deductions = {
        "acquisition_cost": args.acquisition_cost, "eviction_cost": args.eviction_cost,
        "repair_cost": args.repair_cost, "finance_and_holding_cost": args.finance_and_holding_cost,
        "rights_risk_reserve": args.rights_risk_reserve, "minimum_margin": args.minimum_margin,
    }
    total = sum(deductions.values())
    ceiling = anchor - total
    if ceiling <= 0:
        print("bid-ceiling blocked: deductions exceed the selected market anchor", file=sys.stderr)
        return 3
    result = {
        "schema_version": "auction-bid-ceiling-0.1.0", "created_at": datetime.now(UTC).isoformat(),
        "purpose": "reference ceiling only; not an appraisal, investment recommendation, or bid instruction",
        "market_anchor": {"type": "same_complex_similar_area_median", "amount_krw": anchor},
        "deductions_krw": deductions, "total_deductions_krw": total, "reference_bid_ceiling_krw": ceiling,
        "assumptions": ["Rights review status remains conditional_candidate at the time of bidding.", "Same-complex comparable data remains current and representative.", "All user-entered costs and reserves are complete."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"bid-ceiling: PASS ceiling={ceiling} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
