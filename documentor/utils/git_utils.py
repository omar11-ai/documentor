"""Git utilities for DocuMentor."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime
from git import Repo, InvalidGitRepositoryError, GitCommandError

from documentor.core.models import CommitInfo


def get_repo_root(path: Path = Path.cwd()) -> Path:
    """Find the root of the git repository."""
    try:
        repo = Repo(path, search_parent_directories=True)
        return Path(repo.working_tree_dir)
    except InvalidGitRepositoryError:
        return path


def is_git_repo(path: Path = Path.cwd()) -> bool:
    """Check if path is inside a git repository."""
    try:
        Repo(path, search_parent_directories=True)
        return True
    except InvalidGitRepositoryError:
        return False


def get_git_log(
    repo_path: Path,
    max_count: int = 1000,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[CommitInfo]:
    """Get git log as list of CommitInfo."""
    try:
        repo = Repo(repo_path)
        commits = []

        log_args = ["--pretty=format:%H|%an|%ad|%s", "--date=iso-strict", f"-n {max_count}"]
        if since:
            log_args.append(f"--since={since.isoformat()}")
        if until:
            log_args.append(f"--until={until.isoformat()}")

        log_output = repo.git.log(*log_args)

        for line in log_output.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue

            hash_, author, date_str, message = parts
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                date = datetime.now()

            # Check if bug fix or feature
            msg_lower = message.lower()
            is_bug_fix = any(kw in msg_lower for kw in ["fix", "bug", "patch", "hotfix", "regress"])
            is_feature = any(kw in msg_lower for kw in ["feat", "feature", "add", "implement", "new"])

            commits.append(CommitInfo(
                hash=hash_,
                message=message,
                author=author,
                date=date,
                is_bug_fix=is_bug_fix,
                is_feature=is_feature,
            ))

        return commits

    except (InvalidGitRepositoryError, GitCommandError):
        return []


def get_file_history(repo_path: Path, file_path: Path, max_count: int = 50) -> list[CommitInfo]:
    """Get commit history for a specific file."""
    try:
        repo = Repo(repo_path)
        rel_path = file_path.relative_to(repo_path)

        log_output = repo.git.log(
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso-strict",
            f"-n {max_count}",
            "--",
            str(rel_path),
        )

        commits = []
        for line in log_output.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue

            hash_, author, date_str, message = parts
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                date = datetime.now()

            msg_lower = message.lower()
            is_bug_fix = any(kw in msg_lower for kw in ["fix", "bug", "patch", "hotfix", "regress"])
            is_feature = any(kw in msg_lower for kw in ["feat", "feature", "add", "implement", "new"])

            commits.append(CommitInfo(
                hash=hash_,
                message=message,
                author=author,
                date=date,
                is_bug_fix=is_bug_fix,
                is_feature=is_feature,
            ))

        return commits

    except (InvalidGitRepositoryError, GitCommandError, ValueError):
        return []


def get_commit_info(repo_path: Path, commit_hash: str) -> Optional[CommitInfo]:
    """Get detailed info for a specific commit."""
    try:
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)

        msg_lower = commit.message.lower()
        is_bug_fix = any(kw in msg_lower for kw in ["fix", "bug", "patch", "hotfix", "regress"])
        is_feature = any(kw in msg_lower for kw in ["feat", "feature", "add", "implement", "new"])

        return CommitInfo(
            hash=commit.hexsha,
            message=commit.message.strip(),
            author=commit.author.name,
            date=datetime.fromtimestamp(commit.committed_date),
            files_changed=[f for f in commit.stats.files.keys()],
            is_bug_fix=is_bug_fix,
            is_feature=is_feature,
        )
    except (InvalidGitRepositoryError, GitCommandError, ValueError):
        return None


def get_co_change_files(repo_path: Path, file_path: Path, max_commits: int = 100) -> list[str]:
    """Get files that frequently change together with the given file."""
    try:
        repo = Repo(repo_path)
        rel_path = file_path.relative_to(repo_path)

        # Get commits that touched this file
        commits = repo.iter_commits(paths=str(rel_path), max_count=max_commits)

        co_change_counts: dict[str, int] = {}
        for commit in commits:
            for changed_file in commit.stats.files.keys():
                if changed_file != str(rel_path):
                    co_change_counts[changed_file] = co_change_counts.get(changed_file, 0) + 1

        # Sort by frequency
        sorted_files = sorted(co_change_counts.items(), key=lambda x: x[1], reverse=True)
        return [f for f, _ in sorted_files[:20]]

    except (InvalidGitRepositoryError, GitCommandError, ValueError):
        return []