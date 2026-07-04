# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# Unit tests for the Xen KernelSbom extensions (xen_parsers.py), using the exact
# command strings observed in the Xen hypervisor build (analysis/xen-poc/).
#
# Run:
#   PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
#       python3 -m pytest scripts/xen-sbom-poc/tests/ -q
# or with unittest:
#   PYTHONPATH=... python3 -m unittest discover -s scripts/xen-sbom-poc/tests

import unittest

import xen_parsers
import sbom.cmd_graph.savedcmd_parser as savedcmd_pkg
from sbom.cmd_graph.savedcmd_parser import savedcmd_parser
from sbom.cmd_graph import hardcoded_dependencies


class TestCompatToolParser(unittest.TestCase):
    def test_build_header_stdin_and_positional(self):
        cmd = (
            "/usr/bin/python3 ./tools/compat-build-header.py "
            "<include/compat/xen.i compat/xen.h >>include/compat/xen.h.new"
        )
        inputs = xen_parsers._parse_compat_tool(cmd)
        self.assertIn("include/compat/xen.i", inputs)      # stdin redirect
        self.assertIn("compat/xen.h", inputs)              # positional data arg
        self.assertIn("./tools/compat-build-header.py", inputs)  # the script
        self.assertNotIn("/usr/bin/python3", inputs)       # interpreter dropped
        self.assertNotIn("include/compat/xen.h.new", inputs)  # output dropped
        self.assertFalse(any(i.startswith((">", "<")) for i in inputs))

    def test_build_source_stdin(self):
        cmd = (
            "/usr/bin/python3 ./tools/compat-build-source.py ./include/xlat.lst "
            "<include/public/xen.h >include/compat/xen.c.new"
        )
        inputs = xen_parsers._parse_compat_tool(cmd)
        self.assertIn("include/public/xen.h", inputs)      # stdin redirect
        self.assertIn("./include/xlat.lst", inputs)        # positional
        self.assertNotIn("include/compat/xen.c.new", inputs)

    def test_xlat_header_no_stdin(self):
        cmd = (
            "/usr/bin/python3 ./tools/compat-xlat-header.py include/compat/xen.h "
            "include/compat/.xlat/xen.lst > include/compat/.xlat/xen.h.new"
        )
        inputs = xen_parsers._parse_compat_tool(cmd)
        self.assertIn("include/compat/xen.h", inputs)
        self.assertIn("include/compat/.xlat/xen.lst", inputs)
        self.assertNotIn("include/compat/.xlat/xen.h.new", inputs)  # space-separated output


class TestBinfileParser(unittest.TestCase):
    def test_binfile_input_is_blob_and_script(self):
        cmd = "/bin/sh ./tools/binfile  common/config_data.S common/config.gz xen_config_data"
        inputs = xen_parsers._parse_binfile(cmd)
        self.assertIn("common/config.gz", inputs)          # blob input
        self.assertIn("./tools/binfile", inputs)           # the script
        self.assertNotIn("common/config_data.S", inputs)   # output .S excluded
        self.assertNotIn("xen_config_data", inputs)        # symbol name excluded


class TestCombineTwoBinariesParser(unittest.TestCase):
    def test_file_valued_options_only(self):
        cmd = (
            "/usr/bin/python3 ./tools/combine_two_binaries.py --gap 0x010200 "
            "--text-diff 0x408020 --script arch/x86/boot/build32.base.lds "
            "--bin1 arch/x86/boot/built-in-32.base.bin "
            "--bin2 arch/x86/boot/built-in-32.offset.bin "
            "--map arch/x86/boot/built-in-32.base.map "
            "--exports cmdline_parse_early,reloc --output arch/x86/boot/built-in-32.S"
        )
        inputs = xen_parsers._parse_combine_two_binaries(cmd)
        self.assertIn("arch/x86/boot/build32.base.lds", inputs)         # --script
        self.assertIn("arch/x86/boot/built-in-32.base.bin", inputs)     # --bin1
        self.assertIn("arch/x86/boot/built-in-32.offset.bin", inputs)   # --bin2
        self.assertIn("arch/x86/boot/built-in-32.base.map", inputs)     # --map
        self.assertIn("./tools/combine_two_binaries.py", inputs)        # script
        self.assertNotIn("arch/x86/boot/built-in-32.S", inputs)         # --output
        self.assertNotIn("0x010200", inputs)                            # --gap value
        self.assertNotIn("cmdline_parse_early,reloc", inputs)           # --exports


class TestIfBlockAndPrelude(unittest.TestCase):
    def setUp(self):
        xen_parsers.install_xen_extensions()  # ensure Xen parsers (cat, mv, ...) are registered
        xen_parsers.OBJ_TREE = None           # disable existence filtering for unit tests

    def test_ifblock_then_inputs_are_kept(self):
        # if..then..fi (compile.h): then-branch inputs must be captured, not dropped.
        cmd = (
            "if [ ! -r x ]; then cat .banner; sed -e 's/a/b/' < include/xen/compile.h.in "
            "> include/xen/.compile.h.tmp; mv -f include/xen/.compile.h.tmp include/xen/compile.h; fi"
        )
        inputs = xen_parsers.xen_parse_inputs_from_commands(cmd, False)
        self.assertIn("include/xen/compile.h.in", inputs)
        self.assertIn(".banner", inputs)

    def test_validation_prelude_is_stripped(self):
        cmd = (
            "objdump -h a.o | while read i n s r; do case \"$n\" in .text) ;; esac; done "
            "|| exit $?; objcopy --rename-section .rodata=.init.rodata a.o a.init.o"
        )
        inputs = xen_parsers.xen_parse_inputs_from_commands(cmd, False)
        self.assertIn("a.o", inputs)   # objcopy input survives; loop fragments gone


class TestMvParser(unittest.TestCase):
    def test_mv_returns_source(self):
        cmd = "mv -f include/compat/xen.h.new include/compat/xen.h"
        self.assertEqual(
            xen_parsers._parse_mv_command(cmd), ["include/compat/xen.h.new"]
        )


class TestInstallInjection(unittest.TestCase):
    def test_install_registers_parsers_and_hardcoded_deps(self):
        xen_parsers.install_xen_extensions()

        # mv and compat-build-header now resolve to a parser (not None).
        registry = savedcmd_parser.DEFAULT_COMMAND_PARSER_REGISTRY
        for probe in (
            "mv -f a.new a",
            "/usr/bin/python3 ./tools/compat-build-header.py <x.i y.h >>z.new",
            "/usr/bin/python3 ./tools/compat-build-source.py ./x.lst <a.h >b.c.new",
            "/usr/bin/python3 ./tools/compat-xlat-header.py a.h b.lst > c.h.new",
        ):
            matched = next((p for pat, p in registry if pat.match(probe)), None)
            self.assertIsNotNone(matched, f"no parser matched: {probe}")

        # The IfBlock-aware parser is installed on the package.
        self.assertIs(
            savedcmd_pkg.parse_inputs_from_commands,
            xen_parsers.xen_parse_inputs_from_commands,
        )

        # compile.h hardcoded dependency is present.
        self.assertIn(
            "include/xen/compile.h", hardcoded_dependencies.HARDCODED_DEPENDENCIES
        )
        self.assertIn(
            "include/xen/compile.h.in",
            hardcoded_dependencies.HARDCODED_DEPENDENCIES["include/xen/compile.h"],
        )


if __name__ == "__main__":
    unittest.main()
