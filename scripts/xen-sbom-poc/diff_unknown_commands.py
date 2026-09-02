#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# diff_unknown_commands.py - Compare two unknown-commands.json reports
# (written by xen_parsers.write_unknown_commands_report, one per
# gen_xen_sbom.py run) to answer: did this change introduce a build command
# the SBOM parser can't handle yet, and does that look config-driven or
# genuinely new?
#
# Usage:
#   diff_unknown_commands.py <baseline.json> <current.json>
#
# Exit codes: 0 = no new unknown commands, 1 = new unknown commands found,
# 2 = usage or read error.

import json
import sys


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _commands(report: dict) -> set[str]:
    return {entry["command"] for entry in report.get("unknown_commands", [])}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    baseline_path, current_path = sys.argv[1], sys.argv[2]
    try:
        baseline = _load(baseline_path)
        current = _load(current_path)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    baseline_cmds = _commands(baseline)
    current_cmds = _commands(current)
    new_cmds = current_cmds - baseline_cmds
    resolved_cmds = baseline_cmds - current_cmds

    print(f">> baseline: {baseline_path} "
          f"(xen_commit={baseline.get('xen_commit')}, arch={baseline.get('arch')})")
    print(f">> current:  {current_path} "
          f"(xen_commit={current.get('xen_commit')}, arch={current.get('arch')})")

    if baseline.get("xen_commit") != current.get("xen_commit"):
        print(f">> NOTE: xen_commit differs ({baseline.get('xen_commit')} -> "
              f"{current.get('xen_commit')}) -- a new unknown command may reflect "
              f"the Makefile at the new commit rather than a config/toolchain effect.")

    config_diff = sorted(
        set(baseline.get("config_enabled", [])) ^ set(current.get("config_enabled", []))
    )
    if config_diff:
        print(f">> NOTE: enabled-config differs: {', '.join(config_diff)} -- "
              f"per ADR-0011, parser gaps have historically tracked config, not arch.")

    if resolved_cmds:
        print(f">> resolved ({len(resolved_cmds)}): no longer unknown")
        for cmd in sorted(resolved_cmds):
            print(f"  - {cmd}")

    if new_cmds:
        print(f">> NEW unknown commands ({len(new_cmds)}): parser update likely needed")
        for cmd in sorted(new_cmds):
            print(f"  + {cmd}")
        return 1

    print(">> RESULT: no new unknown commands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
