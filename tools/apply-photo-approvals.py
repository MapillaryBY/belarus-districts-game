#!/usr/bin/env python3
"""Apply image selections from photo-approvals.json to src/hits.htm."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NAME_PATTERN = re.compile(r'^(\s*)"name": "(.+)",\s*$')
EMPTY_PHOTOS_PATTERN = re.compile(r'^(\s*)"photos": \[\]')


def parse_name(serialized_name: str) -> str:
	return json.loads(f'"{serialized_name}"')


def directory_name(name: str, district: str, index: int) -> str:
	source = f"{index:04d}-{name}-{district}".lower()
	safe = re.sub(r"[^a-zа-яё0-9]+", "-", source, flags=re.IGNORECASE).strip("-")
	return safe[:120] or f"item-{index:04d}"


def targets_from_lines(lines: list[str]) -> dict[str, int]:
	targets: dict[str, int] = {}
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
		elif EMPTY_PHOTOS_PATTERN.match(line) and item:
			targets[directory_name(item, district, index)] = index

	return targets


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--path", type=Path, default=Path(__file__).parent.parent / "src" / "hits.htm")
	args = parser.parse_args()

	html_path = args.path.resolve()
	tools_path = Path(__file__).parent
	approvals_path = tools_path / "photo-approvals.json"
	if not approvals_path.exists():
		print(f"No approvals file: {approvals_path}")
		return 1

	approvals: dict[str, list[str]] = json.loads(approvals_path.read_text(encoding="utf-8"))
	lines = html_path.read_text(encoding="utf-8-sig").splitlines()
	targets = targets_from_lines(lines)
	applied = 0

	for item_id, selected_urls in approvals.items():
		index = targets.get(item_id)
		if index is None or not selected_urls:
			continue

		indent = EMPTY_PHOTOS_PATTERN.match(lines[index]).group(1)
		lines[index] = f'{indent}"photos": {json.dumps(selected_urls, ensure_ascii=False)}'
		html_path.write_text("\n".join(lines), encoding="utf-8")
		applied += 1
		print(f"Applied: {item_id} -> {len(selected_urls)} photo(s)")

	print(f"Applied objects: {applied}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
