#!/usr/bin/env python3
"""Check whether a court-auction document bundle is complete enough to review.

This is an intake gate. It never makes a rights-effect or bidding decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


REQUIRED = {
    "case_summary": "사건·물건내역",
    "sale_specification": "매각물건명세서",
    "status_report": "현황조사서",
    "appraisal": "감정평가서",
    "registry": "최신 등기사항전부증명서",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        documents = manifest["documents"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"gate error: cannot read intake manifest: {exc}", file=sys.stderr)
        return 2

    types = {item["document_type"] for item in documents}
    missing = [
        {"document_type": kind, "name": label, "severity": "blocking"}
        for kind, label in REQUIRED.items() if kind not in types
    ]
    ocr_needed = [
        {"document_id": item["document_id"], "file_name": item["file_name"], "reason": "; ".join(item.get("quality_notes", []))}
        for item in documents if item["extraction_status"] != "complete"
    ]
    result = {
        "schema_version": "auction-bundle-gate-0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "purpose": "document-completeness gate only; no rights conclusion",
        "document_count": len(documents),
        "detected_document_types": sorted(types),
        "missing_required_documents": missing,
        "ocr_or_manual_review_required": ocr_needed,
        "review_status": "ready_for_document_review" if not missing and not ocr_needed else "limited_source_mode",
        "next_action": (
            "문서 페이지별 사실 추출·대조를 시작할 수 있습니다."
            if not missing and not ocr_needed
            else "누락 문서를 보완하고 OCR/원문 대조를 마친 뒤에만 권리효과 검토를 진행합니다."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"bundle-gate: PASS status={result['review_status']} missing={len(missing)} ocr_review={len(ocr_needed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
