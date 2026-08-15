#!/usr/bin/env python3
"""Create a transparent apartment transaction comparable set from MOLIT data.

This tool produces market evidence, not an appraisal or bid recommendation.
It uses a strict hierarchy: same-complex and similar area first; otherwise it
falls back to the same legal dong and labels the result as a weak substitute.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def normalized(value: str | None) -> str:
    return "".join((value or "").lower().split())


def amount_summary(rows: list[dict[str, Any]]) -> dict[str, int | float | None]:
    amounts = sorted(row["amount_krw"] for row in rows)
    per_sqm = sorted(row["amount_per_sqm_krw"] for row in rows if row["amount_per_sqm_krw"] is not None)
    return {
        "count": len(rows),
        "minimum_krw": amounts[0] if amounts else None,
        "median_krw": round(statistics.median(amounts)) if amounts else None,
        "maximum_krw": amounts[-1] if amounts else None,
        "median_per_sqm_krw": round(statistics.median(per_sqm)) if per_sqm else None,
    }


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "complex_name", "complex_id", "contract_date", "amount_krw", "exclusive_area_sqm",
            "amount_per_sqm_krw", "floor", "legal_dong", "jibun", "building_year",
            "transaction_type", "registration_date", "land_leasehold",
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", required=True, type=Path, help="output of fetch_molit_apt_trades.py")
    parser.add_argument("--target-area-sqm", required=True, type=float)
    parser.add_argument("--legal-dong", required=True)
    parser.add_argument("--target-complex", help="exact apartment complex name, when confirmed")
    parser.add_argument("--area-tolerance", type=float, default=0.10, help="relative tolerance; default 10%%")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.target_area_sqm <= 0 or not 0 < args.area_tolerance <= 0.30:
        print("comparable error: target area must be positive and tolerance must be 0–0.30", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.trades.read_text(encoding="utf-8"))
        source_rows = payload["transactions"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"comparable error: cannot read MOLIT trade data: {exc}", file=sys.stderr)
        return 2

    filtered: list[dict[str, Any]] = []
    excluded = {"missing_value": 0, "cancelled": 0, "area_outside_tolerance": 0, "other_dong": 0}
    for row in source_rows:
        if not row.get("amount_krw") or not row.get("exclusive_area_sqm"):
            excluded["missing_value"] += 1
            continue
        if row.get("cancellation_type"):
            excluded["cancelled"] += 1
            continue
        if normalized(row.get("legal_dong")) != normalized(args.legal_dong):
            excluded["other_dong"] += 1
            continue
        if abs(row["exclusive_area_sqm"] - args.target_area_sqm) / args.target_area_sqm > args.area_tolerance:
            excluded["area_outside_tolerance"] += 1
            continue
        row = dict(row)
        row["amount_per_sqm_krw"] = round(row["amount_krw"] / row["exclusive_area_sqm"])
        filtered.append(row)

    exact_complex = []
    if args.target_complex:
        target = normalized(args.target_complex)
        exact_complex = [row for row in filtered if normalized(row.get("complex_name")) == target]
    if exact_complex:
        tier, selected = "same_complex_similar_area", exact_complex
        warning = None
    else:
        tier, selected = "same_legal_dong_similar_area", filtered
        warning = (
            "동일 단지의 확인된 거래가 없거나 단지명이 입력되지 않아 같은 법정동·유사 면적 거래를 사용했습니다. "
            "건물 연식·입지·동·층·관리상태 차이가 크므로 이 결과를 동일 건물 시세로 취급하면 안 됩니다."
        )

    output = {
        "schema_version": "auction-market-comparables-0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "purpose": "market evidence only; not appraisal, investment recommendation, or bid price",
        "source": payload.get("source", {}),
        "target": {
            "exclusive_area_sqm": args.target_area_sqm, "legal_dong": args.legal_dong,
            "target_complex": args.target_complex, "area_tolerance": args.area_tolerance,
        },
        "selection": {"tier": tier, "warning": warning, "exclusions": excluded},
        "summary": amount_summary(selected),
        "comparables": [compact(row) for row in sorted(selected, key=lambda item: item.get("contract_date") or "")],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"comparables: PASS tier={tier} count={len(selected)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
