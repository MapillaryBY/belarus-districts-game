#!/usr/bin/env python3
"""Find external Bing image URLs for review without changing hits.htm."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote_plus


NAME_PATTERN = re.compile(r'^(\s*)"name": "(.+)",\s*$')
EMPTY_PHOTOS_PATTERN = re.compile(r'^\s*"photos": \[\]')
VILLAGE_PATTERN = re.compile(r'\s+в\s+д\.\s*', re.IGNORECASE)


def parse_name(serialized_name: str) -> str:
    return json.loads(f'"{serialized_name}"')


def search_query(name: str, district: str) -> str:
    simplified = VILLAGE_PATTERN.sub(" ", name)
    if simplified != name:
        return " ".join(simplified.split())

    return f"{name} {district}".strip()


def directory_name(name: str, district: str, index: int) -> str:
    source = f"{index:04d}-{name}-{district}".lower()
    safe = re.sub(r"[^a-zа-яё0-9]+", "-", source, flags=re.IGNORECASE).strip("-")
    return safe[:120] or f"item-{index:04d}"


def targets_from_lines(lines: list[str], only_empty: bool = True) -> list[dict[str, object]]:
    targets: list[dict[str, object]] = []
    district = ""
    item = ""

    for index, line in enumerate(lines):
        name_match = NAME_PATTERN.match(line)
        if name_match:
            name = parse_name(name_match.group(2))
            if index + 1 < len(lines) and re.match(r'^\s*"items"', lines[index + 1]):
                district = name
            else:
                item = name
        elif '"photos":' in line and item and (not only_empty or EMPTY_PHOTOS_PATTERN.match(line)):
            targets.append({"id": directory_name(item, district, index), "name": item, "district": district})

    return targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=Path(__file__).parent.parent / "src" / "hits.htm")
    parser.add_argument("--max-photos", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--item-id")
    args = parser.parse_args()

    html_path = args.path.resolve()
    manifest_path = Path(__file__).with_name("photo-candidates.json")
    state_path = Path(__file__).with_name("photo-crawler-state.json")
    targets = targets_from_lines(
        html_path.read_text(encoding="utf-8-sig").splitlines(),
        only_empty=not bool(args.item_id),
    )
    state = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.exists() else {"processed": []}
    processed = set(state.get("processed", []))
    if args.item_id:
        targets = [target for target in targets if target["id"] == args.item_id]
    else:
        targets = [target for target in targets if target["id"] not in processed]
    if args.limit > 0:
        targets = targets[:args.limit]

    manifest: list[dict[str, object]] = []
    manifest_path.write_text("[]\n", encoding="utf-8")
    print(f"Remaining objects without photos: {len(targets)}")
    for position, target in enumerate(targets, start=1):
        name = str(target["name"])
        district = str(target["district"])
        query = search_query(name, district)
        manifest.append({
            "id": target["id"],
            "name": name,
            "district": district,
            "query": query,
            "search_url": f"https://www.bing.com/images/search?q={quote_plus(query)}",
        })
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{position}] {query}")

        processed.add(str(target["id"]))
        state_path.write_text(json.dumps({"processed": sorted(processed)}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Candidates: {len(manifest)}")
    print(f"State: {state_path}")
    print(f"Open: {Path(__file__).with_name('review-photos.html')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
