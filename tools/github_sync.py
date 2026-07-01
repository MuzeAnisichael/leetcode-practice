"""Sync the local LeetCode archive to a GitHub repository.

Examples:
    python tools/github_sync.py --repo leetcode-practice --public
    python tools/github_sync.py --repo MuzeAnisichael/leetcode-practice --message "Update archive"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GITHUB_CONFIG_PATH = DATA_DIR / "github.json"


class SyncError(RuntimeError):
    pass


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def text(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


@dataclass
class SyncResult:
    repo: str
    repo_url: str
    branch: str
    created_remote: bool = False
    committed: bool = False
    pushed: bool = False
    commands: list[CommandResult] = field(default_factory=list)


def run_command(args: list[str], check: bool = True) -> CommandResult:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    result = CommandResult(args=args, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
    if check and completed.returncode != 0:
        command = " ".join(args)
        raise SyncError(f"Command failed: {command}\n{result.text}")
    return result


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
    parts = re.findall(r"[a-zA-Z0-9]+", value.lower())
    return "-".join(parts) or "leetcode-practice"


def default_repo_name() -> str:
    return slugify(ROOT.name)


def parse_repo(value: str) -> tuple[str | None, str]:
    value = value.strip().removesuffix(".git")
    github_prefix = "https://github.com/"
    if value.startswith(github_prefix):
        value = value[len(github_prefix) :]
    value = value.strip("/")
    if "/" in value:
        owner, name = value.split("/", 1)
        return owner.strip(), slugify(name)
    return None, slugify(value)


def git_is_repo(commands: list[CommandResult]) -> bool:
    result = run_command(["git", "rev-parse", "--is-inside-work-tree"], check=False)
    commands.append(result)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def git_has_head(commands: list[CommandResult]) -> bool:
    result = run_command(["git", "rev-parse", "--verify", "HEAD"], check=False)
    commands.append(result)
    return result.returncode == 0


def git_status_porcelain(commands: list[CommandResult]) -> str:
    result = run_command(["git", "status", "--porcelain"], check=True)
    commands.append(result)
    return result.stdout


def ensure_git_repo(branch: str, commands: list[CommandResult]) -> None:
    if not git_is_repo(commands):
        commands.append(run_command(["git", "init"], check=True))

    current_branch = run_command(["git", "branch", "--show-current"], check=False)
    commands.append(current_branch)
    if current_branch.stdout.strip() != branch:
        checkout = run_command(["git", "checkout", "-B", branch], check=True)
        commands.append(checkout)


def commit_changes(message: str, commands: list[CommandResult]) -> bool:
    if not git_status_porcelain(commands):
        return False

    commands.append(run_command(["git", "add", "-A"], check=True))
    commands.append(run_command(["git", "commit", "-m", message], check=True))
    return True


def current_origin(commands: list[CommandResult]) -> str | None:
    result = run_command(["git", "remote", "get-url", "origin"], check=False)
    commands.append(result)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def gh_current_user(commands: list[CommandResult]) -> str:
    result = run_command(["gh", "api", "user", "--jq", ".login"], check=True)
    commands.append(result)
    user = result.stdout.strip()
    if not user:
        raise SyncError("GitHub CLI is authenticated, but the login name could not be read.")
    return user


def repo_exists(full_name: str, commands: list[CommandResult]) -> bool:
    result = run_command(["gh", "repo", "view", full_name, "--json", "name"], check=False)
    commands.append(result)
    return result.returncode == 0


def ensure_remote(
    repo: str,
    visibility: str,
    description: str,
    commands: list[CommandResult],
) -> tuple[str, str, bool]:
    owner, repo_name = parse_repo(repo)
    if owner is None:
        owner = gh_current_user(commands)

    full_name = f"{owner}/{repo_name}"
    repo_url = f"https://github.com/{full_name}"

    origin = current_origin(commands)
    if origin:
        return full_name, repo_url, False

    if repo_exists(full_name, commands):
        commands.append(run_command(["git", "remote", "add", "origin", f"{repo_url}.git"], check=True))
        return full_name, repo_url, False

    visibility_flag = "--public" if visibility == "public" else "--private"
    command = [
        "gh",
        "repo",
        "create",
        full_name,
        visibility_flag,
        "--source",
        str(ROOT),
        "--remote",
        "origin",
        "--description",
        description,
    ]
    commands.append(run_command(command, check=True))
    return full_name, repo_url, True


def save_sync_config(result: SyncResult, visibility: str) -> None:
    save_json(
        GITHUB_CONFIG_PATH,
        {
            "repo": result.repo,
            "url": result.repo_url,
            "visibility": visibility,
            "branch": result.branch,
            "last_sync_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def sync_to_github(
    repo: str | None = None,
    visibility: str = "public",
    branch: str = "main",
    message: str = "Sync LeetCode archive",
    description: str = "Structured local LeetCode practice archive.",
) -> SyncResult:
    if visibility not in {"public", "private"}:
        raise ValueError("visibility must be 'public' or 'private'")

    commands: list[CommandResult] = []
    repo = repo or default_repo_name()
    branch = branch or "main"
    message = message or "Sync LeetCode archive"

    ensure_git_repo(branch, commands)
    full_name, repo_url, created_remote = ensure_remote(repo, visibility, description, commands)
    result = SyncResult(
        repo=full_name,
        repo_url=repo_url,
        branch=branch,
        created_remote=created_remote,
        committed=False,
        pushed=False,
        commands=commands,
    )
    save_sync_config(result, visibility)

    committed = commit_changes(message, commands)

    if git_has_head(commands):
        commands.append(run_command(["git", "push", "-u", "origin", branch], check=True))
        pushed = True
    else:
        pushed = False

    result.committed = committed
    result.pushed = pushed
    save_sync_config(result, visibility)
    return result


def result_summary(result: SyncResult) -> str:
    lines = [
        f"Repository: {result.repo}",
        f"URL: {result.repo_url}",
        f"Branch: {result.branch}",
        f"Created remote: {'yes' if result.created_remote else 'no'}",
        f"Committed changes: {'yes' if result.committed else 'no'}",
        f"Pushed: {'yes' if result.pushed else 'no'}",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync this LeetCode archive to GitHub.")
    parser.add_argument("--repo", default=default_repo_name(), help="Repository name, owner/name, or GitHub URL.")
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument("--public", action="store_true", help="Create the repository as public. Default.")
    visibility.add_argument("--private", action="store_true", help="Create the repository as private.")
    parser.add_argument("--branch", default="main", help="Branch to push. Default: main.")
    parser.add_argument("--message", default="Sync LeetCode archive", help="Commit message.")
    parser.add_argument("--description", default="Structured local LeetCode practice archive.", help="GitHub repository description.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    visibility = "private" if args.private else "public"
    try:
        result = sync_to_github(
            repo=args.repo,
            visibility=visibility,
            branch=args.branch,
            message=args.message,
            description=args.description,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
