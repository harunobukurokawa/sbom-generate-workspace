# Reproduction Runbook (for human re-verification and external-report preparation)

*Whereas `01`–`04` "explain the tool and the design", this document is a
**hands-on, step-by-step runbook for people who reproduce the work themselves**.
Its purposes are: (1) checking the recorded procedure for errors, (2) verifying
that the same or similar results can be obtained, and (3) enabling engineers who
understand the content to explain it to external parties such as the Xen
community. All numbers and warning texts are actual figures transcribed from the
run logs and statistics files under `analysis/`; use them to cross-check against
the results of your own run of this document.*

## 0. Intended audience and how to use this document

- Intended audience: internal members who reproduce this project's procedure
  themselves, and whoever will eventually explain it to the Xen community.
- Each step is presented as "command" → "expected result (actual figures)". If
  your results deviate significantly from the actual figures (e.g. element
  counts are substantially different, or unknown warnings appear), reproduction
  has likely failed; re-check the preconditions for that step (source version,
  build configuration).
- This document covers only the hypervisor core (`xen/`). `tools/`, `libs/`,
  etc. are not yet covered (backlog item B-3 in `worklog/backlog.md`).

## 1. Prerequisites

### 1.1 Verified environment (actual)

Environment in which this procedure was actually run, taken from build
information embedded in `analysis/xen-poc/xen-poc.run.log` (Xen's `compile.h`
generation command):

- OS: Ubuntu 22.04 (`gcc (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`)
- Python: 3.10.12 (KernelSbom **requires Python 3.10 or later**;
  `run-linux-sbom.sh` asserts the version at runtime)
- Linux: equivalent to v7.2-rc1 (master of `torvalds/linux` at the time it was
  fetched)
- Xen: 4.23-unstable (HEAD of `xenbits/xen`, at changeset `f0161d2`)

The procedure should reproduce without needing the exact same versions, but
note that significantly older/newer versions may have changed `.cmd` file
formats or build commands.

### 1.2 Required tools

- `git` (source fetching)
- The standard toolset needed to build the Linux kernel: `gcc`, `make`, `bc`,
  `flex`, `bison`, `libssl-dev`, `libelf-dev`, etc. (any environment that can
  build a normal kernel defconfig is sufficient)
- The toolset needed to build the Xen hypervisor (`gcc`, `make`, binutils)
- `python3` (3.10+), `pytest` (only when running unit tests)

### 1.3 Disk space / time estimates (actual)

| Task                                 | Time taken (actual) | Notes                             |
| ------------------------------------ | -------------------- | ---------------------------------- |
| Fetch Linux source (shallow clone)   | A few minutes (network-dependent) | Shallow unless `FULL=1` is set |
| Fetch Xen source (shallow clone)     | A few minutes (network-dependent) | Same as above                  |
| Linux kernel build + `make sbom`     | **4 min 17 s**       | x86_64 defconfig, out-of-tree      |
| Xen hypervisor build                 | **23 s**             | x86_64_defconfig                   |
| Xen PoC (unmodified tool)            | A few to tens of seconds | Assumes build already done     |
| Xen complete SBOM generation         | A few to tens of seconds | Assumes build already done     |

## 2. Overall flow

```
scripts/fetch-sources.sh
        │
        ▼
scripts/run-linux-sbom.sh  ──────────► Linux-side SBOM, 3 documents (reproduction goal 1)
        │
        ▼
make -C external/xen/xen ... defconfig
make -C external/xen/xen ... -jN        ──► Actual Xen hypervisor build
        │
        ▼
scripts/xen-sbom-poc/run-xen-poc.sh      ──► Xen PoC (unmodified tool, warnings present)
        │
        ▼
scripts/xen-sbom-poc/generate-xen-sbom.sh ──► Xen complete SBOM (zero unknown commands)
        │
        ▼
(Verification) JSON-LD structural check + unit tests
```

## 3. Step 1: Fetch sources

```bash
scripts/fetch-sources.sh          # shallow clone of Linux + Xen
```

- To fetch individually: `scripts/fetch-sources.sh linux` / `scripts/fetch-sources.sh xen`
- Only use `FULL=1 scripts/fetch-sources.sh` if you need full history (e.g. to
  tag), since it takes considerably longer than a shallow clone

**Expected result:**

- `external/linux/.git` and `external/xen/.git` are created
- The `HEAD` commit hash and one log line for each are printed to stdout
- If already cloned, `already present ... (skipping clone)` is printed and the
  clone is skipped (safe to re-run)

## 4. Step 2: Reproducing the Linux KernelSbom

```bash
scripts/run-linux-sbom.sh                 # ARCH=host, DEFCONFIG=defconfig
```

Internally this runs `make defconfig O=kernel_build` then
`make sbom O=kernel_build -j$(nproc)`, and at the end prints a simple
verification (each document's `@graph` element count and `@context`) via a
Python one-liner.

**Expected result (actual figures, x86_64 defconfig, equivalent to v7.2-rc1, 4 min 17 s):**

| Output file                | Size             | Element count    | Breakdown (main types)                                                          |
| --------------------------- | ---------------- | ---------------- | ------------------------------------------------------------------------------- |
| `sbom-source.spdx.json`    | 4,513,615 bytes  | **13,796**        | software_File 7,138 / Relationship 6,611 / simplelicensing_LicenseExpression 43 |
| `sbom-build.spdx.json`     | 27,440,983 bytes | **15,282**        | Relationship 7,378 / software_File 3,977 / build_Build 3,923                    |
| `sbom-output.spdx.json`    | 34,960 bytes      | **60**             | Relationship 27 / software_File 14 / software_Package 13 (bzImage + modules)   |

For all three, confirm from the script's output that `@context` points to
`https://spdx.org/rdf/3.0.1/spdx-context.jsonld`, i.e. SPDX 3.0.1 JSON-LD.

Output location: `external/linux/kernel_build/sbom-{source,build,output}.spdx.json`
(`external/` is git-ignored, so the repository only contains the samples/stats
`analysis/sample-sbom-*.spdx.json` and `analysis/linux-reproduction-stats.md`).

## 5. Step 3: Building the Xen hypervisor

```bash
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
```

**Expected result:**

- `external/xen/xen/xen-syms` (actual: about 26 MB) and `external/xen/xen/xen`
  (about 3.1 MB) are produced
- `external/xen/xen/prelink.o` and its `.cmd` file `.prelink.o.cmd` exist
  (this is the root artifact for the next SBOM-generation stage)
- The full build produces many `.cmd` files (actual: 624). These are the
  inputs to KernelSbom's dependency graph

**Example verification command:**

```bash
ls -la external/xen/xen/prelink.o external/xen/xen/.prelink.o.cmd
```

## 6. Step 4: Xen PoC (baseline verification with unmodified KernelSbom)

```bash
scripts/xen-sbom-poc/run-xen-poc.sh          # ROOT_ARTIFACT=prelink.o (optional)
```

Applies upstream `sbom.py` to the Xen hypervisor **without any modification**,
with `--do-not-fail-on-unknown-build-command` and `--write-output-on-error`.
Output goes to `analysis/xen-poc/`.

**Expected result (actual figures):**

| Output                    | Size   | Element count             | Notes                                                      |
| -------------------------- | ------ | -------------------------- | ------------------------------------------------------------ |
| `sbom-build.spdx.json`    | 3.1 MB | 3,280                       | software_File 1,441 / build_Build 539                       |
| `sbom-output.spdx.json`   | 25 KB  | 12                          | software_Package 1 (`prelink.o`)                            |
| `sbom.used-files.txt`     | 35 KB  | **1,442 files**            | `.c` 419 / `.h` 505 / `.o` 490 / `.S` 23 / `.a` 3           |

- Exit code: **0** (by design, `--do-not-fail-on-unknown-build-command` makes
  the tool exit normally even when unknown commands are present)
- Because this is an in-tree build (`--src-tree == --obj-tree`), an `[INFO]`
  log states that no separate source document is generated (this is expected
  behavior, not an anomaly)

**Expected warnings (known, harmless, 6 categories, 300+ occurrences):**

These are aggregated in the `Summarize warnings:` block at the end of the run
log. Seeing them confirms the run went as expected, and they can be referenced
to external audiences as "known unsupported commands".

1. `Skipped parsing command /usr/bin/python3 ./tools/compat-build-header.py ... because no matching parser was found` (280+ occurrences)
2. `Skipped parsing command mv -f include/compat/xen.h.new include/compat/xen.h because no matching parser was found`
3. `Skipped parsing command mv -f include/compat/xlat.h.new include/compat/xlat.h because no matching parser was found`
4. `Skipped parsing command cat .banner; sed -e ... < include/xen/compile.h.in > ...; mv -f ... include/xen/compile.h because input files in IfBlock 'then' statement are not supported`
5. `Could not infer primary purpose for .../include/hypercall-defs.i` (type inference failure, not a parse failure)

**If the result differs:** if the kinds of unknown commands differ
significantly from the above (e.g. new command types appear), the Xen version
being used has likely drifted from the version recorded here
(4.23-unstable, `f0161d2`) and the build commands may have changed.

## 7. Step 5: Generating the complete Xen SBOM (using runtime-injected Xen extensions)

```bash
scripts/xen-sbom-poc/generate-xen-sbom.sh    # ROOT_ARTIFACT=prelink.o (optional)
```

Before launching upstream `sbom.py` via `runpy`,
`scripts/xen-sbom-poc/gen_xen_sbom.py` calls `xen_parsers.install_xen_extensions()`,
which injects the Xen-specific parsers, the patched `parse_inputs_from_commands`,
and the existence filter. **Upstream `external/linux/scripts/sbom/` itself
remains unmodified.** Unlike Step 4, this runs with fail-on-unknown (a single
unknown command is an error). Output goes to `analysis/xen-full/`.

**Expected result (actual figures):**

- **Exit code 0, zero unknown-command occurrences** (the script prints
  `>> unknown-command occurrences: 0  (target: 0)` and
  `>> RESULT: complete SBOM, zero unknown commands.` at the end)
- Total files covered: **1,519** (+77 over the Step 4 baseline of 1,442)
  - Breakdown: h:506, o:490, c:440, S:24, i:22, lst:20, py:4, a:3, (no ext):2,
    bin:2, gz:1, banner:1, in:1, sed:1
  - Newly captured files are mainly: compat `.i` (22), xlat `.lst` (20), Xen
    codegen `.py` (4), boot `.bin` (2), `include/xen/compile.h.in`, `.banner`,
    and `tools/process-banner.sed`
- Remaining warnings (**harmless, expected**): about 52 occurrences of
  `Could not infer primary purpose for ...` (for things like the
  `compat-build-header.py` script itself and `.i` files — the type just
  cannot be auto-inferred, parsing itself succeeded)

**If exit code is non-zero, or unknown-command occurrences is not zero:**
reproduction has failed. Check whether Step 5 (the build, i.e. Step 3 above)
completed correctly and whether `prelink.o` is up to date (if you rebuilt, make
sure `.cmd` files were also regenerated).

## 8. Verification: running the unit tests

Also run the unit tests for the Xen extension parsers themselves, to confirm
the implementation is not broken.

```bash
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/ -q
```

**Expected result:** all 9 tests pass (as recorded in `worklog/journal.md`).

## 9. Verification: manually inspecting the generated SPDX documents

The same idea `run-linux-sbom.sh` applies automatically on the Linux side can
be applied manually to the Xen-side output as well.

```bash
python3 - <<'PY'
import json
for path in [
    "analysis/xen-full/sbom-build.spdx.json",
    # adjust the path to match where your run actually wrote output
]:
    d = json.load(open(path))
    g = d.get("@graph", [])
    ctx = d.get("@context", [""])
    ver = ctx[0] if isinstance(ctx, list) else ctx
    print(f"{path}: {len(g):,} elements, context={ver}")
    # count per element type
    from collections import Counter
    c = Counter(e.get("type") for e in g)
    for t, n in c.most_common():
        print(f"  {t}: {n}")
PY
```

**Criteria for judging results "the same or similar":**

- `@context` points to `https://spdx.org/rdf/3.0.1/spdx-context.jsonld`
- Per-type element counts roughly match the actual figures recorded in this
  document (some variance is acceptable since the source commit will not be
  identical; a large order-of-magnitude difference, or a type dropping to
  zero, is a sign of trouble)
- No new `[WARNING]` lines appear in the log beyond the "Expected warnings"
  section of this document (especially anything related to `no matching
  parser` or `IfBlock`)

## 10. Known limitations (to state explicitly in any external report)

Even when the reproduction procedure itself succeeds, be aware that the
following are **not yet done / not yet established**, and avoid overstating
them when reporting externally (see `worklog/backlog.md`; status as of the
time this document was written).

- **Validation against an external SPDX validator has not been done**
  (backlog B-1). The current "validity check" is JSON-LD structural checking
  only (presence of `@graph`, element counts); formal schema validation with
  an official SPDX tool (e.g. `pyspdxtools`) has not been performed. This
  requires expanding the custom JSON-LD `@context` as a precondition.
- **`tools/`, `libs/`, `stubdom/` are not covered** (backlog B-3). This
  runbook covers only the hypervisor core (`xen/`).
- **Linking to the Safety Case (backlog B-2) is on hold.** SPDX 3.1's Safety
  Profile is still at Release Candidate stage, and it has not been confirmed
  in writing that the Xen FuSa SIG needs SBOM/SPDX usage.
  `analysis/xen-safety-case-relationships.example.spdx.json` is illustrative
  only and is not automatically linked to the generated SBOM.
- **Verification on arm/arm64 has not been done** (backlog B-6). All
  procedures and figures in this document are for x86_64.
- CI integration (backlog B-4) and upstream contribution (backlog B-5) have
  also not been started.

## 11. Key points for external explanation (reference)

The core narrative to connect when explaining this to the Xen community or
similar external audiences (see the "summary" at the end of
`worklog/journal.md` for detail):

- **Question:** can the SPDX-SBOM tool that landed in Linux v7
  (`scripts/sbom/`) be reused to auto-generate SPDX for Xen itself?
- **Answer (confirmed by reproducing this document):** for the hypervisor
  core, the upstream tool can be applied directly, unmodified (the PoC in
  Step 6). Adding roughly 200 lines of runtime-injected extensions
  (`xen_parsers.py`) yields a complete SBOM with zero unknown commands and
  exit code 0 (Step 7).
- **Rationale:** Xen's `xen/` derives from Linux Kbuild, and `fixdep.c`
  produces `.cmd` files in the same format, so KernelSbom's dependency-graph
  analysis works unchanged.
- **Remaining work:** external validator verification, filling in `tools/`
  and `libs/` coverage, and formalizing the Safety Case link (see Section 10
  above).
