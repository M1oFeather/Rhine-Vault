"""Small Git integration boundary for approved workflow commits."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitCommitResult:
    status: str
    commit: str | None
    message: str | None = None


def commit_paths(*, repo_root: Path, paths: tuple[Path, ...], message: str) -> GitCommitResult:
    """Commit approved files when repo_root is a Git repository.

    The caller persists the returned status. This helper never raises for ordinary
    Git availability/configuration problems because SQLite has already recorded
    the approval intent and must be able to surface versioning failure explicitly.
    """

    if not paths:
        return GitCommitResult(status="skipped", commit=None, message="no paths to commit")
    if not (repo_root / ".git").exists():
        return GitCommitResult(status="skipped", commit=None, message="not a git repository")

    relative_paths = [str(path.relative_to(repo_root)) for path in paths]
    try:
        subprocess.run(
            ["git", "add", *relative_paths],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if diff_check.returncode == 0:
            return GitCommitResult(status="skipped", commit=None, message="no git changes")
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        rev_parse = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return GitCommitResult(status="failed", commit=None, message=str(exc))

    return GitCommitResult(status="committed", commit=rev_parse.stdout.strip())
