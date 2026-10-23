import argparse
import json
import re
import shutil
from pathlib import Path

from google.cloud import translate_v3

PROJECT_ID = "belarus-districts-game-123456"
DATA_FILE = Path(__file__).resolve().parents[1] / "src" / "district-info.js"
BATCH_SIZE = 25


def load_data():
	source = DATA_FILE.read_text(encoding="utf-8")
	match = re.search(r"window\.districtInfo\s*=\s*(\{.*\});\s*$", source, re.DOTALL)
	if not match:
		raise ValueError(f"Could not read districtInfo data from {DATA_FILE}")
	return json.loads(match.group(1))


def write_data(data):
	backup = DATA_FILE.with_suffix(".before-be-translation.js")
	if not backup.exists():
		shutil.copy2(DATA_FILE, backup)
		print(f"Created backup: {backup}")

	serialized = json.dumps(data, ensure_ascii=False, indent=4)
	DATA_FILE.write_text(f"window.districtInfo = {serialized};\n", encoding="utf-8")


def missing_fields(data):
	fields = []
	for district in data["districts"]:
		for item in district.get("items", []):
			for field_name in ("name", "desc"):
				value = item.get(field_name)
				if isinstance(value, dict) and value.get("ru") and not value.get("be"):
					fields.append(value)
	return fields


def translate_missing(data):
	fields = missing_fields(data)
	if not fields:
		print("All Belarusian translations are already present.")
		return

	client = translate_v3.TranslationServiceClient()
	parent = f"projects/{PROJECT_ID}/locations/global"

	for offset in range(0, len(fields), BATCH_SIZE):
		batch = fields[offset:offset + BATCH_SIZE]
		response = client.translate_text(
			request={
				"parent": parent,
				"contents": [field["ru"] for field in batch],
				"mime_type": "text/plain",
				"source_language_code": "ru",
				"target_language_code": "be",
			}
		)
		if len(response.translations) != len(batch):
			raise RuntimeError("Translation API returned an incomplete batch")

		for field, translation in zip(batch, response.translations):
			field["be"] = translation.translated_text

		print(f"Translated {min(offset + len(batch), len(fields))}/{len(fields)} fields")
		write_data(data)


def main():
	parser = argparse.ArgumentParser(
		description="Translate missing Belarusian district attraction fields with Google Cloud Translation."
	)
	parser.add_argument(
		"--apply",
		action="store_true",
		help="Call the Translation API and write translations. Without this option, only report pending fields.",
	)
	args = parser.parse_args()

	data = load_data()
	fields = missing_fields(data)
	print(f"Missing Belarusian fields: {len(fields)}")
	if args.apply:
		translate_missing(data)


if __name__ == "__main__":
	main()
