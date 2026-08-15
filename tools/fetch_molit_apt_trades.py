#!/usr/bin/env python3
"""Fetch Korean apartment transaction data from the MOLIT public API.

The service key is deliberately read only from ``AUCTION_RTMS_API_KEY``.
Never place keys in a case JSON, report, command-line argument, or repository.
The output records provenance and API response metadata, but never the key.
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


ENDPOINT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
ITEM_FIELDS = (
    "aptNm", "aptDong", "aptSeq", "buildYear", "dealAmount", "dealDay", "dealMonth",
    "dealYear", "excluUseAr", "floor", "jibun", "landLeaseholdGbn", "roadNm", "umdCd",
    "umdNm", "cdealType", "cdealDay", "dealingGbn", "rgstDate",
)


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def transaction(item: ET.Element) -> dict[str, Any]:
    raw = {field: clean(item.findtext(field)) for field in ITEM_FIELDS}
    amount_raw = raw.get("dealAmount")
    amount_krw = int(amount_raw.replace(",", "")) * 10_000 if amount_raw else None
    try:
        area_sqm = float(raw["excluUseAr"]) if raw.get("excluUseAr") else None
    except ValueError:
        area_sqm = None
    try:
        floor = int(raw["floor"]) if raw.get("floor") else None
    except ValueError:
        floor = None
    contract_date = None
    if all(raw.get(key) for key in ("dealYear", "dealMonth", "dealDay")):
        contract_date = f"{int(raw['dealYear']):04d}-{int(raw['dealMonth']):02d}-{int(raw['dealDay']):02d}"
    return {
        "complex_name": raw.get("aptNm"),
        "complex_id": raw.get("aptSeq"),
        "contract_date": contract_date,
        "amount_krw": amount_krw,
        "exclusive_area_sqm": area_sqm,
        "floor": floor,
        "legal_dong": raw.get("umdNm"),
        "legal_dong_code": raw.get("umdCd"),
        "road_name": raw.get("roadNm"),
        "jibun": raw.get("jibun"),
        "building_year": raw.get("buildYear"),
        "cancellation_type": raw.get("cdealType"),
        "cancellation_date": raw.get("cdealDay"),
        "transaction_type": raw.get("dealingGbn"),
        "registration_date": raw.get("rgstDate"),
        "land_leasehold": raw.get("landLeaseholdGbn"),
        "source_raw": raw,
    }


def fetch_month(api_key: str, lawd_cd: str, month: str, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not (lawd_cd.isdigit() and len(lawd_cd) == 5):
        raise ValueError("--lawd-cd must be a five-digit legal-district code")
    if not (month.isdigit() and len(month) == 6):
        raise ValueError("--month must be YYYYMM")
    query = urllib.parse.urlencode({
        "serviceKey": urllib.parse.unquote(api_key),
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": month,
        "numOfRows": "1000",
        "pageNo": "1",
    })
    request = urllib.request.Request(f"{ENDPOINT}?{query}", headers={"User-Agent": "auction-rights-analysis/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        # The endpoint sometimes returns an XML explanation only on an HTTP error.
        # Do not include the request URL: it contains the service key.
        detail = exc.read().decode("utf-8", errors="replace").replace("\n", " ")[:500]
        raise RuntimeError(f"MOLIT API HTTP {exc.code}: {detail or exc.reason}") from exc
    root = ET.fromstring(body)
    result_code = clean(root.findtext(".//resultCode"))
    result_message = clean(root.findtext(".//resultMsg"))
    # The approved general endpoint returns ``000`` while some portal examples
    # show ``00``. Both mean success.
    if result_code not in {None, "00", "000"}:
        raise RuntimeError(f"MOLIT API error {result_code}: {result_message or 'unknown error'}")
    items = [transaction(item) for item in root.findall(".//item")]
    return items, {"http_status": status, "result_code": result_code, "result_message": result_message}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lawd-cd", required=True, help="five-digit legal-district code, e.g. 11215")
    parser.add_argument("--month", required=True, action="append", help="YYYYMM; repeat for multiple months")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    api_key = os.environ.get("AUCTION_RTMS_API_KEY")
    if not api_key:
        print("fetch error: set AUCTION_RTMS_API_KEY in the execution environment", file=sys.stderr)
        return 2

    all_items: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    try:
        for month in args.month:
            items, metadata = fetch_month(api_key, args.lawd_cd, month, args.timeout)
            all_items.extend(items)
            responses.append({"month": month, **metadata, "count": len(items)})
    except (OSError, ValueError, ET.ParseError, RuntimeError) as exc:
        print(f"fetch error: {exc}", file=sys.stderr)
        return 1

    output = {
        "schema_version": "molit-apt-trades-0.1.0",
        "source": {
            "provider": "MOLIT / data.go.kr",
            "dataset": "국토교통부_아파트 매매 실거래가 자료",
            "endpoint": ENDPOINT,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "lawd_cd": args.lawd_cd,
            "months": args.month,
            "responses": responses,
        },
        "transactions": all_items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fetch: PASS months={len(args.month)} transactions={len(all_items)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
