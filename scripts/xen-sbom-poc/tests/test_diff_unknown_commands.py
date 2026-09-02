# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# Unit tests for diff_unknown_commands.py, which compares two
# unknown-commands.json reports (see xen_parsers.write_unknown_commands_report)
# to flag parser-maintenance regressions ahead of other SBOM work.
#
# Run:
#   PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
#       python3 -m pytest scripts/xen-sbom-poc/tests/test_diff_unknown_commands.py -q

import json
import os
import tempfile
import unittest

import diff_unknown_commands as duc


def _write(tmp, name, report):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f)
    return path


class TestDiffUnknownCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_no_change_returns_zero(self):
        report = {
            "xen_commit": "abc123", "arch": "x86_64", "config_enabled": [],
            "unknown_commands": [{"command": "foo", "reason": "no_matching_parser", "detail": ""}],
        }
        baseline = _write(self.tmp, "baseline.json", report)
        current = _write(self.tmp, "current.json", report)
        self.assertEqual(_run(baseline, current), 0)

    def test_new_unknown_command_returns_one(self):
        baseline = _write(self.tmp, "baseline.json", {
            "xen_commit": "abc123", "arch": "arm64", "config_enabled": ["CONFIG_XSM_FLASK=y"],
            "unknown_commands": [],
        })
        current = _write(self.tmp, "current.json", {
            "xen_commit": "def456", "arch": "arm64", "config_enabled": ["CONFIG_XSM_FLASK=y"],
            "unknown_commands": [{"command": "new-tool --x", "reason": "no_matching_parser", "detail": ""}],
        })
        self.assertEqual(_run(baseline, current), 1)

    def test_resolved_command_alone_returns_zero(self):
        baseline = _write(self.tmp, "baseline.json", {
            "xen_commit": "abc123", "arch": "x86_64", "config_enabled": [],
            "unknown_commands": [{"command": "old-tool", "reason": "no_matching_parser", "detail": ""}],
        })
        current = _write(self.tmp, "current.json", {
            "xen_commit": "abc123", "arch": "x86_64", "config_enabled": [],
            "unknown_commands": [],
        })
        self.assertEqual(_run(baseline, current), 0)

    def test_missing_file_returns_two(self):
        current = _write(self.tmp, "current.json", {"unknown_commands": []})
        self.assertEqual(_run(os.path.join(self.tmp, "does-not-exist.json"), current), 2)


def _run(baseline_path, current_path):
    import sys
    old_argv = sys.argv
    sys.argv = ["diff_unknown_commands.py", baseline_path, current_path]
    try:
        return duc.main()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
