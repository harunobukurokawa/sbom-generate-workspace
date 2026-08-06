"""
Integration of tree-sitter-bash into xen-sbom-poc parser framework

Provides command parsing for complex shell commands used in Xen build system,
including if-then-else, while loops, pipes, and other shell constructs.
"""

import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from shell_parser_wrapper import TreeSitterBashParser
except ImportError:
    # Fallback if not in correct directory
    TreeSitterBashParser = None


class TreeSitterCommandParser:
    """
    Parser for complex shell commands using tree-sitter-bash

    Handles:
    - if-then-else statements
    - while/for loops
    - Pipe operations
    - Redirections
    - And other shell constructs
    """

    class ParseResult:
        """Result of parsing a command"""

        def __init__(
            self,
            inputs: List[str] = None,
            outputs: List[str] = None,
            parsed_data: Dict[str, Any] = None,
        ):
            self.inputs = inputs or []
            self.outputs = outputs or []
            self.parsed_data = parsed_data or {}

    def __init__(self):
        """Initialize tree-sitter-bash parser"""
        if TreeSitterBashParser is None:
            raise ImportError("tree-sitter-bash parser not available")
        self.ts_parser = TreeSitterBashParser()

    def can_handle(self, command: str) -> bool:
        """
        Check if this parser should handle the command

        Returns True for complex shell commands
        """
        complex_indicators = [
            "if [",
            "then",
            "else",
            "fi",
            "while",
            "do",
            "done",
            "for ",
            " in ",
            " | ",  # pipe
            " && ",
            " || ",  # logical operators
        ]

        return any(indicator in command for indicator in complex_indicators)

    def parse(
        self, command: str, output_file: Optional[str] = None
    ) -> "TreeSitterCommandParser.ParseResult":
        """
        Parse command and extract dependencies

        Args:
            command: Shell command string
            output_file: Expected output file (optional)

        Returns:
            ParseResult with inputs, outputs, parsed_data
        """
        result = self.ts_parser.parse_command(command)

        if not result.get("success"):
            # Fall back to basic extraction
            return self._parse_failed(command, result.get("error", "Unknown error"))

        # Extract I/O from all branches
        all_inputs = set()
        all_outputs = set()

        # Direct I/O
        io_result = result.get("io", {})
        all_inputs.update(io_result.get("inputs", []))
        all_outputs.update(io_result.get("outputs", []))

        # Extract from conditionals
        control_flow = result.get("control_flow", {})

        for if_stmt in control_flow.get("if_statements", []):
            # Process then branch
            if if_stmt.get("then_body"):
                for cmd in if_stmt["then_body"]:
                    branch_result = self._extract_from_command(cmd)
                    all_inputs.update(branch_result[0])
                    all_outputs.update(branch_result[1])

            # Process else branch
            if if_stmt.get("else_body"):
                for cmd in if_stmt["else_body"]:
                    branch_result = self._extract_from_command(cmd)
                    all_inputs.update(branch_result[0])
                    all_outputs.update(branch_result[1])

        # Extract from loops
        for while_stmt in control_flow.get("while_loops", []):
            if while_stmt.get("body"):
                for cmd in while_stmt["body"]:
                    body_result = self._extract_from_command(cmd)
                    all_inputs.update(body_result[0])
                    all_outputs.update(body_result[1])

        # Extract from pipelines
        for pipeline in result.get("pipelines", []):
            for cmd in pipeline:
                cmd_result = self._extract_from_command(cmd)
                all_inputs.update(cmd_result[0])
                all_outputs.update(cmd_result[1])

        # Apply output_file if provided
        if output_file:
            all_outputs.add(output_file)

        return self.ParseResult(
            inputs=sorted(list(all_inputs)),
            outputs=sorted(list(all_outputs)),
            parsed_data={
                "parser": "tree-sitter-bash",
                "control_flow": control_flow,
                "pipelines": result.get("pipelines", []),
                "has_conditionals": bool(control_flow.get("if_statements"))
                or bool(control_flow.get("while_loops")),
                "has_pipes": bool(result.get("pipelines", [])),
            },
        )

    def _extract_from_command(self, cmd: str) -> Tuple[set, set]:
        """Helper to extract I/O from a single command"""
        inputs, outputs = self.ts_parser.extract_inputs_outputs(cmd)
        return set(inputs), set(outputs)

    def _parse_failed(self, command: str, error: str) -> "ParseResult":
        """Fallback when tree-sitter parsing fails"""
        import re

        inputs = set()
        outputs = set()

        # Simple regex-based fallback
        for match in re.finditer(r"<\s*(\S+)", command):
            inputs.add(match.group(1))

        for match in re.finditer(r">\s*(\S+)", command):
            outputs.add(match.group(1))

        return self.ParseResult(
            inputs=sorted(list(inputs)),
            outputs=sorted(list(outputs)),
            parsed_data={
                "parser": "tree-sitter-bash-fallback",
                "error": error,
            },
        )


if __name__ == "__main__":
    # Test
    try:
        parser = TreeSitterCommandParser()

        # Test if-then-else
        cmd = "if [ -f compat.o ]; then ld -r compat.o -o final.o; else ld -r base.o -o final.o; fi"
        print(f"Command: {cmd}")
        print(f"Can handle: {parser.can_handle(cmd)}")

        result = parser.parse(cmd)
        print(f"Inputs: {result.inputs}")
        print(f"Outputs: {result.outputs}")
        print(f"Data: {result.parsed_data}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
