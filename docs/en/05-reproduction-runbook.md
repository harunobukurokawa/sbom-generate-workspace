# Reproduction Runbook (for hands-on verification and external reporting)

*Where `01`–`04` explain the tooling and the design, this document is an **end-to-end
runbook for someone actually reproducing the work**. Its goals are (1) to check that
the recorded procedure contains no errors, (2) to verify that the same or comparable
results are obtained, and (3) to let the reader understand the work well enough to
explain it to external engineers such as the Xen community. All figures and warning
strings are transcribed from the run logs and statistics files under `analysis/`;
compare them against what your own run produces.*

## 0. Audience and how to use this

- Intended readers: team members reproducing this project's procedure themselves, and
  whoever will eventually present it to the Xen community.
- Each step is given as "command" followed by "expected result (measured)". If your
  result diverges substantially from the measured value (element counts far off,
  unfamiliar warnings, and so on), reproduction has probably failed — revisit that
  step's prerequisites (source revision, build configuration).
- This runbook covers only the hypervisor proper (`xen/`). `tools/`, `libs/` and
  friends are not yet supported (backlog B-3 in `worklog/backlog.md`).

## 1. Prerequisites

### 1.1 Verified environment (measured)

Taken from the build information embedded in `analysis/xen-poc/xen-poc.run.log` (Xen's
`compile.h` generation command), i.e. the environment in which this procedure was
actually carried out:

- OS: Ubuntu 22.04 (`gcc (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`)
- Python: 3.10.12 (KernelSbom **requires Python 3.10 or newer**; `run-linux-sbom.sh`
  asserts the version at runtime)
- Linux: equivalent to v7.2-rc1 (master at the time `torvalds/linux` was fetched)
- Xen: 4.23-unstable (`xenbits/xen` HEAD, at changeset `f0161d2`)

The procedure should reproduce without exactly matching versions, but note that on
substantially older or newer revisions the `.cmd` format or the build commands may
have changed.

### 1.2 Required tools

- `git` (fetching sources)
- The standard toolset for building a Linux kernel: `gcc`, `make`, `bc`, `flex`,
  `bison`, `libssl-dev`, `libelf-dev`, etc. (any environment where an ordinary kernel
  defconfig build succeeds is sufficient)
- The toolset for building the Xen hypervisor (`gcc`, `make`, binutils)
- `python3` (3.10+), and `pytest` (only for running the unit tests)

### 1.3 Disk and time estimates (measured)

| Task | Time (measured) | Note |
| ---- | --------------- | ---- |
| Fetch Linux sources (shallow clone) | a few minutes (network-bound) | shallow unless `FULL=1` |
| Fetch Xen sources (shallow clone) | a few minutes (network-bound) | same |
| Linux kernel build + `make sbom` | **4 min 17 s** | x86_64 defconfig, out-of-tree |
| Xen hypervisor build | **23 s** | x86_64_defconfig |
| Xen PoC (unmodified tool) | seconds to tens of seconds | assumes the build is done |
| Xen full SBOM generation | seconds to tens of seconds | assumes the build is done |
| **arm64** hypervisor build | **8.0 s** | `arm64_defconfig`, true clean build after `make clean`, `-j12` |
| **arm64** SBOM generation | **0.8 s** | assumes the build is done; parses 303 `.cmd` files |

The two arm64 rows were measured on a 12-core machine (after confirming that
`make clean` really removes `prelink.o`, the `.cmd` files and `built_in.o`). The
hypervisor proper is small, so both its build and its SBOM generation are orders of
magnitude faster than the Linux kernel's.

## 2. Overall flow

```
scripts/fetch-sources.sh
        │
        ▼
scripts/run-linux-sbom.sh  ──────────► 3 SBOM documents for Linux (reproduction goal 1)
        │
        ▼
make -C external/xen/xen ... defconfig
make -C external/xen/xen ... -jN        ──► real Xen hypervisor build
        │
        ▼
scripts/xen-sbom-poc/run-xen-poc.sh      ──► Xen PoC (unmodified tool, warnings expected)
        │
        ▼
scripts/xen-sbom-poc/generate-xen-sbom.sh ──► full Xen SBOM (zero unknown commands)
        │
        ▼
(step 6) arm64 cross-build + SBOM       ──► arm64 SBOM (zero unknown commands)
        │
        ▼
(verification) JSON-LD structure check + unit tests
```

Steps 1–5 target x86_64; step 6 targets arm64. Step 6 depends only on step 1
(fetching sources) and can be run independently of steps 2–5.

## 3. Step 1: fetch the sources

```bash
scripts/fetch-sources.sh          # shallow clone Linux + Xen
```

- To fetch one at a time: `scripts/fetch-sources.sh linux` /
  `scripts/fetch-sources.sh xen`
- Only when full history is needed (e.g. to create tags):
  `FULL=1 scripts/fetch-sources.sh` (considerably slower than a shallow clone)

**Expected result:**

- `external/linux/.git` and `external/xen/.git` are created
- stdout shows each repository's `HEAD` commit hash and a one-line log
- If already cloned, it prints `already present ... (skipping clone)` and skips
  (re-running is safe)

## 4. Step 2: reproduce Linux KernelSbom

```bash
scripts/run-linux-sbom.sh                 # ARCH=host, DEFCONFIG=defconfig
```

Internally this runs `make defconfig O=kernel_build` then
`make sbom O=kernel_build -j$(nproc)`, and finishes by printing a quick check (each
document's `@graph` element count and its `@context`) via a Python one-liner.

**Expected result (measured: x86_64 defconfig, ~v7.2-rc1, 4 min 17 s):**

| Output file | Size | Elements | Main breakdown |
| ----------- | ---- | -------- | -------------- |
| `sbom-source.spdx.json` | 4,513,615 bytes | **13,796** | software_File 7,138 / Relationship 6,611 / simplelicensing_LicenseExpression 43 |
| `sbom-build.spdx.json` | 27,440,983 bytes | **15,282** | Relationship 7,378 / software_File 3,977 / build_Build 3,923 |
| `sbom-output.spdx.json` | 34,960 bytes | **60** | Relationship 27 / software_File 14 / software_Package 13 (bzImage + modules) |

Confirm from the script's output that each is SPDX 3.0.1 JSON-LD whose `@context`
points at `https://spdx.org/rdf/3.0.1/spdx-context.jsonld`.

Output location: `external/linux/kernel_build/sbom-{source,build,output}.spdx.json`.
Because `external/` is git-ignored, the repository only carries the samples and
statistics: `analysis/sample-sbom-*.spdx.json` and
`analysis/linux-reproduction-stats.md`.

## 5. Step 3: build the Xen hypervisor

```bash
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
```

**Expected result:**

- `external/xen/xen/xen-syms` (measured: ~26 MB) and `external/xen/xen/xen` (~3.1 MB)
  are produced
- `external/xen/xen/prelink.o` and its `.cmd` file `.prelink.o.cmd` exist (this is the
  root artifact for the next stage's SBOM generation)
- The build produces many `.cmd` files (measured: 624). These are the input to
  KernelSbom's dependency graph

**Example check:**

```bash
ls -la external/xen/xen/prelink.o external/xen/xen/.prelink.o.cmd
```

## 6. Step 4: Xen PoC (baseline with unmodified KernelSbom)

```bash
scripts/xen-sbom-poc/run-xen-poc.sh          # ROOT_ARTIFACT=prelink.o (optional)
```

Applies the upstream `sbom.py` to the Xen hypervisor **without changing it at all**,
adding `--do-not-fail-on-unknown-build-command` and `--write-output-on-error`. Output
goes to `analysis/xen-poc/`.

**Expected result (measured):**

| Output | Size | Elements | Notes |
| ------ | ---- | -------- | ----- |
| `sbom-build.spdx.json` | 3.1 MB | 3,280 | software_File 1,441 / build_Build 539 |
| `sbom-output.spdx.json` | 25 KB | 12 | software_Package 1 (`prelink.o`) |
| `sbom.used-files.txt` | 35 KB | **1,442 files** | `.c` 419 / `.h` 505 / `.o` 490 / `.S` 23 / `.a` 3 |

- exit code: **0** (by design: `--do-not-fail-on-unknown-build-command` lets the tool
  exit normally even with unknown commands)
- Because this is an in-tree build (`--src-tree == --obj-tree`), an `[INFO]` log states
  that no separate source document is produced (as specified; not an anomaly)

**Expected warnings (known, harmless; 6 families, 300+ occurrences):**

These are collected under `Summarize warnings:` at the end of the run log. Seeing them
means things are as expected, and they can be cited externally as "known unhandled
commands".

1. `Skipped parsing command /usr/bin/python3 ./tools/compat-build-header.py ... because no matching parser was found` (280+ occurrences)
2. `Skipped parsing command mv -f include/compat/xen.h.new include/compat/xen.h because no matching parser was found`
3. `Skipped parsing command mv -f include/compat/xlat.h.new include/compat/xlat.h because no matching parser was found`
4. `Skipped parsing command cat .banner; sed -e ... < include/xen/compile.h.in > ...; mv -f ... include/xen/compile.h because input files in IfBlock 'then' statement are not supported`
5. `Could not infer primary purpose for .../include/hypercall-defs.i` (type could not be inferred; parsing did not fail)

**If your result differs:** if the set of unknown commands differs substantially from
the above (e.g. new command kinds appear), your Xen revision is probably far from the
recorded one (4.23-unstable, `f0161d2`) and its build commands have changed.

## 7. Step 5: full Xen SBOM generation (using the runtime-injected Xen extensions)

```bash
scripts/xen-sbom-poc/generate-xen-sbom.sh    # ROOT_ARTIFACT=prelink.o (optional)
```

Before launching the upstream `sbom.py` through `runpy`,
`scripts/xen-sbom-poc/gen_xen_sbom.py` calls
`xen_parsers.install_xen_extensions()` to inject the Xen-specific parsers, the improved
`parse_inputs_from_commands`, and the existence filter. **The upstream
`external/linux/scripts/sbom/` itself stays unmodified.** Unlike step 4, this runs with
fail-on-unknown (a single unknown command is an error). Output goes to
`analysis/xen-full/`.

**Expected result (measured):**

- **exit code 0, zero unknown-command occurrences** (the script prints
  `>> unknown-command occurrences: 0  (target: 0)` and
  `>> RESULT: complete SBOM, zero unknown commands.` at the end)
- Files covered: **1,519** (up 77 from step 4's baseline of 1,442)
  - Breakdown: h:506, o:490, c:440, S:24, i:22, lst:20, py:4, a:3, (no ext):2, bin:2,
    gz:1, banner:1, in:1, sed:1
  - Newly captured, mainly: compat `.i` (22), xlat `.lst` (20), Xen codegen `.py` (4),
    boot `.bin` (2), `include/xen/compile.h.in`, `.banner`,
    `tools/process-banner.sed`
- Remaining warnings (**harmless, expected**): about 52 of the form
  `Could not infer primary purpose for ...` (e.g. `compat-build-header.py` itself and
  `.i` files — only the type cannot be inferred automatically; parsing succeeded)

**If the exit code is non-zero, or unknown-command occurrences is not 0:**
reproduction has failed. Check that step 3 (the build) completed correctly and that
`prelink.o` is current (if you rebuilt, that the `.cmd` files were regenerated too).

## 8. Step 6: reproduce on arm64 (cross-build)

Steps 1–5 target x86_64. This section does the same on arm64. The detailed analysis is
in `docs/en/06-arm64-parser-gap-analysis.md`.

### 8.1 Additional tools

```bash
sudo apt-get install -y gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu
```

Measured with `aarch64-linux-gnu-gcc 11.4.0` and `aarch64-linux-gnu-ld`
(binutils 2.38). Node.js is **not** required (it is only for the tree-sitter
experiment and is unused by SBOM generation).

### 8.2 Build

```bash
make -C external/xen/xen XEN_TARGET_ARCH=arm64 arm64_defconfig
CROSS_COMPILE=aarch64-linux-gnu- make -C external/xen/xen XEN_TARGET_ARCH=arm64 -j"$(nproc)"
```

**Expected result:**

- `external/xen/xen/prelink.o` (measured: ~16 MB) and `.prelink.o.cmd` exist
- The `.cmd` file count is **303** (fewer than x86_64's 624, because a different set of
  features is enabled)

> **Important: do not run `make clean` after building.** This tool hashes the
> intermediate files on disk (`common/built_in.o` and friends) *after* the build, so
> cleaning makes SBOM generation fail.

### 8.3 Generate the SBOM

```bash
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom  external/xen/xen  analysis/arm64  prelink.o
```

> **The single most important detail: the second argument is the hypervisor directory
> (`external/xen/xen`), not the root of the Xen repository (`external/xen`).** Paths
> inside `.cmd` files are recorded relative to the hypervisor build directory, so being
> off by even one level makes every input resolve to a nonexistent path and yields
> **an SBOM containing exactly one tracked file**. This actually happened, and
> identifying the cause took considerable time (see section 2 of
> `docs/en/06-arm64-parser-gap-analysis.md`).
>
> A warning now detects this mistake. If you see the following, re-check the second
> argument:
>
> ```
> [WARNING] obj-tree <...> has no .config, but <...>/xen/.config does.
>           ... pass <...>/xen instead.
> ```

**Expected result (measured):**

- `analysis/arm64/sbom-build.spdx.json`: **1,951 elements** (~1.4 MB)
  - `software_File` 894 / `Relationship` 758 / `build_Build` 290 /
    `simplelicensing_LicenseExpression` 5 / 4 others
- `analysis/arm64/sbom.used-files.txt`: `wc -l` prints **894** (there is no trailing
  newline; the file actually lists **895 paths**)
  - By extension: `.h` 359 / `.c` 222 / `.o` 281 / `.S` 19 / `.a` 2
  - 894 of the 895 become `software_File` elements. The one difference is `prelink.o`,
    which is the root artifact and therefore lives in `sbom-output.spdx.json`
  - An entry `../../../usr/bin/dash` appears (the real path behind `/bin/sh`). That is
    the shell which ran the codegen scripts, tracked as a dependency — not an anomaly
- Unknown commands: **0**
- Expected warnings:
  - `All 1 parsed input(s) were dropped ... .banner.tmp` — normal if it appears
    **only once** (it is a temporary file). Many occurrences suggest the second
    argument is at the wrong level
  - `Could not infer primary purpose for ...` — 10 occurrences measured (only the type
    could not be inferred)

Because `gen_xen_sbom.py` runs with fail-on-unknown, **the mere existence of the output
files proves there were zero unknown commands.**

**Example checks:**

```bash
wc -l analysis/arm64/sbom.used-files.txt
grep -E "flask/policy" analysis/arm64/sbom.used-files.txt
```

The latter lists five XSM/FLASK policy files (`mkflask.sh`, `security_classes`,
`initial_sids`, `mkaccess_vector.sh`, `access_vectors`). They are the evidence that the
parser added for arm64 is working, and they do not appear in the x86_64 SBOM (because
`arm64_defconfig` enables XSM/FLASK).

### 8.4 What actually differs from x86_64

arm64 required exactly **one additional parser, for XSM/FLASK policy code generation**.
That is a **configuration** difference rather than an architecture difference: the
`aarch64-linux-gnu-*` compiler and linker commands themselves are handled by the
upstream parsers as-is. For the details and the measurement method, see
`docs/en/06-arm64-parser-gap-analysis.md`.

## 9. Verification: run the unit tests

Also run the unit tests for the Xen extension parsers themselves, to confirm the
implementation is not broken.

```bash
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/ -q
```

**Expected result:** **23 passed, 10 skipped** (measured as of 2026-08-06).

- The 10 skips are `test_tree_sitter_parser.py`. The tree-sitter-bash integration is
  **incomplete** and not adopted, so it is skipped deliberately (the reason is in the
  skip message; see section 4.5 of `docs/en/06-arm64-parser-gap-analysis.md` and
  backlog B-11).
- **A single failure means reproduction failed.** Skips are expected; failures are not.

## 10. Verification: inspect the generated SPDX documents yourself

The same idea that `run-linux-sbom.sh` applies automatically on the Linux side can be
applied by hand to the Xen output.

```bash
python3 - <<'PY'
import json
for path in [
    "analysis/xen-full/sbom-build.spdx.json",
    # adjust the path to wherever your run wrote its output
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

**How to judge "the same or comparable result":**

- `@context` points at `https://spdx.org/rdf/3.0.1/spdx-context.jsonld`
- Per-type element counts roughly match the measured values in this document (some
  variation is acceptable since the source commits will not match exactly; an
  order-of-magnitude difference, or a type dropping to zero, indicates a problem)
- No new `[WARNING]` beyond the "expected warnings" in this document appears in the log
  (particularly nothing about `no matching parser` or `IfBlock`)

## 11. Known limitations (state these explicitly in external reports)

Even when the procedure itself succeeds, be aware that the following are **not done or
not established**, and take care not to overclaim when reporting (see
`worklog/backlog.md`; status is as of this document's revision).

- **Validation with an external SPDX validator has not been done** (backlog B-1). The
  current "validity check" is only a JSON-LD structural check (presence of `@graph`,
  counting elements); no formal schema validation with an official SPDX tool (e.g.
  `pyspdxtools`) has been performed. Expanding the custom JSON-LD `@context` is a
  prerequisite.
- **`tools/`, `libs/` and `stubdom/` are not supported** (backlog B-3). This runbook
  covers only the hypervisor proper (`xen/`).
- **Linking to the Safety Case (backlog B-2) is on hold**, because SPDX 3.1's Safety
  Profile is still a Release Candidate and, on the Xen FuSa SIG side, the need for
  SBOM/SPDX is not confirmed in writing.
  `analysis/xen-safety-case-relationships.example.spdx.json` is illustrative only and
  is not automatically linked to the generated SBOM.
- **arm64 is verified** (backlog B-6, completed 2026-08-06; step 6 = section 8), but
  **arm32 is not**. arm64 needed only one extra parser, for XSM/FLASK, and that was a
  configuration difference rather than an architecture one
  (`docs/en/06-arm64-parser-gap-analysis.md`).
- **Coverage on other defconfigs is unverified** (backlog B-10). The arm64 work showed
  that gaps depend on *which features are enabled*, so other configurations — e.g.
  `x86_64` with XSM/FLASK enabled — may still leave unknown commands.
- CI integration (backlog B-4) and upstream contribution (backlog B-5) have not been
  started.

## 12. Talking points for external presentation (reference)

The skeleton to connect when presenting to the Xen community and similar audiences (for
detail see the "summary" at the end of `worklog/journal.md`):

- **Question:** can the SPDX-SBOM tool that landed in Linux v7 (`scripts/sbom/`) be
  reused to generate SPDX for Xen itself?
- **Answer (what reproducing this runbook demonstrates):** for the hypervisor proper,
  the upstream tool applies directly with no modification (the PoC in step 4). Adding
  roughly 200 lines of runtime-injected extensions (`xen_parsers.py`) yields a complete
  SBOM with zero unknown commands and exit 0 (step 5).
- **Why it works:** Xen's `xen/` derives from Linux Kbuild and its `fixdep.c` emits
  `.cmd` files in the same format, so KernelSbom's dependency-graph analysis applies
  unchanged.
- **Remaining work:** external validator verification, covering `tools/` and `libs/`,
  and formalising the Safety Case link (section 11 above).
