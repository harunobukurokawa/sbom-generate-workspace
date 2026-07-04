# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# Xen-specific extensions for the upstream Linux KernelSbom tool.
#
# The upstream tool (external/linux/scripts/sbom) is used UNMODIFIED. This module
# injects, at runtime, the Xen-specific build handling that KernelSbom does not
# yet have, so that the Xen hypervisor SBOM reaches 100% (zero unknown commands).
#
# Three things are injected:
#   1. Command parsers for Xen's compat codegen family (compat-*.py) and `mv`,
#      added to savedcmd_parser.DEFAULT_COMMAND_PARSER_REGISTRY.
#   2. A replacement parse_inputs_from_commands that, for shell `if..then..fi`
#      blocks (used to generate include/xen/compile.h), parses the then-branch
#      inputs instead of dropping them with a warning. Patched on the package so
#      cmd_file (imported later) picks up the new function.
#   3. A hardcoded dependency for compile.h as belt-and-suspenders coverage.
#
# Requires the upstream `sbom` package to be importable (the driver inserts
# external/linux/scripts/sbom onto sys.path before importing this module).

import os
import re
import shlex

import sbom.cmd_graph.savedcmd_parser as savedcmd_pkg
from sbom.cmd_graph.savedcmd_parser import savedcmd_parser
from sbom.cmd_graph.savedcmd_parser.command_parser_registry import CommandParserRegistry
from sbom.cmd_graph.savedcmd_parser.command_splitter import IfBlock, split_commands
from sbom.cmd_graph.savedcmd_parser.tokenizer import (
    CmdParsingError,
    Option,
    Positional,
    tokenize_single_command,
)
from sbom.cmd_graph import hardcoded_dependencies
import sbom.sbom_logging as sbom_logging
from sbom.path_utils import PathStr


# --------------------------------------------------------------------------- #
# Command parsers
# --------------------------------------------------------------------------- #

def _parse_mv_command(command: str) -> list[PathStr]:
    """Parse `mv [-f] src... dst`; the renamed source(s) are the inputs.

    Cannot reuse the upstream cp parser because it rejects options, and Xen's mv
    uses `-f` (e.g. `mv -f include/compat/xen.h.new include/compat/xen.h`).
    """
    parts = tokenize_single_command(command, flag_options=["-f", "-i", "-n", "-v"])
    positionals = [p.value for p in parts if isinstance(p, Positional)]
    # positionals == ["mv", src, ..., dst]; inputs are the sources.
    return positionals[1:-1]


def _parse_compat_tool(command: str) -> list[PathStr]:
    """Parse Xen's compat codegen tools, all of the shape:

        python3 ./tools/compat-<X>.py [args...] [<in] [>out]

    e.g. compat-build-header.py, compat-build-source.py, compat-xlat-header.py.
    Inputs are the stdin-redirected file, the positional file arguments, and the
    generator script itself. Output redirections (`>`/`>>`) and the interpreter
    path are excluded.
    """
    inputs: list[PathStr] = []
    skip_next = False
    for token in shlex.split(command):
        if skip_next:
            skip_next = False
            continue
        if token in (">", ">>"):
            skip_next = True  # skip the following output filename
            continue
        if token == "<":
            continue  # the following token is the stdin file -> keep it
        if token.startswith("<"):
            inputs.append(token[1:])  # stdin redirect -> input
            continue
        if token.startswith(">"):
            continue  # output redirect target -> not an input
        if token.endswith(("python", "python3")) or token.startswith("/usr/"):
            continue  # interpreter, not a source file
        inputs.append(token)
    return [i for i in inputs if i]


def _parse_noop(command: str) -> list[PathStr]:
    """No input files (validation preludes, shell-loop fragments)."""
    return []


def _parse_cat_bare(command: str) -> list[PathStr]:
    """Parse `cat FILE...` with no pipe/redirect (e.g. `cat .banner`). Upstream
    only handles the piped/redirected form, so bare cat leaks. The files are
    inputs."""
    return [
        p.value
        for p in tokenize_single_command(command)
        if isinstance(p, Positional)
    ][1:]


def _parse_binfile(command: str) -> list[PathStr]:
    """Parse Xen's `tools/binfile`, which embeds a blob into an assembly file:

        /bin/sh ./tools/binfile <output.S> <input> <symbol>

    e.g. `... binfile common/config_data.S common/config.gz xen_config_data`.
    Inputs are the blob (the non-.S data file) and the binfile script itself; the
    output `.S` and the symbol name are not inputs.
    """
    positionals = [
        p.value for p in tokenize_single_command(command) if isinstance(p, Positional)
    ]
    result: list[PathStr] = []
    script = next((p for p in positionals if p.endswith("binfile")), None)
    if script:
        result.append(script)
    # blob input = a positional that is a path but not the output .S nor a bare symbol
    result += [
        p for p in positionals
        if "/" in p and not p.endswith(".S") and not p.endswith("binfile")
    ]
    return result


# combine_two_binaries.py file-valued options (x86 boot: combines the base and
# offset 32-bit built-in blobs into an assembly file). --output is the output;
# --gap/--text-diff/--exports are not files.
_COMBINE_FILE_OPTS = {"--script", "--bin1", "--bin2", "--map"}


def _parse_combine_two_binaries(command: str) -> list[PathStr]:
    parts = tokenize_single_command(command)
    inputs = [
        p.value for p in parts
        if isinstance(p, Option) and p.name in _COMBINE_FILE_OPTS and p.value
    ]
    script = [
        p.value for p in parts
        if isinstance(p, Positional) and p.value.endswith(".py")
    ]
    return script + inputs


# Registry entries. Patterns are matched (re.match, anchored at start) before the
# upstream entries, so keep the Xen-specific ones first. `.*` tolerates a leading
# interpreter path.
XEN_COMMAND_PARSERS = [
    (re.compile(r"^mv\b"), _parse_mv_command),
    (re.compile(r".*compat-[\w-]+\.py"), _parse_compat_tool),
    (re.compile(r".*combine_two_binaries\.py"), _parse_combine_two_binaries),
    (re.compile(r".*tools/binfile\b"), _parse_binfile),
    (re.compile(r"^cat\s+[^|>]*$"), _parse_cat_bare),
    # .banner generation (a version string). No source-file provenance; figlet is
    # an optional decorative renderer, so these branches carry no build inputs.
    (re.compile(r".*\|\s*figlet\b"), _parse_noop),
    (re.compile(r"^else\s+echo\b"), _parse_noop),
]


# Xen's *.init.o recipe prepends a section-size validation loop
# (`objdump -h X | while read ...; do case ...; esac; done || exit $?;`) before
# the real `objcopy`. split_commands would shred this shell loop into meaningless
# fragments, so we strip the whole prelude up front. It has no file inputs; the
# real dependency (the source .o) is recovered from the trailing objcopy.
_VALIDATION_PRELUDE = re.compile(
    r"objdump\b.*?\bwhile\b.*?\bdone\b(\s*\|\|\s*exit\s+\S+)?\s*;?\s*",
    re.DOTALL,
)

# Object tree root, set by the driver. When set, parsed inputs are filtered to
# files that actually exist in the tree. Xen's "generate to X.new then `mv` to X"
# idiom and its logical name arguments (e.g. a header *name* passed to a codegen
# script) would otherwise yield references to transient/non-file paths that the
# post-build tool cannot hash. A post-build SBOM should only cite existing files.
OBJ_TREE: str | None = None


def _keep_existing(paths: list[PathStr]) -> list[PathStr]:
    if OBJ_TREE is None:
        return paths
    return [p for p in paths if os.path.exists(os.path.join(OBJ_TREE, p))]


# --------------------------------------------------------------------------- #
# IfBlock-aware parse_inputs_from_commands (for include/xen/compile.h)
# --------------------------------------------------------------------------- #

def xen_parse_inputs_from_commands(
    commands: str,
    fail_on_unknown_build_command: bool,
    registry: CommandParserRegistry | None = None,
) -> list[PathStr]:
    """Drop-in replacement for the upstream function. Identical behaviour except
    that `if..then..fi` blocks have their then-branch inputs *parsed and kept*
    (Xen uses one to generate compile.h) instead of dropped with a warning."""

    def log_error_or_warning(message: str, /, **kwargs: str) -> None:
        if fail_on_unknown_build_command:
            sbom_logging.error(message, **kwargs)
        else:
            sbom_logging.warning(message, **kwargs)

    if registry is None:
        registry = savedcmd_parser.DEFAULT_COMMAND_PARSER_REGISTRY

    # Xen change: strip the *.init.o section-size validation prelude before
    # splitting, so its shell-loop fragments are never parsed as commands.
    commands = _VALIDATION_PRELUDE.sub("", commands)

    input_files: list[PathStr] = []
    for single_command in split_commands(commands):
        if isinstance(single_command, IfBlock):
            # Xen change: keep the then-branch inputs instead of dropping them.
            input_files.extend(
                xen_parse_inputs_from_commands(
                    single_command.then_statement, fail_on_unknown_build_command, registry
                )
            )
            continue

        matched_parser = next((parser for pattern, parser in registry if pattern.match(single_command)), None)
        if matched_parser is None:
            log_error_or_warning(
                "Skipped parsing command {single_command} because no matching parser was found",
                single_command=single_command,
            )
            continue
        try:
            input_files.extend(matched_parser(single_command))
        except (CmdParsingError, IndexError) as e:
            log_error_or_warning(
                "Skipped parsing command {single_command} because of command parsing error: {error_message}",
                single_command=single_command,
                error_message=str(e),
            )

    return _keep_existing([input.strip().rstrip("/") for input in input_files])


# Belt-and-suspenders: also declare compile.h's inputs as hardcoded dependencies.
XEN_HARDCODED_DEPENDENCIES: dict[str, list[str]] = {
    "include/xen/compile.h": [
        "include/xen/compile.h.in",
        ".banner",
        "tools/process-banner.sed",
    ],
}


def install_xen_extensions() -> None:
    """Inject the Xen parsers, the IfBlock-aware parser, and hardcoded deps into
    the already-imported upstream sbom package. Must run before the cmd graph is
    built (and before cmd_file is imported, so it picks up the patched function)."""
    base_entries = list(CommandParserRegistry.create())
    savedcmd_parser.DEFAULT_COMMAND_PARSER_REGISTRY = CommandParserRegistry(
        XEN_COMMAND_PARSERS + base_entries
    )
    # cmd_file does `from sbom.cmd_graph.savedcmd_parser import parse_inputs_from_commands`
    # at its import time, which happens (transitively, via the sbom.cmd_graph
    # package) BEFORE this install runs. So patch the name in cmd_file's own
    # namespace, where it is actually called. Also patch the package attribute for
    # any not-yet-imported consumer.
    savedcmd_pkg.parse_inputs_from_commands = xen_parse_inputs_from_commands
    import sbom.cmd_graph.cmd_file as cmd_file_mod
    cmd_file_mod.parse_inputs_from_commands = xen_parse_inputs_from_commands
    hardcoded_dependencies.HARDCODED_DEPENDENCIES.update(XEN_HARDCODED_DEPENDENCIES)
