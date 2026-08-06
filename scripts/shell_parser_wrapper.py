"""
Python wrapper for tree-sitter-bash via Node.js subprocess

Provides a Python interface to the Node.js shell_parser.js using subprocess calls.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class TreeSitterBashParser:
    """Wrapper around Node.js tree-sitter-bash parser"""

    def __init__(self, node_js_script_path: Optional[str] = None):
        """
        Initialize parser

        Args:
            node_js_script_path: Path to src/shell_parser.js
        """
        if node_js_script_path is None:
            # Look for shell_parser.js in src directory
            possible_paths = [
                Path(__file__).parent.parent / "src" / "shell_parser.js",
                Path.cwd() / "src" / "shell_parser.js",
            ]
            for path in possible_paths:
                if path.exists():
                    node_js_script_path = str(path)
                    break

            if node_js_script_path is None:
                raise FileNotFoundError("shell_parser.js not found in expected locations")

        self.script_path = str(node_js_script_path)
        self._verify_node_js()

    def _verify_node_js(self) -> None:
        """Verify Node.js is installed"""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError("Node.js not found or not in PATH")
        except FileNotFoundError:
            raise RuntimeError("Node.js not found. Please install Node.js >= v14.0")

    def parse_command(self, command_string: str) -> Dict:
        """
        Parse shell command using tree-sitter-bash

        Args:
            command_string: Shell command to parse

        Returns:
            dict with parse result and analysis
        """
        try:
            result = subprocess.run(
                ["node", self.script_path, command_string],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr,
                    "io": None,
                    "control_flow": None,
                    "pipelines": None,
                }

            # Parse JSON output
            lines = result.stdout.strip().split("\n")

            # First JSON block is parse result
            parse_result = json.loads(lines[0])

            # Second JSON block is analysis result (if successful)
            analysis_result = {}
            if len(lines) > 1 and parse_result.get("success"):
                try:
                    analysis_result = json.loads("\n".join(lines[1:]))
                except json.JSONDecodeError:
                    pass

            return {
                "success": parse_result.get("success", False),
                "error": parse_result.get("error"),
                **analysis_result,  # Merge io, control_flow, pipelines
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Parser timeout (>10s)",
                "io": None,
                "control_flow": None,
                "pipelines": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "io": None,
                "control_flow": None,
                "pipelines": None,
            }

    def extract_inputs_outputs(self, command_string: str) -> Tuple[List[str], List[str]]:
        """
        Extract input/output files from command

        Returns:
            Tuple of (inputs, outputs)
        """
        result = self.parse_command(command_string)
        if result.get("success") and "io" in result:
            io = result["io"]
            return io.get("inputs", []), io.get("outputs", [])
        return [], []

    def is_conditional_command(self, command_string: str) -> bool:
        """Check if command contains conditionals"""
        result = self.parse_command(command_string)
        if not result.get("success"):
            return False

        flow = result.get("control_flow", {})
        return (
            bool(flow.get("if_statements"))
            or bool(flow.get("while_loops"))
            or bool(flow.get("for_loops"))
        )

    def has_pipeline(self, command_string: str) -> bool:
        """Check if command contains pipe operations"""
        result = self.parse_command(command_string)
        if not result.get("success"):
            return False

        pipelines = result.get("pipelines", [])
        return len(pipelines) > 0


if __name__ == "__main__":
    # Demo/test
    try:
        parser = TreeSitterBashParser()

        test_commands = [
            "gcc -c file.c -o file.o",
            "if [ -f out.o ]; then ld -r out.o -o final.o; fi",
            "objdump -h file.o | while read a b; do echo $a; done > out.txt",
        ]

        for cmd in test_commands:
            print(f"\nCommand: {cmd}")
            result = parser.parse_command(cmd)
            print(f"Success: {result.get('success')}")
            if result.get("success"):
                io = result.get("io", {})
                print(f"  Inputs: {io.get('inputs', [])}")
                print(f"  Outputs: {io.get('outputs', [])}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
