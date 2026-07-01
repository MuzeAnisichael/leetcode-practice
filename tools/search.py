"""Search local LeetCode archive.

Examples:
    python tools/search.py --id 1
    python tools/search.py --tag "Hash Table"
    python tools/search.py --category hash
    python tools/search.py --category 哈希 --open
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROBLEMS_PATH = DATA_DIR / "problems.json"
CATEGORIES_PATH = DATA_DIR / "categories.json"
PLANS_PATH = DATA_DIR / "plans.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def slugify(value: str) -> str:
    parts = re.findall(r"[a-zA-Z0-9]+", value.lower())
    return "-".join(parts)


def norm(value: Any) -> str:
    return str(value).strip().lower()


def norm_key(value: Any) -> str:
    raw = norm(value)
    return slugify(raw) or raw


def build_category_lookup(categories: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in categories:
        slug = item.get("slug", "")
        keys = [slug, item.get("label", ""), *item.get("aliases", [])]
        for key in keys:
            if key:
                lookup[norm(key)] = slug
                lookup[norm_key(key)] = slug
    return lookup


def category_slug(value: str, categories: list[dict[str, Any]]) -> str:
    lookup = build_category_lookup(categories)
    key = norm(value)
    return lookup.get(key) or lookup.get(norm_key(value)) or value


def text_matches(needle: str, values: list[Any]) -> bool:
    if not needle:
        return True
    needle_raw = norm(needle)
    needle_key = norm_key(needle)
    for value in values:
        hay_raw = norm(value)
        hay_key = norm_key(value)
        if needle_raw in hay_raw or needle_key in hay_key:
            return True
    return False


def entry_record_values(entry: dict[str, Any], field: str) -> list[Any]:
    plural_fields = {"category": "categories", "plan": "plans"}
    values = list(entry.get(plural_fields.get(field, field + "s"), []))
    for record in entry.get("records", []):
        value = record.get(field)
        if value:
            values.append(value)
    return values


def matches(entry: dict[str, Any], args: argparse.Namespace, categories: list[dict[str, Any]]) -> bool:
    if args.id is not None and int(entry.get("id", -1)) != args.id:
        return False

    if args.plan and not text_matches(args.plan, entry_record_values(entry, "plan")):
        return False

    if args.category:
        wanted = category_slug(args.category, categories)
        values = entry_record_values(entry, "category")
        if wanted not in values and not text_matches(wanted, values):
            return False

    for tag in args.tag or []:
        if not text_matches(tag, entry.get("tags", [])):
            return False

    if args.query:
        values = [
            entry.get("title", ""),
            entry.get("slug", ""),
            entry.get("url", ""),
            entry.get("notes", ""),
        ]
        if not text_matches(args.query, values):
            return False

    return True


def display_problem(entry: dict[str, Any], index: int) -> None:
    problem_id = int(entry.get("id", 0))
    title = entry.get("title", "")
    difficulty = entry.get("difficulty") or "Unknown"
    tags = ", ".join(entry.get("tags", [])) or "-"
    categories = ", ".join(entry.get("categories", [])) or "-"
    plans = ", ".join(entry.get("plans", [])) or "-"

    print(f"{index}. #{problem_id:04d} {title} [{difficulty}]")
    print(f"   plans: {plans}")
    print(f"   categories: {categories}")
    print(f"   tags: {tags}")

    if entry.get("url"):
        print(f"   url: {entry['url']}")

    records = entry.get("records", [])
    if not records:
        print("   records: -")
        return

    print("   records:")
    for record in records:
        folder = ROOT / record.get("folder", "")
        status = record.get("status", "draft")
        plan = record.get("plan", "-")
        category = record.get("category", "-")
        print(f"     - {plan}/{category} [{status}] {folder}")


def first_folder(results: list[dict[str, Any]]) -> Path | None:
    for entry in results:
        for record in entry.get("records", []):
            folder = record.get("folder")
            if folder:
                return ROOT / folder
    return None


def open_folder(folder: Path) -> None:
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if hasattr(os, "startfile"):
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        print(folder)


def list_categories(categories: list[dict[str, Any]]) -> None:
    for item in categories:
        aliases = ", ".join(item.get("aliases", []))
        print(f"{item['slug']}: {item.get('label', '')} ({aliases})")


def list_plans(plans: list[dict[str, Any]]) -> None:
    for item in plans:
        status = item.get("status", "")
        desc = item.get("description", "")
        print(f"{item['slug']}: {item.get('name', '')} [{status}] {desc}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search local LeetCode archive.")
    parser.add_argument("--id", type=int, help="LeetCode problem number.")
    parser.add_argument("--tag", action="append", help="LeetCode tag. Can be repeated.")
    parser.add_argument("--category", help="Local category slug, label, or alias.")
    parser.add_argument("--plan", help="Study plan slug.")
    parser.add_argument("--query", "-q", help="Search title, slug, url, or notes.")
    parser.add_argument("--open", action="store_true", help="Open the first matched problem folder.")
    parser.add_argument("--json", action="store_true", help="Print matched entries as JSON.")
    parser.add_argument("--list-categories", action="store_true", help="List available category slugs.")
    parser.add_argument("--list-plans", action="store_true", help="List known plans.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    categories = load_json(CATEGORIES_PATH, [])
    plans = load_json(PLANS_PATH, [])

    if args.list_categories:
        list_categories(categories)
        return 0

    if args.list_plans:
        list_plans(plans)
        return 0

    problems = load_json(PROBLEMS_PATH, [])
    results = [entry for entry in problems if matches(entry, args, categories)]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif not results:
        print("No problems found.")
        print("Use tools/new_problem.py to create entries, or adjust the search filters.")
    else:
        for index, entry in enumerate(results, start=1):
            display_problem(entry, index)

    if args.open:
        folder = first_folder(results)
        if folder is None:
            print("No folder to open.")
        else:
            open_folder(folder)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
