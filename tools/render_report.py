#!/usr/bin/env python3
"""Render a self-contained, evidence-linked HTML report from a validated case JSON."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


STATUS = {"confirmed": "확인", "conditional": "조건부", "withheld": "판단유보"}
DECISION_STATUS = {
    "do_not_bid_yet": "현재는 입찰 보류",
    "conditional_candidate": "조건 충족 시 검토 가능",
    "not_assessable": "입찰 판단 불가",
}
BUYER_VERDICT = {
    "preliminary_bid_candidate": "권리상 잠정 입찰 후보",
    "expert_review_required": "전문 검토 후에만 접근",
    "avoid": "현재 조건에서는 회피",
}
CONFIDENCE = {"low": "낮음", "medium": "보통", "high": "높음"}
NOVICE_FIT = {"suitable": "초보자도 검토 가능", "caution": "초보자는 주의", "unsuitable": "초보자 부적합"}
RIGHT_NAMES = {
    "ownership": "소유권",
    "mortgage": "근저당권",
    "provisional_registration_other": "가등기",
    "auction_commencement": "경매개시등기",
}
SPECIAL_STATUS = {"not_indicated": "해당 징후 없음", "candidate": "확인 필요", "confirmed": "확인", "unknown": "미확인"}
PRIORITY_NAMES = {"blocker": "입찰 전 필수", "critical": "중요", "important": "확인 권장"}
SEVERITY_NAMES = {"blocking": "필수", "material": "중요", "informational": "참고"}
DOCUMENT_NAMES = {
    "registry": "등기사항증명서",
    "sale_specification": "매각물건명세서",
    "status_report": "현황조사서",
    "appraisal": "감정평가서",
    "case_summary": "법원 사건내역",
    "schedule": "법원 기일내역",
    "other": "제공자료",
}
RULE_NAMES = {
    "lr_proc_01": "법원 문서와 매각절차",
    "lr_reg_01": "매각 후 등기권리",
    "lr_lease_01": "임차인의 대항력",
    "lr_lease_02": "임차인의 우선변제",
    "lr_dist_01": "배당요구",
    "lr_land_01": "대지권과 토지등기",
    "lr_lien_01": "유치권",
    "lr_superficies_01": "법정지상권",
    "lr_protect_01": "가등기·가처분",
}
ISSUE_NAMES = {
    "IA01": "목적물·매각 범위",
    "IA02": "등기 시간축·기준등기 후보",
    "IA03": "점유·주택 임대차",
    "IA04": "배당요구와 절차 기한",
    "IA05": "명세서·현황조사서·감정의 불일치",
    "IA06": "선순위·보전등기 등기권리",
    "IA07": "대지권·토지 별도등기",
    "IA08": "유치권 주장",
    "IA09": "법정·관습법상 지상권",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def as_text(value: dict[str, Any] | None) -> str:
    if not value:
        return "미확인"
    return esc(value.get("raw") or value.get("value") or "미확인")


def masked_people(case: dict[str, Any], mask: bool) -> dict[str, str]:
    people: dict[str, str] = {}
    for index, person in enumerate(case["persons"], start=1):
        if mask and person["privacy_status"] != "synthetic":
            people[person["person_id"]] = f"당사자 {index}"
        else:
            people[person["person_id"]] = person["display_name"]
    return people


def redact_evidence_text(value: str, case: dict[str, Any], mask: bool) -> str:
    """Mask known direct identifiers in evidence excerpts for shareable HTML."""
    if not mask:
        return esc(value)
    redacted = value
    for asset in case.get("assets", []):
        address = asset.get("address_raw")
        if address and address != "소재지 미확인":
            redacted = redacted.replace(address, "[주소 비공개]")
    for person in case.get("persons", []):
        if person.get("privacy_status") != "synthetic" and person.get("display_name"):
            redacted = redacted.replace(person["display_name"], "[당사자 비공개]")
    return esc(redacted)


def evidence_link(evidence_id: str, evidence_numbers: dict[str, int]) -> str:
    return f'<a href="#ev-{esc(evidence_id)}">근거 {evidence_numbers[evidence_id]}</a>'


def document_name(document: dict[str, Any]) -> str:
    if document["document_type"] == "other" and "인사이트옥션" in document.get("file_name", ""):
        return "인사이트옥션 경매지"
    return DOCUMENT_NAMES.get(document["document_type"], "제공자료")


def case_links(path: Path) -> dict[str, str]:
    """Read official-case links from the public research register, if present."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"^\| (SC-[A-Z0-9-]+) \| \[[^]]+\]\((https://[^)]+)\)", text, re.MULTILINE)
    }


def won(value: int | float | None) -> str:
    return f"{int(value):,}원" if value is not None else "미확인"


def ref_links(item: dict[str, Any], known_case_links: dict[str, str]) -> str:
    rule_names = [esc(RULE_NAMES.get(rule, "관련 법률")) for rule in item.get("legal_rule_ids", [])]
    parts = ["관련 법률: " + ", ".join(rule_names)] if rule_names else []
    for index, case_id in enumerate(item.get("case_ids", []), start=1):
        url = known_case_links.get(case_id)
        label = f"관련 대법원 판례 {index}"
        parts.append(f'<a href="{esc(url)}">{label}</a>' if url else label)
    return " · ".join(parts) or "근거 미기재"


def extract_auction_prices(evidence: dict[str, dict[str, Any]]) -> tuple[int | None, int | None]:
    text = " ".join(str(item.get("text_raw", "")) for item in evidence.values())
    appraisal_match = re.search(r"감정(?:평가액|가)\s*[:：]?\s*([\d,]+)\s*원?", text)
    minimum_match = re.search(r"최저(?:매각가격|가)\s*[:：]?\s*(?:\(\d+%\))?\s*([\d,]+)\s*원?", text)

    def amount(match: re.Match[str] | None) -> int | None:
        return int(match.group(1).replace(",", "")) if match else None

    return amount(appraisal_match), amount(minimum_match)


def render(case: dict[str, Any], mask: bool, market: dict[str, Any] | None, known_case_links: dict[str, str]) -> str:
    analysis = case["analysis"]
    case_info = case["case"]
    people = masked_people(case, mask)
    asset = case["assets"][0]
    address = "주소 비공개" if mask and analysis["privacy_mode"] != "synthetic" else asset["address_raw"]
    documents = {item["document_id"]: item for item in case["documents"]}
    evidence = {item["evidence_id"]: item for item in case["evidence"]}
    evidence_numbers = {item["evidence_id"]: index for index, item in enumerate(case["evidence"], start=1)}

    finding_cards: list[str] = []
    for finding in case["findings"]:
        status = finding["conclusion_status"]
        sources = " · ".join(evidence_link(item, evidence_numbers) for item in finding["evidence_ids"])
        rules = ", ".join(esc(RULE_NAMES.get(item, "관련 법률")) for item in finding["legal_rule_ids"])
        finding_cards.append(
            "<section class=\"card\">"
            f"<h3>{esc(ISSUE_NAMES.get(finding['issue_code'], finding['issue_code']))}</h3>"
            f"<p class=\"status {esc(status)}\">{STATUS[status]}</p>"
            f"<p>{esc(finding['summary'].replace('MVP', '자동분석'))}</p>"
            f"<p class=\"fine\">증거 {sources}<br>규칙 {rules}</p>"
            "</section>"
        )

    timeline: list[tuple[str, str, list[str]]] = []
    for event in case["events"]:
        date = event["date"].get("value") or "미확인"
        timeline.append((date, event.get("description", event["event_type"]), event["evidence_ids"]))
    timeline.sort(key=lambda item: item[0])
    timeline_rows = "".join(
        f"<tr><th>{esc(date)}</th><td>{esc(description)} · "
        f"{' · '.join(evidence_link(item, evidence_numbers) for item in evidence_ids)}</td></tr>"
        for date, description, evidence_ids in timeline
    )

    missing = [item for item in case["missing_items"] if item["status"] == "open"]
    missing_html = "".join(
        f"<li><strong>{esc(SEVERITY_NAMES.get(item['severity'], item['severity']))}</strong> — {esc(item.get('name') or item['item_type'])}: "
        f"{esc(item['impact'].replace('MVP', '자동분석'))}</li>"
        for item in missing
    ) or "<li>열린 누락 항목이 없습니다.</li>"

    conflicts = "".join(
        f"<tr><th>{esc(item['field_path'])}</th><td>{esc(item.get('description', ''))}<br>"
        f"상태: <strong>{esc(item['status'])}</strong> · "
        f"{' · '.join(evidence_link(eid, evidence_numbers) for eid in item['evidence_ids'])}</td></tr>"
        for item in case["conflicts"]
    ) or "<tr><td colspan=\"2\">기록된 문서 상충이 없습니다.</td></tr>"

    right_rows = "".join(
        f"<tr><td>{esc(RIGHT_NAMES.get(right['right_type'], right['right_type']))}</td><td>{esc(as_text(right['registration_date']))}</td>"
        f"<td>{', '.join(esc(people.get(pid, pid)) for pid in right['holder_person_ids'])}</td>"
        f"<td>{esc(right.get('raw_description', ''))}</td>"
        f"<td>{' · '.join(evidence_link(eid, evidence_numbers) for eid in right['evidence_ids'])}</td></tr>"
        for right in case["rights"]
    )

    evidence_rows = []
    for item in case["evidence"]:
        doc = documents[item["document_id"]]
        evidence_rows.append(
            f'<article id="ev-{esc(item["evidence_id"])}" class="evidence-item"><h3>근거 {evidence_numbers[item["evidence_id"]]} · '
            f'{esc(document_name(doc))} {esc(item["page"])}쪽</h3>'
            f'<p>{redact_evidence_text(item["text_raw"], case, mask)}</p></article>'
        )
    source_file_rows = "".join(
        f"<li>{esc(document_name(document))} — {esc(document['file_name'])}</li>"
        for document in case["documents"]
    )

    questions = [question for finding in case["findings"] for question in finding.get("follow_up_questions", [])]
    question_html = "".join(f"<li>{esc(question)}</li>" for question in questions) or "<li>추가 질문이 없습니다.</li>"
    brief = case.get("buyer_brief")
    buyer_html = ""
    if brief:
        card_titles = {"rights": "등기권리", "occupancy": "점유·임차", "special_property": "특수물건", "price": "가격"}
        brief_cards = "".join(
            f'<section class="brief-card {esc(item["status"])}"><p class="eyebrow">{esc(card_titles[key])}</p>'
            f'<h3>{esc(item["label"])}</h3><p>{esc(item["detail"])}</p></section>'
            for key, item in brief["cards"].items()
        )
        conclusion_rows = "".join(
            f'<section class="conclusion"><h3>{esc(item["title"])}</h3>'
            f'<p><strong>확인된 단서</strong> {esc(item["observed"])}</p>'
            f'<p><strong>가장 가능성 높은 효과</strong> {esc(item["likely_effect"])}</p>'
            f'<p><strong>결론이 뒤집히는 경우</strong> {esc(item["flips_if"])}</p>'
            f'<p><strong>입찰 전 행동</strong> {esc(item["action"])}</p>'
            f'<details class="legal"><summary>근거와 법률 보기</summary><p class="fine">{" · ".join(evidence_link(eid, evidence_numbers) for eid in item["evidence_ids"])}<br>{ref_links(item, known_case_links)}</p></details></section>'
            for item in brief["conditional_conclusions"]
        )
        breakers = "".join(f"<li>{esc(item)}</li>" for item in brief["deal_breakers"])
        buyer_html = (
            '<section class="verdict"><div><p class="eyebrow">입찰자에게 드리는 잠정 답변</p>'
            f'<p class="verdict-label">{esc(BUYER_VERDICT[brief["verdict"]])}</p><h2>{esc(brief["headline"])}</h2>'
            f'<p>{esc(brief["rationale"])}</p></div><div class="verdict-meta">'
            f'<span>판단 신뢰도 <strong>{esc(CONFIDENCE[brief["confidence"]])}</strong></span>'
            f'<span>난이도 <strong>{esc(NOVICE_FIT[brief["novice_fit"]])}</strong></span>'
            f'<span>자료 수준 <strong>{esc(brief["source_strength"])}</strong></span></div></section>'
            f'<div class="brief-grid">{brief_cards}</div>'
            f'<h2>현재 자료로 어디까지 말할 수 있나</h2><div class="conclusions">{conclusion_rows}</div>'
            f'<section class="breaker"><h2>하나라도 나오면 결론을 폐기할 조건</h2><ul>{breakers}</ul></section>'
        )
    scope_warning = ""
    if analysis["scope_status"] != "supported":
        scope_warning = (
            '<details class="scope"><summary>자동분석 범위와 자료 한계</summary><p>아래 사유 때문에 잠정 결론의 신뢰도가 제한됩니다.</p><ul>'
            + "".join(f"<li>{esc(reason.replace('MVP', '자동분석'))}</li>" for reason in analysis.get("scope_reasons", []))
            + "</ul></details>"
        )
    primary_document_types = {"sale_specification", "status_report", "registry"}
    has_primary_document = any(document["document_type"] in primary_document_types for document in case["documents"])
    limited_source_warning = ""
    if not has_primary_document:
        limited_source_warning = (
            '<p class="source-line"><strong>제한자료 분석:</strong> 경매지·요약자료만으로 최대한 추론했습니다. '
            '최종 입찰 전 최신 법원 문서와 등기를 직접 대조하면 위 잠정 결론을 검증할 수 있습니다.</p>'
        )
    general_warning = (
        '<p class="warning-line"><strong>주의:</strong> 제공받은 자료에 국한된 참고 분석입니다. 입찰 전 최신 법원 원문·등기·현장을 직접 확인하십시오.</p>'
    )
    decision = case.get("decision_support")
    decision_html = ""
    if decision:
        signals = "".join(
            "<section class=\"card\"><h3>확인 출발점 — " + esc(item["title"]) + "</h3>"
            + f"<p>{esc(item['detail'])}</p><p class=\"fine\">{' · '.join(evidence_link(eid, evidence_numbers) for eid in item['evidence_ids'])}<br>{ref_links(item, known_case_links)}</p></section>"
            for item in decision["positive_signals"]
        ) or "<p class=\"fine\">현재 자료에서 확정된 긍정 신호는 없습니다.</p>"
        risks = "".join(
            "<section class=\"card risk\"><h3>해소 전 위험 — " + esc(item["title"]) + "</h3>"
            + f"<p>{esc(item['detail'])}</p><p class=\"fine\">{' · '.join(evidence_link(eid, evidence_numbers) for eid in item['evidence_ids'])}<br>{ref_links(item, known_case_links)}</p></section>"
            for item in decision["blocking_risks"]
        ) or "<p class=\"fine\">기록된 차단 위험이 없습니다.</p>"
        action_rows = "".join(
            "<tr><th>" + esc(PRIORITY_NAMES.get(item["priority"], item["priority"])) + "<br>" + esc(item["title"]) + "</th>"
            + f"<td><strong>왜:</strong> {esc(item['why'])}<br><strong>해소 방법:</strong> {esc(item['resolution'])}<br>"
            + f"<strong>확인되면:</strong> {esc(item['outcome_if_clear'])}<br><strong>확인 안 되면:</strong> {esc(item['outcome_if_not_clear'])}<br>"
            + f"<span class=\"fine\">{' · '.join(evidence_link(eid, evidence_numbers) for eid in item['evidence_ids'])}<br>{ref_links(item, known_case_links)}</span></td></tr>"
            for item in decision["pre_bid_actions"]
        )
        special_cards = "".join(
            "<section class=\"card\"><h3>" + esc(item["type"]) + " <span class=\"status " + esc(item["status"]) + "\">" + esc(SPECIAL_STATUS.get(item["status"], item["status"])) + "</span></h3>"
            + f"<p>{esc(item['why'])}</p><p><strong>해소:</strong> {esc(item['resolution'])}</p>"
            + f"<p class=\"fine\">{' · '.join(evidence_link(eid, evidence_numbers) for eid in item['evidence_ids'])}<br>{ref_links(item, known_case_links)}</p></section>"
            for item in decision["special_rights"]
        )
        decision_body = (
            "<section class=\"decision\"><p class=\"decision-status\">"
            + esc(DECISION_STATUS[decision["decision_status"]]) + "</p><p>" + esc(decision["summary"]) + "</p></section>"
            + "<h2>입찰 전 해소해야 할 일</h2><table><tbody>" + action_rows + "</tbody></table>"
            + "<h2>특수 권리·점유 검토</h2><div class=\"grid\">" + special_cards + "</div>"
            + "<h2>확인 출발점과 차단 위험</h2><div class=\"grid\">" + signals + risks + "</div>"
        )
        decision_html = (
            '<details class="deep-review"><summary>전문 검토 상세와 입찰 전 체크리스트</summary>' + decision_body + "</details>"
            if brief else "<h2>입찰 판단</h2>" + decision_body
        )
    market_html = ""
    if market:
        selection = market.get("selection", {})
        summary = market.get("summary", {})
        target = market.get("target", {})
        comparable_rows = "".join(
            f"<tr><td>{esc(item.get('complex_name') or '미확인')}</td><td>{esc(item.get('contract_date') or '미확인')}</td>"
            f"<td>{esc(item.get('exclusive_area_sqm') or '미확인')}㎡</td><td>{esc(item.get('floor') or '미확인')}</td>"
            f"<td>{won(item.get('amount_krw'))}</td><td>{won(item.get('amount_per_sqm_krw'))}/㎡</td></tr>"
            for item in market.get("comparables", [])
        ) or "<tr><td colspan=\"6\">조건에 맞는 비교 거래가 없습니다.</td></tr>"
        warning = selection.get("warning") or "동일 단지·유사 면적 비교군입니다."
        appraisal_price, minimum_price = extract_auction_prices(evidence)
        interpretation = ""
        median_price = summary.get("median_krw")
        market_minimum = summary.get("minimum_krw")
        if minimum_price and appraisal_price:
            interpretation += f"최저가는 감정가보다 {(1 - minimum_price / appraisal_price) * 100:.1f}% 낮습니다. "
        if minimum_price and median_price:
            interpretation += f"약한 비교군 중앙값보다 {(1 - minimum_price / median_price) * 100:.1f}% 낮습니다. "
        if minimum_price and market_minimum:
            relation = (minimum_price / market_minimum - 1) * 100
            interpretation += f"다만 비교군 최저 거래보다 {abs(relation):.1f}% {'높습니다' if relation >= 0 else '낮습니다'}."
        market_html = (
            "<h2>가격 판단 — 국토교통부 실거래가</h2><section class=\"market-summary\"><strong>현재 가격이 싸 보이는가?</strong>"
            + f"<p>{esc(warning)}</p><p>대상 면적 {esc(target.get('exclusive_area_sqm'))}㎡ · 비교 거래 {esc(summary.get('count'))}건 · "
            + f"거래가 중앙값 {won(summary.get('median_krw'))} · 범위 {won(summary.get('minimum_krw'))}–{won(summary.get('maximum_krw'))} · "
            + f"㎡당 중앙값 {won(summary.get('median_per_sqm_krw'))}</p>"
            + f"<p><strong>해석:</strong> {esc(interpretation or '대상 최저가와 비교군을 연결할 가격정보가 부족합니다.')}</p>"
            + "<p>동일 단지 확정 사례가 아니므로 가격 방향만 보여 줍니다. 최종 상한가는 명도·수리·세금·금융비용을 뺀 뒤 계산해야 합니다.</p></section>"
            + "<table><thead><tr><th>단지</th><th>계약일</th><th>전용면적</th><th>층</th><th>거래가</th><th>㎡당</th></tr></thead><tbody>" + comparable_rows + "</tbody></table>"
        )

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>권리분석 보고서 — {esc(case_info['case_number'])}</title>
<style>
:root{{--ink:#172033;--muted:#637083;--line:#d8dee8;--bg:#f5f7fb;--card:#fff;--good:#0e7a55;--warn:#a95b00;--hold:#9d2436}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}main{{max-width:1040px;margin:auto;padding:32px 20px 72px}}header{{border-radius:18px;padding:30px;background:#16243b;color:#fff}}h1,h2,h3{{line-height:1.25}}h1{{margin:0 0 8px;font-size:28px}}h2{{margin:34px 0 14px;font-size:20px}}h3{{margin:0 0 6px;font-size:16px}}.sub,.fine{{color:var(--muted)}}header .sub,header .fine{{color:#d5dceb}}.meta{{margin-top:18px;display:flex;flex-wrap:wrap;gap:8px}}.chip{{border:1px solid #426084;border-radius:999px;padding:3px 10px;font-size:13px;background:#233653;color:#e9effa}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}.card,details,.decision{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}.risk{{border-left:4px solid var(--hold)}}.decision{{border-left:6px solid var(--hold);background:#fff3f4}}.decision-status{{margin:0 0 8px;color:var(--hold);font-size:23px;font-weight:800}}.status{{font-weight:700}}.confirmed{{color:var(--good)}}.conditional{{color:var(--warn)}}.withheld{{color:var(--hold)}}.candidate,.unknown{{color:var(--warn)}}.not_indicated{{color:var(--hold)}}table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}}th,td{{text-align:left;vertical-align:top;padding:11px;border-bottom:1px solid var(--line)}}th{{background:#edf2f8}}.notice{{border-left:4px solid var(--hold);padding:14px 16px;background:#fff3f4;border-radius:6px;margin-top:16px}}.general-warning{{border-left-color:#a95b00;background:#fff8e8}}.source-warning{{border-left-color:#9d2436;background:#fff3f4}}a{{color:#125faa}}details{{margin:8px 0}}summary{{cursor:pointer;font-weight:650}}code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em}}@media print{{body{{background:#fff;font-size:11px}}main{{max-width:none;padding:0}}header{{color:#000;background:#fff;border:1px solid #777}}.card,table,details{{break-inside:avoid}}a{{color:#000;text-decoration:none}}}}
.warning-line,.source-line{{margin:12px 0 0;padding:10px 14px;border-radius:9px;background:#fff8e8;border:1px solid #ead7a9}}.source-line{{background:#fff3f4;border-color:#efc5cc}}.verdict{{display:grid;grid-template-columns:1.6fr 1fr;gap:24px;margin-top:18px;padding:26px;border-radius:18px;background:#fff;border:1px solid var(--line);border-top:6px solid #176b55}}.verdict h2{{margin:8px 0 10px;font-size:25px}}.verdict-label{{display:inline-block;margin:4px 0;padding:5px 11px;border-radius:999px;background:#e5f5ef;color:#075a42;font-weight:800}}.verdict-meta{{display:flex;flex-direction:column;gap:9px;padding:15px;border-radius:12px;background:#f3f6f9}}.verdict-meta span{{display:flex;flex-direction:column}}.eyebrow{{margin:0 0 6px;color:var(--muted);font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}}.brief-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}}.brief-card{{padding:16px;border-radius:13px;background:#fff;border:1px solid var(--line);border-top:4px solid var(--warn)}}.brief-card.favorable{{border-top-color:var(--good)}}.brief-card.high_risk{{border-top-color:var(--hold)}}.brief-card.unknown{{border-top-color:var(--muted)}}.brief-card p:last-child{{margin-bottom:0}}.conclusions{{display:grid;gap:12px}}.conclusion{{padding:18px 20px;border-radius:14px;background:#fff;border:1px solid var(--line)}}.conclusion p{{margin:7px 0}}.conclusion strong{{display:inline-block;min-width:145px}}.legal{{padding:0;border:0;background:transparent}}.legal summary{{font-size:13px;color:#125faa}}.breaker{{margin-top:22px;padding:4px 20px 14px;border-radius:14px;background:#fff3f4;border-left:5px solid var(--hold)}}.breaker h2{{margin-top:18px}}.scope,.deep-review{{margin-top:16px}}.deep-review>summary{{font-size:17px}}.market-summary{{padding:18px;border-radius:14px;background:#edf7f4;border-left:5px solid var(--good)}}@media(max-width:760px){{.verdict{{grid-template-columns:1fr}}.brief-grid{{grid-template-columns:1fr 1fr}}.conclusion strong{{display:block;min-width:0}}}}@media(max-width:480px){{.brief-grid{{grid-template-columns:1fr}}}}
.evidence-panel{{margin-top:28px}}.evidence-panel>summary{{font-size:17px}}.evidence-list{{display:grid;gap:10px;margin-top:14px}}.evidence-item{{padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:#f8fafc;scroll-margin-top:16px}}.evidence-item:target{{border-color:#277b65;background:#eef8f4}}.evidence-item h3{{margin:0 0 5px}}.evidence-item p{{margin:4px 0}}
</style></head><body><main>
<header><h1>권리분석 보고서</h1><p class="sub">{esc(case_info['court_name'])} {esc(case_info['case_number'])} · 물건 {esc(', '.join(case_info['item_numbers']))} · {esc(address)}</p><div class="meta"><span class="chip">분석일 {esc(analysis['analysis_date'])}</span><span class="chip">매각기일 {as_text(case_info.get('sale_date'))}</span><span class="chip">배당요구종기 {as_text(case_info.get('distribution_claim_deadline'))}</span><span class="chip">법률 확인일 {esc(analysis.get('law_checked_at') or '미기재')}</span></div></header>
{buyer_html}
{general_warning}
{limited_source_warning}
{market_html}
{scope_warning}
{decision_html}
<details class="deep-review"><summary>전체 쟁점별 분석</summary><div class="grid">{''.join(finding_cards)}</div></details>
<h2>자료 완전성 및 확인 질문</h2><div class="notice"><strong>열린 누락·확인사항</strong><ul>{missing_html}</ul></div><ul>{question_html}</ul>
<h2>권리 시간축</h2><table><tbody>{timeline_rows}</tbody></table>
<h2>등기 권리표</h2><table><thead><tr><th>권리</th><th>접수일</th><th>권리자</th><th>원문 설명</th><th>증거</th></tr></thead><tbody>{right_rows}</tbody></table>
<h2>문서 상충</h2><table><tbody>{conflicts}</tbody></table>
<details class="evidence-panel"><summary>근거 원문 {len(evidence_rows)}개 보기</summary><details class="source-files"><summary>사용한 원본 파일 {len(case['documents'])}개</summary><ul>{source_file_rows}</ul></details><div class="evidence-list">{''.join(evidence_rows)}</div></details>
<h2>한계</h2><p class="fine">이 보고서는 제공된 문서와 확인된 사실을 연결하는 검토 보조물입니다. 자료가 부족하거나 상충하는 경우 판단유보를 유지합니다. 투자 판단·입찰 권고·개별 사건 법률의견이 아닙니다.</p>
</main><script>function openEvidence(){{const target=document.querySelector(location.hash);if(!target)return;for(const parent of target.closest('details')?[target.closest('details')]:[])parent.open=true;}}window.addEventListener('hashchange',openEvidence);openEvidence();</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("output_html", type=Path)
    parser.add_argument("--mask", action="store_true", help="mask non-synthetic names and the address")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--schema", type=Path, default=Path("case.schema.json"))
    parser.add_argument("--rule-register", type=Path, default=Path("research/legal/LEGAL_RULE_REGISTER.md"))
    parser.add_argument("--case-register", type=Path, default=Path("research/legal/CASE_REGISTER.md"))
    parser.add_argument("--market-comparables", type=Path, help="optional output of build_market_comparables.py")
    args = parser.parse_args()

    if not args.skip_validation:
        command = [sys.executable, str(Path(__file__).with_name("validate_case.py")), str(args.case_json), "--schema", str(args.schema), "--rule-register", str(args.rule_register), "--case-register", str(args.case_register)]
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode

    try:
        case = json.loads(args.case_json.read_text(encoding="utf-8"))
        if not isinstance(case, dict):
            raise ValueError("case JSON root must be an object")
        market = None
        if args.market_comparables:
            market = json.loads(args.market_comparables.read_text(encoding="utf-8"))
            if not isinstance(market, dict) or market.get("schema_version") != "auction-market-comparables-0.1.0":
                raise ValueError("market comparables JSON has an unsupported schema")
        report = render(case, args.mask, market, case_links(args.case_register))
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(report, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"render error: {exc}", file=sys.stderr)
        return 2

    print(f"render: PASS {args.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
