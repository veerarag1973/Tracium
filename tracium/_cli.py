"""Command-line interface for llm-toolkit-schema utilities.

This module provides the ``llm-toolkit-schema`` entry-point command.  It is excluded
from coverage measurement because it is a thin integration shim over the
public library API — all business logic lives in tested library modules.

Entry-point (configured in pyproject.toml)::

    llm-toolkit-schema = "tracium._cli:main"

Sub-commands
------------
``llm-toolkit-schema check-compat <events.json>``
    Load a JSON file containing a list of serialised events and run the
    v1.0 compatibility checklist.  Exits 0 on success, 1 on violations,
    2 on usage/parse errors.

``llm-toolkit-schema list-deprecated``
    Print all event types registered in the global deprecation registry.

``llm-toolkit-schema migration-roadmap [--json]``
    Print the planned v1 → v2 migration roadmap from
    :func:`~tracium.migrate.v2_migration_roadmap`.  Pass
    ``--json`` to emit JSON for machine consumption.

``llm-toolkit-schema check-consumers``
    Assert that all globally registered consumers are compatible with the
    installed schema version.  Exits 0 on success, 1 on incompatibilities.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn


def _cmd_check_compat(args: argparse.Namespace) -> int:
    """Implement the ``check-compat`` sub-command."""
    from tracium.compliance import test_compatibility
    from tracium.event import Event

    path = Path(args.file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(raw, list):
        print("error: JSON file must contain a top-level array of events", file=sys.stderr)
        return 2

    from tracium.exceptions import DeserializationError, SchemaValidationError  # noqa: PLC0415
    try:
        events = [Event.from_dict(item) for item in raw]
    except (DeserializationError, SchemaValidationError, KeyError, TypeError) as exc:
        print(f"error: could not deserialise events: {exc}", file=sys.stderr)
        return 2

    result = test_compatibility(events)

    if result.passed:
        print(
            f"OK — {result.events_checked} event(s) passed all compatibility checks."
        )
        return 0

    print(
        f"FAIL — {len(result.violations)} violation(s) found in "
        f"{result.events_checked} event(s):\n"
    )
    for v in result.violations:
        event_ref = f"[{v.event_id}] " if v.event_id else ""
        print(f"  {event_ref}{v.check_id} ({v.rule}): {v.detail}")

    return 1


def _cmd_list_deprecated(_args: argparse.Namespace) -> int:
    """Implement the ``list-deprecated`` sub-command."""
    from tracium.deprecations import list_deprecated

    notices = list_deprecated()
    if not notices:
        print("No deprecated event types registered.")
        return 0

    print(f"{'Event Type':<50} {'Since':<8} {'Sunset':<8} Replacement")
    print("-" * 90)
    for n in notices:
        repl = n.replacement or "(no replacement)"
        print(f"{n.event_type:<50} {n.since:<8} {n.sunset:<8} {repl}")
    return 0


def _cmd_migration_roadmap(args: argparse.Namespace) -> int:
    """Implement the ``migration-roadmap`` sub-command."""
    from tracium.migrate import v2_migration_roadmap

    roadmap = v2_migration_roadmap()
    if not roadmap:
        print("No migration records found.")
        return 0

    if getattr(args, "json", False):
        output = [
            {
                "event_type": r.event_type,
                "since": r.since,
                "sunset": r.sunset,
                "sunset_policy": r.sunset_policy.value,
                "replacement": r.replacement,
                "migration_notes": r.migration_notes,
                "field_renames": r.field_renames,
            }
            for r in roadmap
        ]
        print(json.dumps(output, indent=2))
        return 0

    print(f"v1 → v2 Migration Roadmap ({len(roadmap)} changes)\n")
    for r in roadmap:
        arrow = f" → {r.replacement}" if r.replacement else " (removed)"
        print(f"  [{r.since}→{r.sunset}] {r.event_type}{arrow}")
        if r.migration_notes:
            import textwrap
            wrapped = textwrap.fill(r.migration_notes, width=72, initial_indent="    ", subsequent_indent="    ")
            print(wrapped)
        if r.field_renames:
            for old, new in r.field_renames.items():
                print(f"    field rename: {old!r} → {new!r}")
        print()
    return 0


def _cmd_check_consumers(_args: argparse.Namespace) -> int:
    """Implement the ``check-consumers`` sub-command."""
    from tracium.consumer import get_registry

    registry = get_registry()
    all_records = registry.all()
    if not all_records:
        print("No consumers registered.")
        return 0

    incompatible = registry.check_compatible()
    if not incompatible:
        print(f"OK — all {len(all_records)} consumer(s) are compatible.")
        return 0

    print(f"INCOMPATIBLE — {len(incompatible)} consumer(s) require a newer schema:\n")
    for tool_name, version in incompatible:
        print(f"  {tool_name!r} requires schema v{version}")
    return 1


def main(argv: list[str] | None = None) -> NoReturn:
    """Entry point for the ``llm-toolkit-schema`` CLI tool."""
    parser = argparse.ArgumentParser(
        prog="llm-toolkit-schema",
        description="llm-toolkit-schema command-line utilities",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # check-compat sub-command
    compat_parser = sub.add_parser(
        "check-compat",
        help="Check a JSON file of events against the v1.0 compatibility checklist",
    )
    compat_parser.add_argument(
        "file",
        metavar="EVENTS_JSON",
        help="Path to a JSON file containing a list of serialised events",
    )

    # list-deprecated sub-command
    sub.add_parser(
        "list-deprecated",
        help="Print all deprecated event types from the global deprecation registry",
    )

    # migration-roadmap sub-command
    roadmap_parser = sub.add_parser(
        "migration-roadmap",
        help="Print the planned v1 → v2 migration roadmap",
    )
    roadmap_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit JSON output for machine consumption",
    )

    # check-consumers sub-command
    sub.add_parser(
        "check-consumers",
        help="Assert all registered consumers are compatible with the installed schema",
    )

    args = parser.parse_args(argv)

    if args.command == "check-compat":
        sys.exit(_cmd_check_compat(args))
    elif args.command == "list-deprecated":
        sys.exit(_cmd_list_deprecated(args))
    elif args.command == "migration-roadmap":
        sys.exit(_cmd_migration_roadmap(args))
    elif args.command == "check-consumers":
        sys.exit(_cmd_check_consumers(args))
    else:
        parser.print_help()
        sys.exit(2)
