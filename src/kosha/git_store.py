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

import os
import subprocess
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from types import TracebackType

_BACKUP_PREFIX = "backup"
_LOCK_NAME = "kosha-ingest.lock"


class GitError(RuntimeError):
    """A ``git`` invocation exited non-zero."""


class IngestLockError(RuntimeError):
    """Raised when a concurrent ingest already holds the repository's ingest lock."""


class IngestLock:
    """An exclusive, PID-stamped lock over one repository's ingest-commit phase.

    Two concurrent ingests against the same bundle repo share one working tree:
    ``GitStore.create_branch``/``commit`` mutate it via ``git`` subprocesses with
    no isolation between processes, so one ingest's branch switch can land
    between another's file write and commit, corrupting the branch or silently
    mixing changes from two ingests into one commit. This lock makes that
    write-phase exclusive per repository and fails loudly rather than letting
    two ingests interleave; it does not queue or wait, since a wait with no
    timeout risks a hung holder blocking every future ingest indefinitely.
    """

    def __init__(self, repo: Path, *, name: str = _LOCK_NAME) -> None:
        self._path = repo / ".git" / name

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> None:
        """Acquire the lock, reclaiming a stale one first; raise if still held."""
        self._reclaim_if_stale()
        try:
            fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise IngestLockError(
                f"another ingest (pid {self._read_holder()}) holds the lock at "
                f"{self._path}; wait for it to finish, or remove the lock file "
                "if that process crashed"
            ) from None
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))

    def release(self) -> None:
        """Release the lock. Safe to call even if it was never acquired."""
        self._path.unlink(missing_ok=True)

    def __enter__(self) -> IngestLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def _read_holder(self) -> str:
        try:
            return self._path.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            return "unknown"

    def _reclaim_if_stale(self) -> None:
        """Remove the lock file if its recorded PID is no longer a live process."""
        if not self._path.is_file():
            return
        raw = self._read_holder()
        if not raw.isdigit() or _pid_is_alive(int(raw)):
            return
        self._path.unlink(missing_ok=True)


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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

    def commit_staged(self, message: str) -> str:
        """Commit whatever is already staged (``git add``ed) with ``message``.

        Used by recovery operations that stage a whole-tree change themselves
        (:meth:`restore_tree`) rather than an explicit path list, so :meth:`commit`'s
        "no paths" refusal does not apply.
        """
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

    def diff_name_status(self, ref_a: str, ref_b: str) -> list[tuple[str, str]]:
        """Return ``(status, path)`` pairs for the tree changes from ``ref_a`` to ``ref_b``.

        ``status`` is git's single-letter code (``A``dded, ``M``odified,
        ``D``eleted); a rename/copy score suffix (e.g. ``R100``) is reduced to
        its leading letter since recovery only needs the coarse kind of
        change, not similarity percentage.
        """
        output = self._git("diff", "--name-status", ref_a, ref_b)
        pairs: list[tuple[str, str]] = []
        for line in output.splitlines():
            if not line:
                continue
            status, _, path = line.partition("\t")
            pairs.append((status[0], path))
        return pairs

    def restore_tree(self, ref: str) -> None:
        """Stage the working tree to exactly match ``ref``'s tree; does not commit.

        Deletes tracked paths absent from ``ref`` and restores/overwrites the
        paths present in it. Callers are expected to have already verified
        ``ref`` exists and to commit the staged result themselves
        (:meth:`commit_staged`) so the caller's commit message can describe the
        recovery action.
        """
        current = set(self.tracked_files())
        target = set(self.tracked_files(ref))
        to_remove = sorted(current - target)
        if to_remove:
            self._git("rm", "-q", "--", *to_remove)
        self._git("checkout", ref, "--", ".")
        self._git("add", "-A")

    def tag_daily_backup(self, on: date | None = None, *, ref: str = "HEAD") -> str:
        """Move (or create) the ``backup/<date>`` tag at ``ref``; return its name.

        One tag per day, force-updated to the latest committed state so the day's
        most recent ingest is always recoverable (§7.1 rollback substrate).
        """
        name = f"{_BACKUP_PREFIX}/{(on or date.today()).isoformat()}"
        self._git("tag", "-f", name, ref)
        return name

    def create_tag(self, name: str, ref: str = "HEAD") -> str:
        """Create a new tag ``name`` at ``ref``; return its name.

        Unlike :meth:`tag_daily_backup`, this never force-moves an existing
        tag — it fails loud (:class:`GitError`) instead, so a recovery-safety
        or release tag can never be silently overwritten once created.
        """
        self._git("tag", name, ref)
        return name

    def export_archive(self, ref: str, out_path: Path) -> Path:
        """Write a deterministic archive of ``ref``'s tree to ``out_path``.

        Format is inferred from ``out_path``'s suffix (``.zip`` or ``.tar``);
        any other suffix is rejected rather than guessed, since ``git
        archive``'s built-in gzip support depends on external tooling
        (``tar.tar.gz.command``) that is not guaranteed to be configured.
        The archive content is a pure function of the tree at ``ref``, so
        exporting the same ref twice produces byte-identical output.
        """
        archive_format = {".zip": "zip", ".tar": "tar"}.get(out_path.suffix)
        if archive_format is None:
            raise GitError(f"unsupported archive format {out_path.suffix!r}: use .zip or .tar")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._git("archive", f"--format={archive_format}", "-o", str(out_path), ref)
        return out_path

    def tags_matching(self, prefix: str) -> list[str]:
        """Return every tag name starting with ``prefix``, sorted."""
        listing = self._git("tag", "--list", f"{prefix}*")
        return sorted(line for line in listing.splitlines() if line)

    def tracked_files(self, ref: str = "HEAD") -> list[str]:
        """Return the repo-relative paths tracked at ``ref`` (sorted)."""
        listing = self._git("ls-tree", "-r", "--name-only", ref)
        return sorted(line for line in listing.splitlines() if line)

    def commit_message(self, ref: str = "HEAD") -> str:
        """Return the full commit message of ``ref``."""
        return self._git("log", "-1", "--format=%B", ref).rstrip("\n")

    def revisions(self, ref: str = "HEAD") -> list[str]:
        """Return every commit SHA reachable from ``ref``, oldest first.

        The chronological walk order the compliance export reads history in —
        matching the oldest-first convention :mod:`kosha.merge.lineage` uses for
        claim history, so a bundle's git and claim audit trails read the same way.
        """
        listing = self._git("log", "--reverse", "--format=%H", ref)
        return [line for line in listing.splitlines() if line]

    def commit_date(self, ref: str = "HEAD") -> datetime:
        """Return ``ref``'s author date as a timezone-aware :class:`datetime`."""
        return datetime.fromisoformat(self._git("log", "-1", "--format=%aI", ref))

    def remote_url(self, name: str = "origin") -> str | None:
        """Return the configured URL of remote ``name``, or ``None`` if unset.

        Optional bundle metadata (system_design §6): a local-only bundle has no
        remote configured, which is not an error worth raising for.
        """
        result = self._run("remote", "get-url", name, check=False)
        return result.stdout.strip() or None if result.returncode == 0 else None

    def show(self, ref: str, path: str) -> str:
        """Return ``path``'s content as committed at ``ref``."""
        return self._git("show", f"{ref}:{path}")

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
