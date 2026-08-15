#!/usr/bin/env python3
"""Collect KCI article metadata for the private auction-rights research layer.

The script sends no source documents and never writes the KCI API key to disk.
It saves bibliographic metadata only; abstracts and original PDFs are excluded.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree as ET


ENDPOINT = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"
DISPLAY_COUNT = 100


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str | None:
    for descendant in element.iter():
        if local_name(descendant.tag) == name and descendant.text:
            value = " ".join(descendant.text.split())
            if value:
                return value
    return None


def descendant_texts(element: ET.Element, name: str) -> list[str]:
    values: list[str] = []
    for descendant in element.iter():
        if local_name(descendant.tag) == name and descendant.text:
            value = " ".join(descendant.text.split())
            if value:
                values.append(value)
    return values


def find_records(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if local_name(element.tag) == "record"]


def result_message(root: ET.Element) -> str | None:
    return child_text(root, "resultMsg")


def parse_record(record: ET.Element, query_id: str) -> dict[str, object]:
    article_info = next(
        (element for element in record.iter() if local_name(element.tag) == "articleInfo"),
        record,
    )
    journal_info = next(
        (element for element in record.iter() if local_name(element.tag) == "journalInfo"),
        record,
    )
    title = child_text(article_info, "article-title")
    authors = descendant_texts(article_info, "author")
    article_id = article_info.attrib.get("article-id") or child_text(article_info, "article-id")
    return {
        "kci_article_id": article_id,
        "title": title,
        "authors": authors,
        "journal": child_text(journal_info, "journal-name"),
        "publisher": child_text(journal_info, "publisher-name"),
        "publication_year": child_text(journal_info, "pub-year"),
        "publication_month": child_text(journal_info, "pub-mon"),
        "volume": child_text(journal_info, "volume"),
        "issue": child_text(journal_info, "issue"),
        "first_page": child_text(article_info, "fpage"),
        "last_page": child_text(article_info, "lpage"),
        "research_field": child_text(article_info, "article-categories"),
        "doi": child_text(article_info, "doi"),
        "uci": child_text(article_info, "uci"),
        "citation_count": child_text(article_info, "citation-count"),
        "full_text_open": child_text(article_info, "orte-open-yn"),
        "kci_url": child_text(article_info, "url"),
        "matched_query_ids": [query_id],
    }


def fetch_page(api_key: str, title: str, page: int) -> ET.Element:
    parameters = {
        "key": api_key,
        "apiCode": "articleSearch",
        "title": title,
        "page": page,
        "displayCount": DISPLAY_COUNT,
        "sortNm": "title",
    }
    request_url = f"{ENDPOINT}?{urlencode(parameters)}"
    with urlopen(request_url, timeout=30) as response:  # nosec B310 - fixed HTTPS endpoint
        return ET.fromstring(response.read())


def merge_records(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for record in records:
        stable_id = str(record.get("kci_article_id") or "")
        fallback = "|".join(
            str(record.get(field) or "") for field in ("title", "journal", "publication_year", "doi")
        )
        key = stable_id or fallback
        if key not in merged:
            merged[key] = record
            continue
        current = merged[key]
        query_ids = set(current["matched_query_ids"]) | set(record["matched_query_ids"])
        current["matched_query_ids"] = sorted(query_ids)
    return sorted(
        merged.values(),
        key=lambda item: (
            str(item.get("publication_year") or ""),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )


def collect(
    api_key: str, queries: list[dict[str, str]], max_pages: int, pause: float
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    collected: list[dict[str, object]] = []
    query_results: list[dict[str, object]] = []
    for query in queries:
        query_id = query["query_id"]
        raw_count = 0
        pages_requested = 0
        reported_total: int | None = None
        status = "complete"
        for page in range(1, max_pages + 1):
            root = fetch_page(api_key, query["title"], page)
            pages_requested += 1
            message = result_message(root)
            if message:
                if message.strip().casefold() in {"no data", "no data."}:
                    status = "no_data"
                    break
                raise RuntimeError(f"KCI API error for {query_id}: {message}")
            records = find_records(root)
            raw_count += len(records)
            collected.extend(parse_record(record, query_id) for record in records)
            total = child_text(root, "total")
            if total and total.isdigit():
                reported_total = int(total)
            if not records or len(records) < DISPLAY_COUNT:
                break
            if reported_total is not None and page * DISPLAY_COUNT >= reported_total:
                break
            time.sleep(pause)
        query_results.append(
            {
                "query_id": query_id,
                "title": query["title"],
                "focus": query.get("focus"),
                "status": status,
                "pages_requested": pages_requested,
                "reported_total": reported_total,
                "raw_records_retrieved": raw_count,
                "max_pages_limit": max_pages,
            }
        )
    return merge_records(collected), query_results


def write_output(
    records: list[dict[str, object]],
    queries: list[dict[str, str]],
    query_results: list[dict[str, object]],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    json_path = output_dir / f"kci-article-metadata-{stamp}.json"
    csv_path = output_dir / f"kci-article-metadata-{stamp}.csv"
    payload = {
        "schema_version": "0.1.0",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": {"provider": "KCI", "endpoint": ENDPOINT, "api_code": "articleSearch"},
        "queries": queries,
        "query_results": query_results,
        "record_count": len(records),
        "records": records,
        "limitations": [
            "Bibliographic metadata only; abstracts and full-text files are intentionally excluded.",
            "KCI retrieval is a secondary-source discovery layer, not a legal authority.",
            "Duplicates are merged by KCI article ID when available; editorial relevance remains a manual review task.",
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "kci_article_id", "title", "authors", "journal", "publisher", "publication_year",
        "publication_month", "volume", "issue", "first_page", "last_page", "research_field",
        "doi", "uci", "citation_count", "full_text_open", "kci_url", "matched_query_ids",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["authors"] = "; ".join(record["authors"])
            row["matched_query_ids"] = "; ".join(record["matched_query_ids"])
            writer.writerow(row)
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=Path("research/kci_queries.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/kci"))
    parser.add_argument("--api-key-env", default="KCI_API_KEY")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum 100-result pages per query.")
    parser.add_argument("--pause", type=float, default=0.3, help="Seconds between paginated requests.")
    args = parser.parse_args()

    if args.max_pages < 1:
        parser.error("--max-pages must be at least 1")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"Missing {args.api_key_env}. Apply for a KCI Open API key and export it only for this run.", file=sys.stderr)
        return 2
    query_payload = json.loads(args.queries.read_text(encoding="utf-8"))
    queries = query_payload.get("queries")
    if not isinstance(queries, list) or not all(
        isinstance(query, dict) and isinstance(query.get("query_id"), str) and isinstance(query.get("title"), str)
        for query in queries
    ):
        parser.error("queries must be a list of objects containing query_id and title")
    records, query_results = collect(api_key, queries, args.max_pages, args.pause)
    json_path, csv_path = write_output(records, queries, query_results, args.output_dir)
    print(f"Collected {len(records)} unique KCI metadata records.")
    print(json_path)
    print(csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
