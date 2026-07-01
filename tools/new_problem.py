"""Create a problem folder and update the local LeetCode index.

Example:
    python tools/new_problem.py --id 1 --title "Two Sum" --plan leetcode-75 --category hash --difficulty Easy --tags "Array,Hash Table"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROBLEMS_PATH = DATA_DIR / "problems.json"
CATEGORIES_PATH = DATA_DIR / "categories.json"
PLANS_PATH = DATA_DIR / "plans.json"
PLAN_TEMPLATE_PATH = ROOT / "plans" / "_template" / "_plan.md"

LANG_EXTENSIONS = {
    "python": "py",
    "python3": "py",
    "cpp": "cpp",
    "c++": "cpp",
    "java": "java",
    "javascript": "js",
    "typescript": "ts",
    "go": "go",
    "rust": "rs",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    words = re.findall(r"[a-z0-9]+", ascii_value)
    return "-".join(words) or "problem"


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def today() -> str:
    return date.today().isoformat()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def norm(value: Any) -> str:
    return str(value).strip().lower()


def norm_key(value: Any) -> str:
    return slugify(str(value)) or norm(value)


def category_lookup(categories: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in categories:
        slug = item.get("slug", "")
        keys = [slug, item.get("label", ""), *item.get("aliases", [])]
        for key in keys:
            if key:
                lookup[norm(key)] = slug
                lookup[norm_key(key)] = slug
    return lookup


def resolve_category(raw_category: str, categories: list[dict[str, Any]]) -> str:
    lookup = category_lookup(categories)
    key = norm(raw_category)
    resolved = lookup.get(key) or lookup.get(norm_key(raw_category))
    if resolved:
        return resolved

    available = ", ".join(item["slug"] for item in categories)
    raise ValueError(f"Unknown category: {raw_category}. Available categories: {available}")


def ensure_plan(plan_slug: str, categories: list[dict[str, Any]]) -> None:
    plan_dir = ROOT / "plans" / plan_slug
    plan_dir.mkdir(parents=True, exist_ok=True)

    plan_file = plan_dir / "_plan.md"
    if not plan_file.exists():
        if PLAN_TEMPLATE_PATH.exists():
            text = PLAN_TEMPLATE_PATH.read_text(encoding="utf-8")
            text = text.replace("计划名称", plan_slug).replace("计划 slug：", f"计划 slug：{plan_slug}")
        else:
            text = f"# {plan_slug}\n\n- 计划 slug：{plan_slug}\n- 状态：planned\n"
        plan_file.write_text(text, encoding="utf-8")

    for item in categories:
        slug = item.get("slug")
        if slug and slug != "_template":
            (plan_dir / slug).mkdir(parents=True, exist_ok=True)


def update_plans(plan_slug: str) -> None:
    plans = load_json(PLANS_PATH, [])
    if any(item.get("slug") == plan_slug for item in plans):
        return
    plans.append(
        {
            "slug": plan_slug,
            "name": plan_slug,
            "description": "",
            "status": "active",
        }
    )
    plans.sort(key=lambda item: item.get("slug", ""))
    save_json(PLANS_PATH, plans)


def solution_filename(language: str) -> str:
    extension = LANG_EXTENSIONS.get(language.lower(), language.lower().lstrip("."))
    return f"solution.{extension}"


def solution_template(language: str) -> str:
    if language.lower() in {"python", "python3"}:
        template_path = ROOT / "templates" / "solution.py"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return "from typing import List, Optional\n\n\nclass Solution:\n    pass\n"
    return ""


def explanation_text(args: argparse.Namespace, category: str, tags: list[str]) -> str:
    tags_text = ", ".join(tags) if tags else ""
    link = args.url or ""
    return f"""# {args.id:04d}. {args.title}

## 题目信息

- 难度：{args.difficulty or ""}
- 本地类别：{category}
- LeetCode 标签：{tags_text}
- 链接：{link}

## 核心思路

待补充。

## 算法步骤

1. 待补充。

## 复杂度

- 时间复杂度：
- 空间复杂度：

## 易错点

- 待补充。

## 复盘

- 待补充。
"""


def metadata(args: argparse.Namespace, category: str, tags: list[str], solution: str) -> dict[str, Any]:
    return {
        "id": args.id,
        "title": args.title,
        "slug": slugify(args.title),
        "difficulty": args.difficulty or "",
        "url": args.url or "",
        "plan": args.plan,
        "category": category,
        "tags": tags,
        "status": args.status,
        "language": args.language,
        "files": {
            "solution": solution,
            "explanation": "explanation.md",
            "cases": "cases.txt",
        },
        "created_at": today(),
        "updated_at": today(),
        "notes": "",
    }


def merge_unique(values: list[Any], additions: list[Any]) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for value in [*values, *additions]:
        key = norm(value)
        if key and key not in seen:
            merged.append(value)
            seen.add(key)
    return merged


def upsert_problem_index(
    args: argparse.Namespace,
    category: str,
    tags: list[str],
    folder: Path,
    solution: str,
) -> None:
    problems = load_json(PROBLEMS_PATH, [])
    entry = next((item for item in problems if int(item.get("id", -1)) == args.id), None)

    record = {
        "plan": args.plan,
        "category": category,
        "folder": rel(folder),
        "solution": solution,
        "explanation": "explanation.md",
        "status": args.status,
    }

    if entry is None:
        entry = {
            "id": args.id,
            "title": args.title,
            "slug": slugify(args.title),
            "difficulty": args.difficulty or "",
            "url": args.url or "",
            "plans": [args.plan],
            "categories": [category],
            "tags": tags,
            "records": [record],
            "notes": "",
        }
        problems.append(entry)
    else:
        entry["title"] = entry.get("title") or args.title
        entry["slug"] = entry.get("slug") or slugify(args.title)
        if args.difficulty:
            entry["difficulty"] = args.difficulty
        if args.url:
            entry["url"] = args.url

        entry["plans"] = merge_unique(entry.get("plans", []), [args.plan])
        entry["categories"] = merge_unique(entry.get("categories", []), [category])
        entry["tags"] = merge_unique(entry.get("tags", []), tags)

        records = entry.setdefault("records", [])
        existing_record = next(
            (
                item
                for item in records
                if item.get("plan") == args.plan and item.get("category") == category
            ),
            None,
        )
        if existing_record:
            existing_record.update(record)
        else:
            records.append(record)

    problems.sort(key=lambda item: int(item.get("id", 0)))
    save_json(PROBLEMS_PATH, problems)


def create_problem(args: argparse.Namespace) -> Path:
    categories = load_json(CATEGORIES_PATH, [])
    category = resolve_category(args.category, categories)
    tags = parse_csv(args.tags)
    title_slug = slugify(args.title)
    folder = ROOT / "plans" / args.plan / category / f"{args.id:04d}-{title_slug}"
    solution = solution_filename(args.language)

    ensure_plan(args.plan, categories)
    update_plans(args.plan)
    folder.mkdir(parents=True, exist_ok=True)

    metadata_path = folder / "metadata.json"
    next_metadata = metadata(args, category, tags, solution)
    if metadata_path.exists():
        previous_metadata = load_json(metadata_path, {})
        next_metadata["created_at"] = previous_metadata.get("created_at") or next_metadata["created_at"]
        next_metadata["notes"] = previous_metadata.get("notes", "")
    metadata_path.write_text(json.dumps(next_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    files_to_create = {
        folder / solution: solution_template(args.language),
        folder / "explanation.md": explanation_text(args, category, tags),
        folder / "cases.txt": "",
    }

    for path, content in files_to_create.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    upsert_problem_index(args, category, tags, folder, solution)
    return folder


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a LeetCode problem archive entry.")
    parser.add_argument("--id", type=int, required=True, help="LeetCode problem number.")
    parser.add_argument("--title", required=True, help="Problem title, for example 'Two Sum'.")
    parser.add_argument("--plan", required=True, help="Study plan slug, for example leetcode-75.")
    parser.add_argument("--category", required=True, help="Local category slug, label, or alias.")
    parser.add_argument("--difficulty", default="", help="Easy, Medium, or Hard.")
    parser.add_argument("--tags", default="", help="Comma-separated LeetCode tags.")
    parser.add_argument("--url", default="", help="LeetCode problem URL.")
    parser.add_argument("--language", default="python", help="Solution language. Default: python.")
    parser.add_argument("--status", default="draft", help="Local status. Default: draft.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        folder = create_problem(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created/updated: {folder}")
    print("Updated index: data/problems.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
