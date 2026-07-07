"""Check the public CLI docs against the live argparse command tree."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from kosha.sync.check import SyncMismatch

CLI_REFERENCE_PATH = Path("docs/cli-reference.md")
README_PATH = Path("README.md")


@dataclass(frozen=True)
class CliCommand:
    """One live ``kosha`` command path from argparse."""

    path: tuple[str, ...]

    @property
    def text(self) -> str:
        """Return the command as users type it."""

        return "kosha " + " ".join(self.path)


def check_cli_reference(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Return mismatches between public CLI docs and the live parser."""

    from kosha.cli import build_parser

    commands = live_cli_commands(build_parser())
    mismatches: list[SyncMismatch] = []
    mismatches.extend(_check_cli_reference_doc(repo_root / CLI_REFERENCE_PATH, commands))
    mismatches.extend(_check_readme_cli_overview(repo_root / README_PATH, commands))
    return tuple(mismatches)


def live_cli_commands(parser: argparse.ArgumentParser) -> tuple[CliCommand, ...]:
    """Enumerate top-level and nested subcommands from an argparse parser."""

    return tuple(CliCommand(path) for path in _command_paths(parser))


def render_cli_synopsis(commands: tuple[CliCommand, ...]) -> str:
    """Render the root command synopsis from the live top-level command list."""

    top_level = tuple(command.path[0] for command in commands if len(command.path) == 1)
    return "kosha [--version] [-h] {" + ",".join(top_level) + "} ..."


def _check_cli_reference_doc(
    path: Path, commands: tuple[CliCommand, ...]
) -> tuple[SyncMismatch, ...]:
    if not path.is_file():
        return (_missing_file("cli-reference", path),)
    text = path.read_text(encoding="utf-8")
    details: list[str] = []
    synopsis = render_cli_synopsis(commands)
    if synopsis not in text:
        details.append(f"missing live synopsis: {synopsis}")
    details.extend(
        f"missing live command: {command.text}" for command in commands if command.text not in text
    )
    if not details:
        return ()
    return (
        SyncMismatch(
            surface="cli-reference",
            path=path,
            message="CLI reference does not match the live argparse command tree",
            details=tuple(details),
        ),
    )


def _check_readme_cli_overview(
    path: Path, commands: tuple[CliCommand, ...]
) -> tuple[SyncMismatch, ...]:
    if not path.is_file():
        return (_missing_file("readme-cli-overview", path),)
    text = path.read_text(encoding="utf-8")
    details = tuple(
        f"missing live command: {command.text}" for command in commands if command.text not in text
    )
    if not details:
        return ()
    return (
        SyncMismatch(
            surface="readme-cli-overview",
            path=path,
            message="README CLI overview omits live commands",
            details=details,
        ),
    )


def _command_paths(parser: argparse.ArgumentParser) -> tuple[tuple[str, ...], ...]:
    subparser_action = _subparser_action(parser)
    if subparser_action is None:
        return ()
    paths: list[tuple[str, ...]] = []
    for name, child in subparser_action.choices.items():
        path = (name,)
        paths.append(path)
        paths.extend((name, *tail) for tail in _command_paths(child))
    return tuple(paths)


def _subparser_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _missing_file(surface: str, path: Path) -> SyncMismatch:
    return SyncMismatch(
        surface=surface,
        path=path,
        message="expected public CLI surface is missing",
    )
