#!/usr/bin/env python3
"""Extract review flags from an official sale specification PDF.

Flags identify phrases requiring verification; they are not findings about the
existence, validity, extinction, or assumption of a right.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path


FLAGS = (
    ("collective_sale", "일괄매각·복수 목록", r"일괄매각"),
    ("excluded_or_additional_building", "제시외 건물", r"제시외\s*건물"),
    ("lien_claim", "유치권 신고·주장", r"유치권"),
    ("surviving_registered_right", "비소멸 등기권리 기재란", r"소멸되지\s*아니하는"),
    ("superficies", "법정지상권 관련 기재란", r"설정된\s*것으로\s*보는\s*지상권"),
    ("tenant_or_occupant", "점유·임차인 기재", r"임차인|점유자"),
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def excerpt(text: str, start: int, end: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - 90): min(len(text), end + 180)]).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        import fitz
        with fitz.open(args.pdf) as pdf:
            pages = [page.get_text("text") for page in pdf]
    except (ImportError, OSError, RuntimeError) as exc:
        print(f"sale-spec error: cannot read PDF: {exc}", file=sys.stderr)
        return 2
    if not any(page.strip() for page in pages):
        print("sale-spec error: no native text; complete local OCR and visual confirmation first", file=sys.stderr)
        return 2
    flags = []
    seen: set[tuple[str, int]] = set()
    for page_number, text in enumerate(pages, start=1):
        for code, label, pattern in FLAGS:
            for match in re.finditer(pattern, text):
                key = (code, page_number)
                if key in seen:
                    continue
                seen.add(key)
                flags.append({
                    "flag_id": f"flag{len(flags) + 1:03d}", "code": code, "label": label,
                    "page": page_number, "excerpt": excerpt(text, match.start(), match.end()),
                    "status": "candidate", "required_action": "원문 전체와 관련 등기·현황·조건 자료를 대조하여 사실과 법률효과를 별도로 검토",
                })
    output = {
        "schema_version": "auction-sale-spec-flags-0.1.0",
        "created_at": datetime.now(UTC).isoformat(), "source_sha256": digest(args.pdf),
        "purpose": "phrase-level review flags only; no rights-effect conclusion", "flags": flags,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sale-spec: PASS pages={len(pages)} flags={len(flags)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
