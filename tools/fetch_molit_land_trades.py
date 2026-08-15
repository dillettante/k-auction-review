#!/usr/bin/env python3
"""Fetch land transaction data from the MOLIT public API.

Use this only as a comparable-data input for separately sold land, land-right
separation, or other land-specific review. A condominium's ordinary land share
is already embodied in unit transactions and must not be added to unit prices.
The service key is read only from ``AUCTION_RTMS_API_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ENDPOINT = "https://apis.data.go.kr/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade"
ITEM_FIELDS = (
    "dealAmount", "dealYear", "dealMonth", "dealDay", "jibun", "landArea", "landUse",
    "landType", "umdCd", "umdNm", "zonage", "cdealType", "cdealDay", "dealingGbn",
    "estateAgentSggNm", "rgstDate",
)


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def trade(item: ET.Element) -> dict[str, Any]:
    raw = {field: clean(item.findtext(field)) for field in ITEM_FIELDS}
    amount_raw = raw.get("dealAmount")
    amount_krw = int(amount_raw.replace(",", "")) * 10_000 if amount_raw else None
    try:
        land_area_sqm = float(raw["landArea"]) if raw.get("landArea") else None
    except ValueError:
        land_area_sqm = None
    contract_date = None
    if all(raw.get(key) for key in ("dealYear", "dealMonth", "dealDay")):
        contract_date = f"{int(raw['dealYear']):04d}-{int(raw['dealMonth']):02d}-{int(raw['dealDay']):02d}"
    return {
        "contract_date": contract_date,
        "amount_krw": amount_krw,
        "land_area_sqm": land_area_sqm,
        "amount_per_sqm_krw": round(amount_krw / land_area_sqm) if amount_krw and land_area_sqm else None,
        "legal_dong": raw.get("umdNm"),
        "legal_dong_code": raw.get("umdCd"),
        "jibun": raw.get("jibun"),
        "land_type": raw.get("landType"),
        "land_use": raw.get("landUse"),
        "zoning": raw.get("zonage"),
        "cancellation_type": raw.get("cdealType"),
        "cancellation_date": raw.get("cdealDay"),
        "transaction_type": raw.get("dealingGbn"),
        "registration_date": raw.get("rgstDate"),
        "source_raw": raw,
    }


def fetch_month(api_key: str, lawd_cd: str, month: str, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not (lawd_cd.isdigit() and len(lawd_cd) == 5):
        raise ValueError("--lawd-cd must be a five-digit legal-district code")
    if not (month.isdigit() and len(month) == 6):
        raise ValueError("--month must be YYYYMM")
    query = urllib.parse.urlencode({
        "serviceKey": urllib.parse.unquote(api_key), "LAWD_CD": lawd_cd, "DEAL_YMD": month,
        "numOfRows": "1000", "pageNo": "1",
    })
    request = urllib.request.Request(f"{ENDPOINT}?{query}", headers={"User-Agent": "auction-rights-analysis/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body, status = response.read(), response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").replace("\n", " ")[:500]
        raise RuntimeError(f"MOLIT API HTTP {exc.code}: {detail or exc.reason}") from exc
    root = ET.fromstring(body)
    code, message = clean(root.findtext(".//resultCode")), clean(root.findtext(".//resultMsg"))
    if code not in {None, "00", "000"}:
        raise RuntimeError(f"MOLIT API error {code}: {message or 'unknown error'}")
    return [trade(item) for item in root.findall(".//item")], {"http_status": status, "result_code": code, "result_message": message}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lawd-cd", required=True)
    parser.add_argument("--month", required=True, action="append")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    api_key = os.environ.get("AUCTION_RTMS_API_KEY")
    if not api_key:
        print("fetch error: set AUCTION_RTMS_API_KEY in the execution environment", file=sys.stderr)
        return 2
    rows: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    try:
        for month in args.month:
            items, metadata = fetch_month(api_key, args.lawd_cd, month, args.timeout)
            rows.extend(items)
            responses.append({"month": month, **metadata, "count": len(items)})
    except (OSError, ValueError, ET.ParseError, RuntimeError) as exc:
        print(f"fetch error: {exc}", file=sys.stderr)
        return 1
    output = {
        "schema_version": "molit-land-trades-0.1.0",
        "source": {
            "provider": "MOLIT / data.go.kr", "dataset": "국토교통부_토지 매매 실거래가 자료",
            "endpoint": ENDPOINT, "retrieved_at": datetime.now(UTC).isoformat(), "lawd_cd": args.lawd_cd,
            "months": args.month, "responses": responses,
            "use_limit": "Do not add these values to ordinary condominium-unit comparables; use only after a land-specific sale scope is confirmed.",
        },
        "transactions": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fetch: PASS months={len(args.month)} transactions={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
