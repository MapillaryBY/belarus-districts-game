#!/usr/bin/env python3
"""Fill empty photo entries from visible Bing Images searches in Microsoft Edge."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait

NAME_PATTERN = re.compile(r'^(\s*)"name": "(.+)",\s*$')
EMPTY_PHOTOS_PATTERN = re.compile(r'^(\s*)"photos": \[\]')
VILLAGE_PATTERN = re.compile(r'\s+в\s+д\.\s*', re.IGNORECASE)


def parse_name(serialized_name: str) -> str:
	return json.loads(f'"{serialized_name}"')


def search_query(name: str, district: str) -> str:
	simplified = VILLAGE_PATTERN.sub(" ", name)
	if simplified != name:
		return " ".join(simplified.split())
	return f"{name} {district}".strip()


def item_id(name: str, district: str, index: int) -> str:
	value = f"{index:04d}-{name}-{district}".lower()
	return re.sub(r"[^a-zа-яё0-9]+", "-", value, flags=re.IGNORECASE).strip("-")[:120]


def find_targets(lines: list[str]) -> list[dict[str, object]]:
	targets: list[dict[str, object]] = []
	district = ""
	item = ""
	for index, line in enumerate(lines):
		match = NAME_PATTERN.match(line)
		if match:
			name = parse_name(match.group(2))
			if index + 1 < len(lines) and re.match(r'^\s*"items"', lines[index + 1]):
				district = name
			else:
				item = name
		elif EMPTY_PHOTOS_PATTERN.match(line) and item:
			targets.append({"index": index, "id": item_id(item, district, index), "name": item, "district": district})
	return targets


def launch_edge() -> webdriver.Edge:
	options = Options()
	options.add_argument("--start-maximized")
	return webdriver.Edge(options=options)


def image_urls(driver: webdriver.Edge, query: str, max_photos: int) -> list[str]:
	driver.get(f"https://www.bing.com/images/search?q={quote_plus(query)}")
	WebDriverWait(driver, 15).until(lambda browser: browser.find_elements(By.CSS_SELECTOR, "a.iusc"))
	time.sleep(1)

	urls: list[str] = []
	for card in driver.find_elements(By.CSS_SELECTOR, "a.iusc"):
		metadata = card.get_attribute("m")
		if not metadata:
			continue
		try:
			url = json.loads(metadata).get("murl")
		except json.JSONDecodeError:
			continue
		if url and url not in urls:
			urls.append(url)
		if len(urls) >= max_photos:
			break
	return urls


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--path", type=Path, default=Path(__file__).parent.parent / "src" / "hits.htm")
	parser.add_argument("--max-photos", type=int, default=2)
	parser.add_argument("--limit", type=int, default=1)
	args = parser.parse_args()

	html_path = args.path.resolve()
	state_path = Path(__file__).with_name("photo-browser-state.json")
	lines = html_path.read_text(encoding="utf-8-sig").splitlines()
	state = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.exists() else {"processed": []}
	processed = set(state.get("processed", []))
	targets = [target for target in find_targets(lines) if target["id"] not in processed]
	if args.limit > 0:
		targets = targets[:args.limit]

	print(f"Objects to process: {len(targets)}")
	try:
		driver = launch_edge()
	except WebDriverException as error:
		print(f"Could not launch Edge: {error}")
		return 1

	try:
		for target in targets:
			query = search_query(str(target["name"]), str(target["district"]))
			try:
				urls = image_urls(driver, query, args.max_photos)
			except Exception as error:
				print(f"ERROR: {query} - {error}")
				continue

			if urls:
				index = int(target["index"])
				indent = EMPTY_PHOTOS_PATTERN.match(lines[index]).group(1)
				lines[index] = f'{indent}"photos": {json.dumps(urls, ensure_ascii=False)}'
				html_path.write_text("\n".join(lines), encoding="utf-8")
				print(f"OK: {query} -> {len(urls)} photo(s)")
			else:
				print(f"NOT FOUND: {query}")

			processed.add(str(target["id"]))
			state_path.write_text(json.dumps({"processed": sorted(processed)}, ensure_ascii=False, indent=2), encoding="utf-8")
	finally:
		driver.quit()

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
