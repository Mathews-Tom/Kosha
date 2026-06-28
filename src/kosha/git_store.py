"""Git system-of-record store: branch per ingest, commit per plan, daily backup.

Kosha treats Git as the system of record (system_design §1 "Every write is
reviewable", §6 "State of record"). The store enforces the §1 governance
invariant in code:

* **Branch per ingest.** Every ingest works on its own branch, so nothing reaches
  ``main`` without a human merge.
* **Commit per approved plan.** An approved :class:`~kosha.plan.ChangePlan` lands
  as one atomic commit on that branch.
* **Daily backup tag.** A ``backup/<date>`` tag is the rollback substrate the
  §7.1 "branch-not-main + daily backup" failure handling relies on.

It is a thin, deterministic wrapper over the ``git`` binary — no new dependency —
that fails loud (:class:`GitError`) on any git error rather than swallowing it.
The committer identity is the product's own (``Kosha``), passed per-invocation so
commits succeed without depending on a machine's global git config.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import date
from pathlib import Path

_BACKUP_PREFIX = "backup"


class GitError(RuntimeError):
    """A ``git`` invocation exited non-zero."""


class GitStore:
    """Branch/commit/tag operations over one Git repository working tree."""

    def __init__(
        self,
        repo: Path,
        *,
        author_name: str = "Kosha",
        author_email: str = "kosha@localhost",
    ) -> None:
        self._repo = repo
        self._author_name = author_name
        self._author_email = author_email

    @classmethod
    def init(
        cls,
        repo: Path,
        *,
        default_branch: str = "main",
        author_name: str = "Kosha",
        author_email: str = "kosha@localhost",
    ) -> GitStore:
        """Initialize a fresh repository at ``repo`` and return its store.

        Used to bootstrap a bundle's repository (and by tests); an existing repo
        is opened with the constructor instead.
        """
        repo.mkdir(parents=True, exist_ok=True)
        store = cls(repo, author_name=author_name, author_email=author_email)
        store._git("init", "-b", default_branch)
        return store

    @property
    def repo(self) -> Path:
        return self._repo

    def is_repo(self) -> bool:
        """True when ``repo`` is inside a Git work tree."""
        result = self._run("rev-parse", "--is-inside-work-tree", check=False)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def head_branch(self) -> str:
        """Return the checked-out branch name (works before the first commit)."""
        return self._git("branch", "--show-current")

    def current_sha(self, ref: str = "HEAD") -> str:
        """Return the commit SHA ``ref`` resolves to."""
        return self._git("rev-parse", ref)

    def branch_exists(self, name: str) -> bool:
        """True when a local branch ``name`` exists."""
        return self._ref_exists(f"refs/heads/{name}")

    def tag_exists(self, name: str) -> bool:
        """True when a tag ``name`` exists."""
        return self._ref_exists(f"refs/tags/{name}")

    def create_branch(self, name: str, *, base: str | None = None, switch: bool = True) -> None:
        """Create branch ``name`` (from ``base`` or current HEAD), checking it out.

        Pass ``switch=False`` to create the branch ref without leaving the current
        branch.
        """
        if switch:
            args = ["switch", "-c", name]
            if base is not None:
                args.append(base)
            self._git(*args)
        else:
            args = ["branch", name]
            if base is not None:
                args.append(base)
            self._git(*args)

    def switch(self, name: str) -> None:
        """Check out an existing branch ``name``."""
        self._git("switch", name)

    def commit(self, paths: Sequence[Path | str], message: str) -> str:
        """Stage ``paths`` and commit them with ``message``; return the new SHA.

        The commit carries the product's committer identity, set per-invocation so
        it does not depend on the machine's global git config.
        """
        if not paths:
            raise GitError("refusing to commit with no paths")
        self._git("add", "--", *(str(path) for path in paths))
        self._git(
            "-c",
            f"user.name={self._author_name}",
            "-c",
            f"user.email={self._author_email}",
            "commit",
            "-m",
            message,
        )
        return self.current_sha()

    def tag_daily_backup(self, on: date | None = None, *, ref: str = "HEAD") -> str:
        """Move (or create) the ``backup/<date>`` tag at ``ref``; return its name.

        One tag per day, force-updated to the latest committed state so the day's
        most recent ingest is always recoverable (§7.1 rollback substrate).
        """
        name = f"{_BACKUP_PREFIX}/{(on or date.today()).isoformat()}"
        self._git("tag", "-f", name, ref)
        return name

    def tracked_files(self, ref: str = "HEAD") -> list[str]:
        """Return the repo-relative paths tracked at ``ref`` (sorted)."""
        listing = self._git("ls-tree", "-r", "--name-only", ref)
        return sorted(line for line in listing.splitlines() if line)

    def commit_message(self, ref: str = "HEAD") -> str:
        """Return the full commit message of ``ref``."""
        return self._git("log", "-1", "--format=%B", ref).rstrip("\n")

    def _ref_exists(self, ref: str) -> bool:
        return self._run("rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0

    def _git(self, *args: str) -> str:
        """Run a git subcommand, returning stripped stdout; raise on failure."""
        result = self._run(*args, check=True)
        return result.stdout.strip()

    def _run(self, *args: str, check: bool) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(self._repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            command = " ".join(args)
            raise GitError(f"git {command} failed ({result.returncode}): {result.stderr.strip()}")
        return result
