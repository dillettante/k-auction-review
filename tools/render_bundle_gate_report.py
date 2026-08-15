#!/usr/bin/env python3
"""Render a shareable HTML report for an auction-document completeness gate."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--flags", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mask", action="store_true", help="omit source excerpts and filenames")
    args = parser.parse_args()
    try:
        manifest, gate = load(args.manifest), load(args.gate)
        flags = load(args.flags).get("flags", []) if args.flags else []
        if gate.get("schema_version") != "auction-bundle-gate-0.1.0":
            raise ValueError("unsupported gate schema")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"bundle-report error: {exc}", file=sys.stderr)
        return 2
    document_rows = "".join(
        f"<tr><td>{esc(item['document_type'])}</td><td>{esc('문서 비공개' if args.mask else item['file_name'])}</td>"
        f"<td>{esc(item['page_count'])}</td><td>{esc(item['extraction_status'])}</td></tr>"
        for item in manifest.get("documents", [])
    )
    missing = "".join(f"<li><strong>{esc(item['name'])}</strong> — {esc(item['severity'])}</li>" for item in gate.get("missing_required_documents", [])) or "<li>필수 문서 누락 없음</li>"
    flag_cards = "".join(
        f"<section class=\"card\"><h3>{esc(item['label'])}</h3><p class=\"status\">후보 경보 · p.{esc(item['page'])}</p>"
        + ("" if args.mask else f"<p>{esc(item['excerpt'])}</p>")
        + f"<p class=\"fine\">{esc(item['required_action'])}</p></section>" for item in flags
    ) or "<p>특수 문구 경보가 없습니다.</p>"
    status = gate.get("review_status")
    verdict = "현재는 입찰 보류" if status == "limited_source_mode" else "문서 검토 시작 가능"
    report = f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>경매 문서 입력 게이트</title><style>:root{{--ink:#172033;--line:#d8dee8;--bg:#f5f7fb;--hold:#9d2436}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}main{{max-width:1040px;margin:auto;padding:32px 20px 72px}}header,.card,table,.notice{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px}}header{{background:#16243b;color:#fff}}h1,h2,h3{{line-height:1.25}}h2{{margin-top:34px}}.notice{{border-left:6px solid var(--hold);background:#fff3f4}}.verdict{{font-size:24px;font-weight:800;color:var(--hold)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}table{{width:100%;border-collapse:collapse;padding:0}}th,td{{text-align:left;padding:11px;border-bottom:1px solid var(--line)}}th{{background:#edf2f8}}.status{{color:#a95b00;font-weight:700}}.fine{{color:#637083}}@media print{{body{{background:#fff}}main{{max-width:none;padding:0}}}}</style></head><body><main><header><h1>경매 문서 입력 게이트</h1><p>제공 자료에 국한된 참고용 점검입니다. 권리효과·입찰 적정성의 결론이 아닙니다.</p></header><h2>현재 판단</h2><section class=\"notice\"><p class=\"verdict\">{esc(verdict)}</p><p>{esc(gate['next_action'])}</p></section><h2>필수 문서 누락</h2><ul>{missing}</ul><h2>제출 문서</h2><table><thead><tr><th>유형</th><th>문서</th><th>쪽수</th><th>추출 상태</th></tr></thead><tbody>{document_rows}</tbody></table><h2>특수 검토 문구</h2><p class=\"fine\">문구 탐지는 권리의 존재·성립·인수 또는 소멸을 뜻하지 않습니다.</p><div class=\"grid\">{flag_cards}</div></main></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"bundle-report: PASS status={status} flags={len(flags)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
