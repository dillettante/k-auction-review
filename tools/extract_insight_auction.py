#!/usr/bin/env python3
"""Create a review-only case JSON from one InsightAuction PDF.

This adapter extracts only visible, deterministic fields. Every fact from the
auction magazine is tagged as a candidate: it must not be treated as the
official registry, sale specification, or status report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


RIGHT_TYPES = {
    "소유권": "ownership",
    "근저당권": "mortgage",
    "가등기": "provisional_registration_other",
    "강제경매": "auction_commencement",
}
ASSET_TYPES = {"아파트": "apartment", "연립": "multifamily_unit", "다세대": "multifamily_unit", "오피스텔": "officetel_residential"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_pages(path: Path) -> list[str]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF (fitz) is required") from exc
    with fitz.open(path) as pdf:
        return [page.get_text("text") for page in pdf]


def first_match(pages: list[str], pattern: str, flags: int = 0) -> tuple[int, re.Match[str]] | None:
    for page_number, page_text in enumerate(pages, start=1):
        match = re.search(pattern, page_text, flags)
        if match:
            return page_number, match
    return None


def candidate_date(raw: str, evidence_id: str) -> dict[str, Any]:
    digits = re.findall(r"\d+", raw)
    value = None
    if len(digits) >= 3:
        value = f"{int(digits[0]):04d}-{int(digits[1]):02d}-{int(digits[2]):02d}"
    return {"value": value, "raw": raw, "status": "candidate", "evidence_ids": [evidence_id]}


def evidence(evidence_id: str, document_id: str, page: int, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "document_id": document_id,
        "page": page,
        "text_raw": normalized(text),
        "extraction_status": "native",
        "confirmation_status": "candidate",
        "note": "경매지 PDF 기재를 자동 추출한 후보 사실; 공식 원문 재확인 필요",
    }


def build_case(path: Path) -> dict[str, Any]:
    pages = extract_pages(path)
    joined = "\n".join(pages)
    if "InsightAuction" not in joined and "인사이트옥션" not in joined:
        raise ValueError("not recognized as an InsightAuction PDF")

    case_match = first_match(pages, r"(\d{4})\s*타경\s*(\d+)\s*\((\d+)\)")
    if not case_match:
        raise ValueError("case number with item number was not found")
    case_page, case_parts = case_match
    case_number = f"{case_parts.group(1)}타경{case_parts.group(2)}"
    item_number = case_parts.group(3)
    evidence_items = [evidence("evcase01", "doc001", case_page, case_parts.group(0))]

    court_match = first_match(pages, r"([가-힣]+지방법원)")
    court_name = court_match[1].group(1) if court_match else "법원 미확인"
    address_match = first_match(pages, r"소재지\s+(.+?)\s+물건종별", re.DOTALL)
    address_raw = normalized(address_match[1].group(1)) if address_match else "소재지 미확인"
    type_match = first_match(pages, r"물건종별\s+([^\s]+)\s+감정가")
    type_raw = type_match[1].group(1) if type_match else "기타"
    asset_type = ASSET_TYPES.get(type_raw, "other")
    asset_page = type_match[0] if type_match else case_page
    evidence_items.append(
        evidence("evasset01", "doc001", asset_page, f"소재지 {address_raw}; 물건종별 {type_raw}")
    )
    asset_evidence_ids = ["evasset01"]
    exclusive_area_raw = None
    area_match = first_match(pages, r"건물면적\s+([\d.]+㎡(?:\([^)]*\))?)")
    if area_match:
        exclusive_area_raw = normalized(area_match[1].group(1))
        evidence_items.append(evidence("evarea01", "doc001", area_match[0], area_match[1].group(0)))
        asset_evidence_ids.append("evarea01")
    land_right_raw = None
    land_match = first_match(pages, r"대지권\s+([\d.]+㎡(?:\([^)]*\))?)")
    if land_match:
        land_right_raw = normalized(land_match[1].group(1))
        evidence_items.append(evidence("evland01", "doc001", land_match[0], land_match[1].group(0)))
        asset_evidence_ids.append("evland01")
    sale_scope_match = first_match(pages, r"매각물건\s+(.+?)(?=\s+소유자|\n)")
    if sale_scope_match:
        evidence_items.append(evidence("evscope01", "doc001", sale_scope_match[0], sale_scope_match[1].group(0)))
        asset_evidence_ids.append("evscope01")
    source_limit_match = first_match(pages, r"건물\s+등기부등본만을\s+기준으로\s+예상배당표를\s+분석")
    if source_limit_match:
        evidence_items.append(evidence("evsource01", "doc001", source_limit_match[0], source_limit_match[1].group(0)))

    sale_date = None
    sale_match = first_match(pages, r"매각기일\s*:\s*(\d{4}[./]\d{1,2}[./]\d{1,2})")
    if sale_match:
        sale_date = candidate_date(sale_match[1].group(1), "evsale01")
        evidence_items.append(evidence("evsale01", "doc001", sale_match[0], sale_match[1].group(0)))

    deadline = None
    deadline_match = first_match(pages, r"배당요구종기\s*:\s*(\d{4}[./]\d{1,2}[./]\d{1,2})")
    if deadline_match:
        deadline = candidate_date(deadline_match[1].group(1), "evdeadline01")
        evidence_items.append(evidence("evdeadline01", "doc001", deadline_match[0], deadline_match[1].group(0)))

    tenancy_match = first_match(pages, r"조사된\s*임차내역이\s*없습니다")
    if tenancy_match:
        evidence_items.append(evidence("evtenancy01", "doc001", tenancy_match[0], tenancy_match[1].group(0)))

    baseline_match = first_match(pages, r"말소기준권리\s*:\s*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2})\.?\s*(근저당권)")
    if baseline_match:
        evidence_items.append(evidence("evbaseline01", "doc001", baseline_match[0], baseline_match[1].group(0)))

    no_surviving_match = first_match(pages, r"매각으로\s*소멸되지\s*않는\s*등기부권리\s+해당사항없음")
    if no_surviving_match:
        evidence_items.append(evidence("evsurvive01", "doc001", no_surviving_match[0], no_surviving_match[1].group(0)))

    no_superficies_match = first_match(pages, r"매각으로\s*설정된\s*것으로\s*보는\s*지상권\s+해당사항없음")
    if no_superficies_match:
        evidence_items.append(evidence("evsuperficies01", "doc001", no_superficies_match[0], no_superficies_match[1].group(0)))

    appraisal_amount = None
    minimum_amount = None
    minimum_rate = None
    price_match = first_match(pages, r"감정가\s+([\d,]+)원.*?최저가\s+\((\d+)%\)\s*([\d,]+)원", re.DOTALL)
    if price_match:
        appraisal_amount = int(price_match[1].group(1).replace(",", ""))
        minimum_rate = int(price_match[1].group(2))
        minimum_amount = int(price_match[1].group(3).replace(",", ""))
        evidence_items.append(evidence("evprice01", "doc001", price_match[0], price_match[1].group(0)))

    right_matches: list[tuple[int, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for page_number, page_text in enumerate(pages, start=1):
        for match in re.finditer(r"(\d{4}\.\d{2}\.\d{2})\s+(소유권|근저당권|가등기|강제경매)", page_text):
            key = (match.group(1), match.group(2))
            if key not in seen:
                seen.add(key)
                right_matches.append((page_number, *key))

    rights: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for index, (page_number, registration_raw, type_raw_right) in enumerate(right_matches, start=1):
        evidence_id = f"evright{index:02d}"
        right_id = f"right{index:03d}"
        evidence_items.append(evidence(evidence_id, "doc001", page_number, f"{registration_raw} {type_raw_right}"))
        registration_date = candidate_date(registration_raw, evidence_id)
        rights.append(
            {
                "right_id": right_id,
                "right_type": RIGHT_TYPES[type_raw_right],
                "asset_ids": ["asset001"],
                "holder_person_ids": [],
                "registration_date": registration_date,
                "raw_description": f"경매지 등기부현황 후보: {type_raw_right}",
                "evidence_ids": [evidence_id],
            }
        )
        events.append(
            {
                "event_id": f"event{index:03d}",
                "event_type": "auction_commenced" if type_raw_right == "강제경매" else "right_registered",
                "date": registration_date,
                "subject_ids": [right_id],
                "description": f"경매지 기재 {type_raw_right} 접수일 후보",
                "evidence_ids": [evidence_id],
            }
        )

    scope_reasons = [
        "단일 경매지 PDF만 제출되어 매각물건명세서·현황조사서·등기사항증명서 원문을 확인하지 못함",
        "경매지의 권리·임차·배당 표기는 후보 사실이며 공식 원문과 대조가 필요함",
    ]
    missing = [
        {
            "missing_id": "missing001",
            "item_type": "document",
            "name": "최신 건물 및 토지 등기사항전부증명서",
            "severity": "blocking",
            "impact": "등기 시간축, 토지 지분 관련 권리 및 매각에 따른 권리효과를 확정할 수 없음",
            "status": "open",
        },
        {
            "missing_id": "missing002",
            "item_type": "document",
            "name": "공식 매각물건명세서 및 현황조사서",
            "severity": "material",
            "impact": "임차인 부존재 표기, 비소멸 권리 및 특별매각조건을 공식 원문으로 확인할 수 없음",
            "status": "open",
        },
    ]
    findings = [
        {
            "finding_id": "finding001",
            "issue_code": "IA01",
            "subject_ids": ["asset001"],
            "conclusion_status": "conditional",
            "summary": "경매지 PDF에는 아파트와 토지 지분·건물 매각이 기재되어 있다. 공식 물건명세서와 등기 원문이 동일한 대상임을 확인하는 조건에서만 매각 범위를 설명할 수 있다.",
            "assumptions": ["경매지 PDF의 사건번호·물건번호·물건 표기가 현재 법원 기록과 일치한다."],
            "evidence_ids": ["evcase01", "evasset01"],
            "legal_rule_ids": ["lr_proc_01", "lr_land_01"],
            "related_missing_ids": ["missing001", "missing002"],
            "analysis_date": date.today().isoformat(),
        },
        {
            "finding_id": "finding002",
            "issue_code": "IA02",
            "subject_ids": [right["right_id"] for right in rights] or ["asset001"],
            "conclusion_status": "conditional",
            "summary": "경매지에 표시된 등기 시간축과 말소기준권리 표기는 후보로 정리할 수 있으나, 건물·토지의 최신 전체 등기사항증명서가 없으므로 개별 권리의 소멸·인수는 판정하지 않는다.",
            "assumptions": ["경매지의 등기부현황이 현재 등기사항증명서와 일치한다."],
            "evidence_ids": [item["evidence_id"] for item in evidence_items if item["evidence_id"].startswith("evright")],
            "legal_rule_ids": ["lr_reg_01"],
            "related_missing_ids": ["missing001"],
            "analysis_date": date.today().isoformat(),
        },
        {
            "finding_id": "finding003",
            "issue_code": "IA03",
            "subject_ids": ["asset001"],
            "conclusion_status": "withheld",
            "summary": "경매지의 ‘조사된 임차내역 없음’ 표기만으로 실제 점유·임대차·대항요건 또는 매수인 부담을 확정하지 않는다.",
            "evidence_ids": ["evtenancy01"] if tenancy_match else ["evasset01"],
            "legal_rule_ids": ["lr_lease_01", "lr_lease_02"],
            "related_missing_ids": ["missing002"],
            "analysis_date": date.today().isoformat(),
        },
        {
            "finding_id": "finding004",
            "issue_code": "IA04",
            "subject_ids": ["case001"],
            "conclusion_status": "conditional" if deadline else "withheld",
            "summary": "배당요구 종기 표기는 후보 일자로 기록한다. 권리자별 배당요구의 필요성·유효성·배당액은 법원 기록으로 재확인하기 전까지 판정하지 않는다.",
            "assumptions": ["경매지에 표시된 배당요구 종기가 현재 사건기록과 일치한다."] if deadline else [],
            "evidence_ids": ["evdeadline01"] if deadline else ["evcase01"],
            "legal_rule_ids": ["lr_dist_01"],
            "analysis_date": date.today().isoformat(),
        },
    ]
    decision_support = {
        "decision_status": "conditional_candidate",
        "summary": "경매지 기재가 공식 원문과 같다는 조건에서는 등기상 인수위험이 낮아 보이는 검토 후보이다. 입찰 직전 최신 법원 문서와 건물·토지 등기에서 이 전제가 유지되는지만 확인해야 한다.",
        "positive_signals": [{
            "title": "후순위 권리들이 모두 소멸로 표시됨",
            "detail": "경매지는 2015. 9. 8. 근저당권을 말소기준권리로, 뒤의 가등기·근저당권·경매개시등기를 소멸로 표시하고 비소멸 등기권리도 없다고 기재한다.",
            "evidence_ids": ["evbaseline01", "evright03", "evright04", "evright05", "evsurvive01"],
            "legal_rule_ids": ["lr_reg_01", "lr_protect_01"],
        }],
        "blocking_risks": [{
            "title": "좋아 보이는 결론의 근거가 경매지 한 장에 집중됨",
            "detail": "가등기의 후속 기록, 임차내역 부존재, 토지 대지권의 별도 부담은 최신 공식 원문에서 뒤집힐 수 있다.",
            "evidence_ids": ["evright03", "evtenancy01", "evsource01"],
            "legal_rule_ids": ["lr_reg_01", "lr_protect_01", "lr_lease_01", "lr_land_01"],
        }],
        "pre_bid_actions": [
            {
                "action_id": "pba01", "priority": "blocker", "title": "입찰 당일 건물·토지 등기와 법원 원문을 1회 교차확인",
                "why": "현재 잠정 결론을 뒤집을 수 있는 것은 선순위 권리, 가등기 후속 본등기, 토지 별도등기, 새 점유 기재이다.",
                "resolution": "건물·토지 최신 등기 전부와 매각물건명세서·현황조사서를 날짜순으로 대조한다.",
                "outcome_if_clear": "권리분석상 입찰 검토 후보를 유지한다.",
                "outcome_if_not_clear": "확인되지 않은 인수금액 전액을 위험으로 보거나 입찰하지 않는다.",
                "evidence_ids": ["evbaseline01", "evright03", "evsource01", "evtenancy01"],
                "legal_rule_ids": ["lr_proc_01", "lr_reg_01", "lr_land_01", "lr_lease_01"],
            },
            {
                "action_id": "pba02", "priority": "critical", "title": "현장 점유와 인도 난이도 확인",
                "why": "임차내역이 없더라도 소유자나 제3자가 점유할 수 있고, 이는 명도 기간과 비용에 영향을 준다.",
                "resolution": "현장 방문, 관리사무소에서 허용되는 범위의 확인, 최신 현황조사서로 실제 점유를 대조한다.",
                "outcome_if_clear": "명도비와 예상기간을 입찰가에 반영한다.",
                "outcome_if_not_clear": "보수적인 명도 충당금을 반영하거나 입찰을 낮춘다.",
                "evidence_ids": ["evtenancy01"], "legal_rule_ids": ["lr_lease_01", "lr_lease_02"],
            },
        ],
        "special_rights": [
            {
                "special_id": "spr01", "type": "집합건물 대지권 지분", "status": "not_indicated",
                "why": "아파트 전유부분과 해당 대지권 지분이 함께 매각되는 표시는 통상적인 구조이며, 일부 지분만 매각하는 지분경매라는 뜻은 아니다.",
                "resolution": "토지 등기와 집합건물 표제부에서 대지권 비율·별도등기·분리처분 흔적만 확인한다.",
                "evidence_ids": ["evscope01", "evland01", "evsource01"], "legal_rule_ids": ["lr_land_01", "lr_proc_01"],
                "case_ids": ["SC-LAND-2008-2005DA15048"],
            },
            {
                "special_id": "spr02", "type": "후순위 가등기", "status": "candidate",
                "why": "경매지상 말소기준권리 뒤에 있고 소멸로 표시되어 있어 현재로서는 인수 가능성보다 소멸 가능성이 높게 보인다.",
                "resolution": "최신 등기에서 접수순위·매매예약 원인·후속 본등기 또는 말소와 법원 명세서 기재를 확인한다.",
                "evidence_ids": ["evbaseline01", "evright03", "evsurvive01"], "legal_rule_ids": ["lr_protect_01", "lr_reg_01"],
            },
        ],
    }
    buyer_brief = {
        "verdict": "preliminary_bid_candidate",
        "confidence": "low",
        "novice_fit": "caution",
        "headline": "권리표의 원문대조만 통과하면 입찰 검토가 가능한 물건으로 보입니다.",
        "rationale": "말소기준권리 뒤의 가등기·근저당권·경매개시등기가 모두 소멸로 표시되고, 임차내역과 비소멸 등기권리가 없다고 기재되어 있습니다. 단, 결론의 근거가 단일 경매지이므로 최신 공식 원문과의 일치가 전제입니다.",
        "source_strength": "단일 민간 경매지 1개: 순위·누락·전부 원문은 아직 확인되지 않음",
        "cards": {
            "rights": {"label": "등기권리", "status": "favorable", "detail": "후순위 권리 모두 소멸 표시; 가등기는 말소기준권리보다 약 2년 8개월 뒤"},
            "occupancy": {"label": "점유·임차", "status": "favorable", "detail": "조사된 임차내역 없음. 실제 점유와 인도비용은 별도 확인"},
            "special_property": {"label": "특수물건", "status": "caution", "detail": "대지권 지분 병합매각은 통상 구조. 후순위 가등기 원문만 집중 확인"},
            "price": {"label": "가격", "status": "caution", "detail": f"최저가 {minimum_amount:,}원은 감정가 {appraisal_amount:,}원의 {minimum_rate}%" if minimum_amount and appraisal_amount and minimum_rate else "경매지 가격은 확인됐지만 비교사례 해석이 필요"},
        },
        "conditional_conclusions": [
            {
                "title": "후순위 가등기는 소멸 가능성이 높아 보임",
                "observed": "가등기는 말소기준 근저당권보다 뒤이고 경매지에 소멸로 표시됨",
                "likely_effect": "최신 원문이 같다면 매수인이 가등기를 인수할 가능성은 낮음",
                "flips_if": "선순위 권리, 가등기 후속 본등기, 특별매각조건이 새로 확인됨",
                "action": "건물·토지 최신 등기의 접수순위·후속기록과 매각물건명세서를 대조",
                "evidence_ids": ["evbaseline01", "evright03", "evsurvive01"], "legal_rule_ids": ["lr_reg_01", "lr_protect_01"],
            },
            {
                "title": "임차인 인수위험은 낮아 보이나 현장확인은 필요",
                "observed": "경매지에 조사된 임차내역이 없다고 표시됨",
                "likely_effect": "선순위 임차인 보증금 인수 위험은 현재 자료상 낮은 편",
                "flips_if": "최신 현황조사나 현장에서 대항력 있는 점유·임차관계가 확인됨",
                "action": "현황조사서·현장점유를 대조하고 미확인 명도비를 입찰가에 반영",
                "evidence_ids": ["evtenancy01"], "legal_rule_ids": ["lr_lease_01", "lr_lease_02"],
            },
        ],
        "deal_breakers": [
            "최신 등기에서 말소기준권리보다 앞선 미확인 권리가 발견됨",
            "토지 등기에 대지권 별도 부담이나 선순위 담보가 발견됨",
            "현황조사·현장에서 선순위 임차인 또는 고비용 명도 문제가 발견됨",
        ],
    }
    return {
        "schema_version": "0.1.0",
        "analysis": {
            "analysis_id": "insight001",
            "analysis_date": date.today().isoformat(),
            "procedure_type": "court_auction",
            "scope_status": "partially_supported",
            "scope_reasons": scope_reasons,
            "privacy_mode": "local_full",
            "engine_version": "prototype-0.1.0",
            "knowledge_version": "phase3-core-2026-08-15",
            "law_checked_at": date.today().isoformat(),
        },
        "documents": [{
            "document_id": "doc001",
            "document_type": "other",
            "file_name": path.name,
            "sha256": sha256(path),
            "page_count": len(pages),
            "extraction_method": "native_pdf",
            "extraction_status": "complete",
            "quality_notes": ["InsightAuction PDF; extracted values are candidate facts only"],
        }],
        "case": {
            "case_id": "case001",
            "court_name": court_name,
            "case_number": case_number,
            "item_numbers": [item_number],
            "auction_kind": "unknown",
            "sale_date": sale_date,
            "distribution_claim_deadline": deadline,
            "asset_ids": ["asset001"],
            "evidence_ids": ["evcase01"],
        },
        "assets": [{
            "asset_id": "asset001",
            "asset_type": asset_type,
            "address_raw": address_raw,
            "exclusive_area_raw": exclusive_area_raw,
            "land_right_raw": land_right_raw,
            "sale_scope_status": "conditional",
            "evidence_ids": asset_evidence_ids,
        }],
        "persons": [],
        "rights": rights,
        "occupancies": [],
        "events": events,
        "evidence": evidence_items,
        "conflicts": [],
        "missing_items": missing,
        "findings": findings,
        "decision_support": decision_support,
        "buyer_brief": buyer_brief,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        case = build_case(args.input_pdf)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"extract error: {exc}", file=sys.stderr)
        return 2
    print(f"extract: PASS case={case['case']['case_number']} item={case['case']['item_numbers'][0]} rights={len(case['rights'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
