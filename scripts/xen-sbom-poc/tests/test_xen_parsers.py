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

import pathlib
import shutil
import tempfile
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


class TestFlaskCodegenParser(unittest.TestCase):
    # Exact commands from the arm64 build (.xsm/flask/include/*.cmd).
    MKFLASK = (
        "/bin/sh ./xsm/flask/policy/mkflask.sh awk xsm/flask/include "
        "./xsm/flask/policy/security_classes ./xsm/flask/policy/initial_sids"
    )
    MKACCESS_VECTOR = (
        "/bin/sh ./xsm/flask/policy/mkaccess_vector.sh awk xsm/flask/include "
        "./xsm/flask/policy/access_vectors"
    )

    def test_mkflask_keeps_script_and_policy_files(self):
        inputs = xen_parsers._parse_flask_codegen(self.MKFLASK)
        self.assertEqual(
            inputs,
            [
                "./xsm/flask/policy/mkflask.sh",
                "./xsm/flask/policy/security_classes",
                "./xsm/flask/policy/initial_sids",
            ],
        )

    def test_mkaccess_vector_keeps_script_and_policy_file(self):
        inputs = xen_parsers._parse_flask_codegen(self.MKACCESS_VECTOR)
        self.assertEqual(
            inputs,
            [
                "./xsm/flask/policy/mkaccess_vector.sh",
                "./xsm/flask/policy/access_vectors",
            ],
        )

    def test_awk_and_output_directory_are_dropped(self):
        # The output dir must not leak: OBJ_TREE's os.path.exists filter accepts
        # directories, so it would survive as a bogus "file" in the SBOM.
        for cmd in (self.MKFLASK, self.MKACCESS_VECTOR):
            inputs = xen_parsers._parse_flask_codegen(cmd)
            self.assertNotIn("awk", inputs)
            self.assertNotIn("xsm/flask/include", inputs)
            self.assertNotIn("/bin/sh", inputs)


class TestXenPatternsDoNotShadowUpstream(unittest.TestCase):
    """The Xen entries are matched before the entire upstream registry, so a loose
    pattern silently steals commands upstream already handles -- a regression that
    emits no warning. These probes are real arm64 build commands that MUST fall
    through to upstream."""

    UPSTREAM_OWNED = (
        # upstream: ^([^\s]+-)?ld\b
        "aarch64-linux-gnu-ld    -EL  --fix-cortex-a53-843419 -r -o prelink.o "
        "common/built_in.o drivers/built_in.o lib/built_in.o xsm/built_in.o "
        "arch/arm/built_in.o --start-group arch/arm/arm64/lib/lib.a lib/lib.a --end-group",
        # upstream: ^([^\s]+-)?(gcc|clang)\b -- note the "build" substring in the
        # include path, which a `.*ld\b` pattern would wrongly match.
        "aarch64-linux-gnu-gcc -c common/device-tree/dom0less-build.c "
        "-o common/device-tree/dom0less-build.o",
        # upstream: ^([^\s]+-)?objcopy\b
        "aarch64-linux-gnu-objcopy -O binary -S xen-syms xen",
    )

    def test_no_xen_pattern_claims_an_upstream_command(self):
        for probe in self.UPSTREAM_OWNED:
            stealer = next(
                (fn for pat, fn in xen_parsers.XEN_COMMAND_PARSERS if pat.match(probe)),
                None,
            )
            self.assertIsNone(
                stealer,
                f"{stealer.__name__ if stealer else ''} shadows upstream for: {probe[:70]}",
            )


class _CapturedWarnings:
    """Swap sbom_logging.warning for a recorder, restoring it afterwards."""

    def __enter__(self):
        self.calls = []
        self._orig = xen_parsers.sbom_logging.warning
        xen_parsers.sbom_logging.warning = lambda tmpl, /, **kw: self.calls.append(
            (tmpl, kw)
        )
        return self

    def __exit__(self, *exc):
        xen_parsers.sbom_logging.warning = self._orig
        return False


class TestKeepExistingWarnsOnTotalDrop(unittest.TestCase):
    """A wrong --obj-tree makes every parsed input resolve to a nonexistent path;
    _keep_existing() used to return [] in silence, which made the misconfiguration
    look like a parser defect. See docs/*/07 section 2.1."""

    def setUp(self):
        self._saved = xen_parsers.OBJ_TREE
        self.tmp = tempfile.mkdtemp()
        # One real file to allow "partial drop" cases.
        pathlib.Path(self.tmp, "real.o").write_bytes(b"")

    def tearDown(self):
        xen_parsers.OBJ_TREE = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_warns_when_every_input_is_dropped(self):
        xen_parsers.OBJ_TREE = self.tmp
        with _CapturedWarnings() as cap:
            kept = xen_parsers._keep_existing(["ghost_a.o", "ghost_b.o"])
        self.assertEqual(kept, [])
        self.assertEqual(len(cap.calls), 1, "expected exactly one warning")
        # The message must name the offending paths and the obj-tree to be actionable.
        _, kwargs = cap.calls[0]
        self.assertEqual(kwargs["count"], "2")
        self.assertEqual(kwargs["obj_tree"], self.tmp)
        self.assertIn("ghost_a.o", kwargs["paths"])

    def test_silent_on_partial_drop(self):
        # Xen's "generate X.new then mv to X" idiom legitimately drops some inputs.
        xen_parsers.OBJ_TREE = self.tmp
        with _CapturedWarnings() as cap:
            kept = xen_parsers._keep_existing(["real.o", "transient.new"])
        self.assertEqual(kept, ["real.o"])
        self.assertEqual(cap.calls, [])

    def test_silent_on_empty_input(self):
        # Parsers that legitimately return no inputs (_parse_noop) must not warn.
        xen_parsers.OBJ_TREE = self.tmp
        with _CapturedWarnings() as cap:
            self.assertEqual(xen_parsers._keep_existing([]), [])
        self.assertEqual(cap.calls, [])

    def test_no_filtering_and_no_warning_when_obj_tree_unset(self):
        xen_parsers.OBJ_TREE = None
        with _CapturedWarnings() as cap:
            kept = xen_parsers._keep_existing(["ghost.o"])
        self.assertEqual(kept, ["ghost.o"])
        self.assertEqual(cap.calls, [])


class TestObjTreeValidation(unittest.TestCase):
    """Catch the "passed the repository root instead of <xen>/xen" mistake up front,
    rather than after a full run produces a one-file SBOM."""

    def setUp(self):
        self._saved = xen_parsers.OBJ_TREE
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        xen_parsers.OBJ_TREE = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_silent_for_a_configured_build_directory(self):
        pathlib.Path(self.tmp, ".config").write_text("CONFIG_ARM64=y\n")
        xen_parsers.OBJ_TREE = self.tmp
        with _CapturedWarnings() as cap:
            xen_parsers._validate_obj_tree()
        self.assertEqual(cap.calls, [])

    def test_detects_repository_root_and_suggests_the_hypervisor_dir(self):
        # Layout: <root>/xen/.config exists, <root>/.config does not.
        nested = pathlib.Path(self.tmp, "xen")
        nested.mkdir()
        (nested / ".config").write_text("CONFIG_ARM64=y\n")
        xen_parsers.OBJ_TREE = self.tmp
        with _CapturedWarnings() as cap:
            xen_parsers._validate_obj_tree()
        self.assertEqual(len(cap.calls), 1)
        self.assertEqual(cap.calls[0][1]["suggestion"], str(nested))

    def test_warns_when_no_config_anywhere(self):
        xen_parsers.OBJ_TREE = self.tmp
        with _CapturedWarnings() as cap:
            xen_parsers._validate_obj_tree()
        self.assertEqual(len(cap.calls), 1)
        self.assertNotIn("suggestion", cap.calls[0][1])

    def test_silent_when_obj_tree_unset(self):
        xen_parsers.OBJ_TREE = None
        with _CapturedWarnings() as cap:
            xen_parsers._validate_obj_tree()
        self.assertEqual(cap.calls, [])


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
            TestFlaskCodegenParser.MKFLASK,
            TestFlaskCodegenParser.MKACCESS_VECTOR,
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
