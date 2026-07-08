# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A **research + tooling** repository (not a shipping application) whose goal is to
generate an **SPDX 3.0.1 SBOM for the Xen hypervisor** by reusing the SPDX-SBOM
generator merged into the Linux kernel (`scripts/sbom/`, "KernelSbom"). It
supports the **Xen functional safety (FuSa)** effort. Most deliverables are
documents; the code is a thin, runtime-injected extension layer over the
unmodified upstream Linux tool.

Key design principle, enforced throughout: **the upstream Linux KernelSbom is
used UNMODIFIED.** All Xen-specific behavior is injected at runtime (see
Architecture). Do not fork or edit `external/linux/scripts/sbom/`; add to
`scripts/xen-sbom-poc/xen_parsers.py` instead.

## Language & documentation conventions

- **Conversation with the user is in Japanese.** Respond in Japanese.
- Deliverable docs are bilingual: `docs/en/` (English) and `docs/ja/` (Japanese),
  kept in sync. When editing one, update its counterpart.
- The work log (`worklog/`) is **Japanese only**.

### Keep a detailed work log (standing instruction)

A founding requirement of this project (from the very first prompt) is that the
interaction and work are **logged in detail as they happen**, because the log is
the source material for later explaining the effort to external parties (the Xen
community). Treat logging as part of the task, not an afterthought:

- Append a chronological record of what was done and why to `worklog/journal.md`.
- Record non-trivial decisions as ADR-style entries in `worklog/decisions.md`
  (background → decision → rationale).
- `worklog/backlog.md` is the **single source of truth** for remaining work
  (supersedes the scattered "next steps" in docs and journal); update it when the
  set of next steps changes.
- The whole effort is Git-managed; keep these logs in sync with the actual work.

## Setup & common commands

Sources live in `external/` (git-ignored, must be fetched first):

```bash
scripts/fetch-sources.sh          # clone Linux (torvalds) + Xen (xenbits), shallow
scripts/fetch-sources.sh linux    # only one; FULL=1 env for full clone (needed for tags)
```

Reproduce the Linux tool (needs Python 3.10+):

```bash
scripts/run-linux-sbom.sh [ARCH] [DEFCONFIG]   # builds kernel + `make sbom`
# → external/linux/kernel_build/sbom-{source,build,output}.spdx.json
```

Build Xen and generate its SBOM:

```bash
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
scripts/xen-sbom-poc/run-xen-poc.sh          # baseline: UNMODIFIED tool, tolerates unknown commands → analysis/xen-poc/
scripts/xen-sbom-poc/generate-xen-sbom.sh    # complete SBOM: Xen extensions, fail-on-unknown → analysis/xen-full/
```

Run the unit tests for the Xen parsers:

```bash
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/ -q
# single test:
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/test_xen_parsers.py::TestMvParser -q
```

The `PYTHONPATH` must include both the upstream `sbom` package and the
`xen-sbom-poc` dir, because the tests import `xen_parsers`, which imports the
real `sbom.*` modules.

## Architecture

### How KernelSbom works (the mechanism being reused)

KernelSbom builds an SBOM by walking Kbuild `.cmd` files. Each object has a
`.<name>.cmd` file recording the `savedcmd` (the exact shell command that
produced it). The tool parses those commands to discover input files, following
the graph from a **root artifact** back to every source. A registry of
per-command parsers (`sbom/cmd_graph/savedcmd_parser/`) knows how to extract
inputs from `gcc`, `ld`, `cp`, etc. Unknown commands are skipped with a warning
(or, with fail-on-unknown, an error).

For Xen the PoC root is **`prelink.o`**, not `xen-syms`: `xen-syms` is linked by
a two-pass symbol-table recipe that emits no `.cmd` file, whereas `prelink.o`
aggregates every `built_in.o` and has a `.prelink.o.cmd`, covering the
hypervisor core.

### The runtime-injection layer (the actual code in this repo)

`scripts/xen-sbom-poc/gen_xen_sbom.py` is the driver. It:
1. puts the upstream `sbom` dir and `xen-sbom-poc` on `sys.path`,
2. imports `xen_parsers` and calls `install_xen_extensions()` **before** the
   command graph is built,
3. sets `sys.argv` and runs the upstream `sbom.py` via `runpy` under
   `run_name="__main__"`. Because the `sbom.*` modules are shared through
   `sys.modules`, the injected changes persist into the upstream run.

`scripts/xen-sbom-poc/xen_parsers.py` injects three things:
1. **Xen command parsers** prepended to `DEFAULT_COMMAND_PARSER_REGISTRY`
   (`mv`, the `compat-*.py` codegen family, `combine_two_binaries.py`, `binfile`,
   bare `cat`, figlet/else no-ops). Patterns are `re.match`-anchored and Xen
   entries go first.
2. A **replacement `parse_inputs_from_commands`** that (a) keeps the *then-branch*
   inputs of shell `if..then..fi` blocks — Xen uses one to generate
   `include/xen/compile.h` — instead of dropping them, and (b) strips the
   `*.init.o` `objdump | while ... done` validation prelude before splitting.
   This must be patched **both** on the package and in `cmd_file`'s own namespace,
   because `cmd_file` did `from ... import parse_inputs_from_commands` at its
   (earlier) import time.
3. **Hardcoded dependencies** for `compile.h` as belt-and-suspenders coverage.

`OBJ_TREE` gating: when set (by the driver), parsed inputs are filtered to files
that actually exist on disk (`_keep_existing`). Xen's "generate `X.new` then
`mv` to `X`" idiom and logical name arguments would otherwise cite transient /
non-file paths a post-build SBOM cannot hash. Unit tests set `OBJ_TREE = None`
to disable this.

Any change to a parser's input-extraction logic should be mirrored by a case in
`tests/test_xen_parsers.py`, which uses the **exact command strings observed in
the real Xen build** (captured under `analysis/xen-poc/`).

### Outputs & analysis

Generated SBOMs and run logs are kept selectively under `analysis/`
(`xen-poc/` = baseline, `xen-full/` = complete). `analysis/*.example.spdx.json`
and `analysis/sample-*` are illustrative snapshots, not build output. Validation
so far is JSON-LD structural only; external SPDX-tool validation requires
expanding the custom JSON-LD `@context` (a tracked backlog item, B-1).
