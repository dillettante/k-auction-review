#!/usr/bin/env python3
"""Build a metadata-only local intake manifest for auction case documents.

The output deliberately contains no extracted page text, absolute paths, or OCR
images. It is an intake gate, not an evidence extractor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable


DOCUMENT_KEYWORDS = (
    ("매각물건명세서", "sale_specification"),
    ("현황조사서", "status_report"),
    ("감정평가", "appraisal"),
    ("등기", "registry"),
    ("전입", "tenant_record"),
    ("건축물대장", "building_register"),
    ("토지대장", "land_register"),
    ("지적도", "cadastral_map"),
    ("신탁원부", "trust_register"),
    ("특별매각", "sale_conditions"),
    ("매각조건", "sale_conditions"),
    ("임대차", "lease_contract"),
    ("유치권", "lien_claim"),
    ("결정", "court_order"),
    ("기일", "schedule"),
    ("사건", "case_summary"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(name: str) -> str:
    return next((kind for keyword, kind in DOCUMENT_KEYWORDS if keyword in name), "other")


def pdf_metadata(path: Path) -> tuple[int, str, str, list[str]]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF (fitz) is required to inspect PDFs") from exc

    notes: list[str] = []
    with fitz.open(path) as pdf:
        page_count = len(pdf)
        text_chars = sum(len(page.get_text("text").strip()) for page in pdf)
    if text_chars == 0:
        notes.append("no native text detected; local OCR review required")
        return page_count, "other_ocr", "not_started", notes
    notes.append("native text detected; text is not retained in this manifest")
    return page_count, "native_pdf", "complete", notes


def document(path: Path, index: int) -> dict[str, Any]:
    suffix = path.suffix.lower()
    item: dict[str, Any] = {
        "document_id": f"doc{index:03d}",
        "document_type": classify(path.name),
        "file_name": path.name,
        "sha256": sha256(path),
    }
    if suffix == ".pdf":
        page_count, method, status, notes = pdf_metadata(path)
        item.update(
            page_count=page_count,
            extraction_method=method,
            extraction_status=status,
            quality_notes=notes,
        )
    elif suffix in {".png", ".jpg", ".jpeg"}:
        item.update(
            page_count=1,
            extraction_method="image_vision",
            extraction_status="not_started",
            quality_notes=["image input; local OCR review required"],
        )
    elif suffix in {".html", ".htm", ".txt"}:
        item.update(
            page_count=1,
            extraction_method="html" if suffix != ".txt" else "manual",
            extraction_status="complete",
            quality_notes=["text content is not retained in this manifest"],
        )
    else:
        item.update(
            page_count=1,
            extraction_method="manual",
            extraction_status="not_started",
            quality_notes=[f"unsupported extension: {suffix or '(none)'}"],
        )
    return item


def files(paths: Iterable[Path], recursive: bool) -> list[Path]:
    collected: list[Path] = []
    for path in paths:
        if path.is_file():
            collected.append(path)
        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            collected.extend(candidate for candidate in iterator if candidate.is_file() and not candidate.name.startswith("."))
        else:
            raise FileNotFoundError(path)
    return sorted(set(collected), key=lambda item: item.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="files or directories to inspect locally")
    parser.add_argument("--output", required=True, type=Path, help="local JSON manifest path")
    parser.add_argument("--recursive", action="store_true", help="include files below input directories")
    args = parser.parse_args()

    try:
        input_files = files(args.inputs, args.recursive)
        if not input_files:
            raise ValueError("no input files found")
        manifest = {
            "manifest_version": "0.1.0",
            "created_at": date.today().isoformat(),
            "privacy_note": "metadata only; no extracted text, image, or absolute path is stored",
            "documents": [document(path, index) for index, path in enumerate(input_files, start=1)],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"intake error: {exc}", file=sys.stderr)
        return 2

    statuses = {item["extraction_status"] for item in manifest["documents"]}
    print(f"intake: PASS documents={len(manifest['documents'])} statuses={','.join(sorted(statuses))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
