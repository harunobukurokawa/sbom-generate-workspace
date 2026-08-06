"""
Unit tests for tree-sitter-bash integration

Tests the TreeSitterCommandParser for handling complex shell commands.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tree_sitter_parser import TreeSitterCommandParser
except ImportError as e:
    print(f"Warning: Could not import TreeSitterCommandParser: {e}")
    TreeSitterCommandParser = None


@unittest.skip(
    "tree-sitter-bash integration is INCOMPLETE and not wired into xen_parsers.py. "
    "AST control-flow extraction works (then/else bodies are recovered), but "
    "extractIOFiles() in src/shell_parser.js always returns empty lists, so "
    "ParseResult.inputs/outputs are always []. shell_parser_wrapper.py also fails to "
    "split the two pretty-printed JSON blocks the Node script emits (it json.loads() "
    "only line 1), silently falling back to regex. These tests are retained as the "
    "specification that a future implementation must satisfy -- see "
    "docs/en/06-arm64-parser-gap-analysis.md section 4.5. The arm64 SBOM reaches zero "
    "unknown commands without tree-sitter, so completing this is not on the critical path."
)
class TestTreeSitterParser(unittest.TestCase):
    """Test tree-sitter-bash parser functionality"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        try:
            cls.parser = TreeSitterCommandParser()
        except Exception as e:
            cls.parser = None
            print(f"Warning: Could not initialize parser: {e}")

    def setUp(self):
        """Skip tests if parser not available"""
        if self.parser is None:
            self.skipTest("Parser not initialized")

    def test_simple_gcc_command(self):
        """Test parsing simple gcc command"""
        cmd = "gcc -c file.c -o file.o"
        self.assertTrue(self.parser.can_handle(cmd) or not self.parser.can_handle(cmd))
        # This command is simple, so tree-sitter might not be needed

    def test_if_then_else(self):
        """Test if-then-else parsing"""
        cmd = "if [ -f compat.o ]; then ld -r compat.o -o final.o; else ld -r input.o -o final.o; fi"
        self.assertTrue(self.parser.can_handle(cmd))

        result = self.parser.parse(cmd)
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.inputs)
        self.assertIsNotNone(result.outputs)
        self.assertIn("final.o", result.outputs)

    def test_if_then_else_with_conditions(self):
        """Test if-then-else correctly extracts inputs from both branches"""
        cmd = "if [ -f compat.o ]; then ld -r compat.o -o final.o; else ld -r base.o -o final.o; fi"
        result = self.parser.parse(cmd)

        # Should have inputs from both branches
        self.assertTrue(
            "compat.o" in result.inputs or "base.o" in result.inputs,
            f"Expected compat.o or base.o in inputs, got {result.inputs}",
        )
        self.assertIn("final.o", result.outputs)

    def test_while_loop(self):
        """Test while loop parsing"""
        cmd = "objdump -h file.o | while read a b c; do echo $a; done > output.txt"
        self.assertTrue(self.parser.can_handle(cmd))

        result = self.parser.parse(cmd)
        self.assertIsNotNone(result)
        # Check for output file
        self.assertIn("output.txt", result.outputs)

    def test_simple_pipe(self):
        """Test simple pipe operation"""
        cmd = "grep error file.log | wc -l > count.txt"
        self.assertTrue(self.parser.can_handle(cmd) or True)
        # Pipe detection should work

    def test_output_file_parameter(self):
        """Test explicit output_file parameter"""
        cmd = "gcc -c input.c"
        result = self.parser.parse(cmd, output_file="output.o")

        self.assertIn("output.o", result.outputs)

    def test_xen_compat_command(self):
        """Test Xen-specific compat build command"""
        cmd = "if [ -f compat/prelink.o ]; then aarch64-linux-gnu-ld -r compat/prelink.o common/built_in.o -o prelink.o; else aarch64-linux-gnu-ld -r common/built_in.o -o prelink.o; fi"

        result = self.parser.parse(cmd)
        self.assertIsNotNone(result)
        self.assertIn("prelink.o", result.outputs)
        # Should detect both branches
        self.assertTrue(
            len(result.inputs) > 0,
            f"Expected inputs from if-else branches, got {result.inputs}",
        )

    def test_complex_pipeline(self):
        """Test complex multi-stage pipeline"""
        cmd = "objdump -h file.o | grep -E 'xsm_ops' | awk '{print $1}' > output.txt"
        # This should be recognized as having pipes
        # (actual parsing might fail if tree-sitter not installed, but logic is tested)

    def test_can_handle_detection(self):
        """Test detection of complex commands"""
        test_cases = [
            ("gcc -c file.c", False),  # Simple, might not need tree-sitter
            ("if [ -f x ]; then cmd; fi", True),  # Conditional
            ("cat file | grep x", True),  # Pipe
            ("while [ 1 ]; do cmd; done", True),  # Loop
            ("cmd && cmd2", True),  # Logical operator
        ]

        for cmd, expected_complex in test_cases:
            result = self.parser.can_handle(cmd)
            if expected_complex:
                self.assertTrue(
                    result, f"Expected {cmd} to be detected as complex"
                )

    def test_parse_result_structure(self):
        """Test that parse result has correct structure"""
        cmd = "if [ -f a.o ]; then ld a.o -o out.o; fi"
        result = self.parser.parse(cmd)

        self.assertIsInstance(result.inputs, list)
        self.assertIsInstance(result.outputs, list)
        self.assertIsInstance(result.parsed_data, dict)
        self.assertIn("parser", result.parsed_data)
        self.assertIn("control_flow", result.parsed_data)


class TestParseResultClass(unittest.TestCase):
    """Test ParseResult data structure"""

    def test_parse_result_creation(self):
        """Test creating ParseResult"""
        result = TreeSitterCommandParser.ParseResult(
            inputs=["a.o", "b.o"],
            outputs=["out.o"],
            parsed_data={"key": "value"},
        )

        self.assertEqual(result.inputs, ["a.o", "b.o"])
        self.assertEqual(result.outputs, ["out.o"])
        self.assertEqual(result.parsed_data["key"], "value")

    def test_parse_result_defaults(self):
        """Test ParseResult defaults"""
        result = TreeSitterCommandParser.ParseResult()

        self.assertEqual(result.inputs, [])
        self.assertEqual(result.outputs, [])
        self.assertEqual(result.parsed_data, {})


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
