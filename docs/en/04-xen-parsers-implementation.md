# Xen Parser Implementation — Reaching a Complete Hypervisor SBOM

*Phase B. Builds on the PoC in `03-xen-spdx-design.md`. Implements the
Xen-specific handling that takes the hypervisor SBOM from ~99% (6 baseline
warnings) to **complete: zero unknown commands, exit 0**, using the upstream
Linux KernelSbom **unmodified**, via runtime injection.*

## 1. Approach: runtime injection (no upstream edits)

`scripts/xen-sbom-poc/xen_parsers.py` installs, at runtime, everything the
upstream tool lacks for Xen. `scripts/xen-sbom-poc/gen_xen_sbom.py` sets it up
and then runs the upstream `sbom.py` via `runpy`, so the upstream package
(`external/linux/scripts/sbom`) is never modified. Run it with
`scripts/xen-sbom-poc/generate-xen-sbom.sh`.

Injection points (all upstream module globals, read per-call):
- **Command parser registry** — `savedcmd_parser.DEFAULT_COMMAND_PARSER_REGISTRY`
  is replaced with `CommandParserRegistry(XEN_COMMAND_PARSERS + base_entries)`
  (Xen entries first so they match first).
- **`parse_inputs_from_commands`** — replaced with an IfBlock/prelude-aware
  version. Because `cmd_file` binds this name at import time (which happens,
  transitively, before install), we patch it **in `cmd_file`'s own namespace**
  (`sbom.cmd_graph.cmd_file.parse_inputs_from_commands`) as well as on the package.
- **Hardcoded dependencies** — `hardcoded_dependencies.HARDCODED_DEPENDENCIES` is
  updated in place.
- **Existence filter** — `xen_parsers.OBJ_TREE` is set by the driver; parsed
  inputs are filtered to files that exist in the tree (see §3).

## 2. Why the gap was bigger than the baseline suggested

The unmodified PoC reported only 6 warnings because it **failed early**: when a
command could not be parsed (e.g. `compat-build-header.py`), the graph stopped
descending into that file's inputs. Each parser we added made the graph go
**deeper**, revealing the next layer of Xen-specific recipes. Reaching zero was
therefore iterative. The recipe families handled:

| Recipe / command | Instances | Handling |
|------------------|-----------|----------|
| `compat-*.py` (build-header, build-source, xlat-header) | ~280 | `_parse_compat_tool` (generic: stdin `<`, positionals, drop `>` and interpreter) |
| `combine_two_binaries.py` (x86 boot) | 2 | `_parse_combine_two_binaries` (file-valued options `--script/--bin1/--bin2/--map`) |
| `tools/binfile` (config blob embed) | 2 | `_parse_binfile` (blob + script; drop output `.S` and symbol) |
| `mv -f X.new X` (generated-header finalise) | many | `_parse_mv_command` (`-f`-aware; source is input) |
| bare `cat FILE` (e.g. `cat .banner`) | — | `_parse_cat_bare` |
| `*.init.o` section-size validation (`objdump\|while;do case;done`) | ~80 | prelude stripped before splitting; real `objcopy` kept |
| `include/xen/compile.h` (`if..then..fi`) | — | IfBlock-aware parser keeps then-branch inputs; also hardcoded deps |
| `.banner` (`if..then echo\|figlet; else echo; fi`) | — | figlet/`else echo` are noop (version string; no source provenance) |

## 3. The existence filter (transient files)

Xen's "generate to `X.new`, then `mv` to `X`" idiom and its logical *name*
arguments (a header name passed to a codegen script) would make parsers cite
paths that do not exist on disk when the post-build SBOM runs — e.g.
`include/compat/xen.h.new` (renamed away) or `compat/xen.h` (a name, not a file).
The upstream tool treats a non-existent dependency as a hard error.

Since a post-build SBOM should only cite files that actually exist, parsed inputs
are filtered against `OBJ_TREE` (`_keep_existing`). This is a general, defensible
rule rather than per-command special-casing, and it removes the transient/name
references cleanly. (A future upstreamable improvement would be to make `mv`
transparent — propagating `X.new`'s provenance onto `X` — but existence filtering
is sufficient here.)

## 4. Result (verified)

`generate-xen-sbom.sh` on Xen 4.23-unstable (x86_64_defconfig, root `prelink.o`),
fail-on-unknown enabled:

- **Exit 0. Unknown-command occurrences: 0.** (baseline: 6)
- Only cosmetic warnings remain (3× "could not infer primary purpose" for
  `.i`/`.py` files).
- **Coverage: 1,519 files** (baseline unmodified: 1,442; **+77**), now including
  22 compat `.i`, 20 xlat `.lst`, 4 Xen codegen `.py`, 2 boot `.bin`,
  `include/xen/compile.h.in`, `.banner`, `tools/process-banner.sed`.
- Valid SPDX 3.0.1 JSON-LD: build 3,554 elements (1,518 `software_File`).
- Samples: `analysis/xen-full/`. Unit tests: `scripts/xen-sbom-poc/tests/`
  (9 tests, all passing).

## 5. Upstreaming note

All Xen handling lives in ~200 lines in `xen_parsers.py`. The command parsers map
cleanly onto the upstream registry's own idiom (`(pattern, parser)` entries) and
`hardcoded_dependencies` map, so they could be contributed upstream as a Xen
architecture extension. The IfBlock-then-input behaviour and the existence filter
are more general improvements worth discussing with the KernelSbom maintainers.
