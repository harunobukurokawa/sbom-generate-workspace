# The Linux Kernel SPDX-SBOM Tool (KernelSbom)

*Analysis target: Linux mainline `v7.2-rc1` (the tree that contains the tool at
the time of writing; note that `v7.0` has no dedicated tag — mainline is already
at 7.2-rc1). Tool path: `scripts/sbom/`.*

## 1. Overview

`KernelSbom` is a pure-Python script (`scripts/sbom/sbom.py`) that runs **after a
successful kernel build** and emits **Software Bill of Materials (SBOM)**
documents in **SPDX 3.0.1** format (serialized as JSON-LD). It was originally
developed by TNG Technology Consulting in the
[KernelSbom repository](https://github.com/TNG/KernelSbom) and merged into the
mainline kernel tree.

It produces up to **three** documents plus one optional flat file:

| File | Contents |
|------|----------|
| `sbom-source.spdx.json` | Every source file involved in the build, each linked to its license expression. *(Only for out-of-tree builds.)* |
| `sbom-output.spdx.json` | Final build outputs (kernel image + `.ko` modules) with build metadata: environment variables and a hash of `.config`. |
| `sbom-build.spdx.json` | Every intermediate artifact, the exact build command for each, and the input→output relationships. Imports files from the source and output docs. |
| `sbom.used-files.txt` | *(Optional, `--generate-used-files`)* flat list of source files used. |

**Requirements:** Python **3.10+**. No third-party libraries.

## 2. How to run it

### 2.1 Via the `make sbom` target (recommended)

```bash
make defconfig O=kernel_build
make sbom O=kernel_build -j"$(nproc)"
```

`make sbom` first builds the kernel (it depends on the image,
`include/generated/autoconf.h`, and — if `CONFIG_MODULES` — `modules` /
`modules.order`), then invokes the script. The three SPDX files land in the
**object tree root** (`kernel_build/`).

The Makefile wiring (`Makefile`, target `sbom`, ~line 2246) expands to:

```make
cmd_sbom = printf "%s\n" "$(KBUILD_IMAGE)" >"$(tmp-target)"; \
           $(if $(CONFIG_MODULES),sed 's/\.o$$/.ko/' $(objtree)/modules.order >> "$(tmp-target)";) \
           $(PYTHON3) $(srctree)/scripts/sbom/sbom.py \
               --src-tree $(abspath $(srctree)) \
               --obj-tree $(abspath $(objtree)) \
               --roots-file "$(tmp-target)" \
               --output-directory $(abspath $(objtree)) \
               --generate-spdx \
               --package-license "GPL-2.0 WITH Linux-syscall-note" \
               --package-version "$(KERNELVERSION)" \
               --write-output-on-error;
```

Key points to note for adapting this elsewhere (e.g. Xen):
- The **roots** are the kernel image plus every module (`.ko`), derived from
  `modules.order` by rewriting `.o` → `.ko`.
- `--package-license "GPL-2.0 WITH Linux-syscall-note"` and
  `--package-version $(KERNELVERSION)` are kernel-specific and passed from the
  Makefile — not hardcoded in the script.
- `sbom-source.spdx.json` is only added to `sbom_targets` when
  `building_out_of_srctree` is set (i.e. `O=` is used).

### 2.2 Standalone

```bash
SRCARCH=x86 python3 scripts/sbom/sbom.py \
    --src-tree . \
    --obj-tree ./kernel_build \
    --roots arch/x86/boot/bzImage \
    --generate-spdx \
    --generate-used-files \
    --prettify-json \
    --debug
```

When run outside `make`, compilation-time environment variables are not
available and thus cannot be recorded. Set at least `SRCARCH`.

To include modules as roots:

```bash
echo "arch/x86/boot/bzImage" > sbom-roots.txt
sed 's/\.o$/.ko/' ./kernel_build/modules.order >> sbom-roots.txt
SRCARCH=x86 python3 scripts/sbom/sbom.py \
    --src-tree . --obj-tree ./kernel_build \
    --roots-file sbom-roots.txt --generate-spdx
```

## 3. How it works

Two phases (`scripts/sbom/sbom.py:main`):

**Phase 1 — build the "cmd graph"** (`sbom/cmd_graph/`): an acyclic directed
dependency graph whose nodes are files and whose edges mean *"file A was used to
build file B"*. Starting from each root artifact, dependencies are gathered from
three sources:

1. **`.cmd` files** (primary) — Kbuild writes `dir/.<name>.cmd` recording the
   exact command and the explicit dependency list for each output. Parsed by
   `sbom/cmd_graph/cmd_file.py` + `deps_parser.py`.
2. **`.incbin` statements** in `.S` assembly files
   (`sbom/cmd_graph/incbin_parser.py`).
3. **Hardcoded dependencies** (`sbom/cmd_graph/hardcoded_dependencies.py`) —
   a small manually-maintained map for dependencies defined in Makefiles/Kbuild
   that are not captured by `.cmd`/`.incbin` (e.g. `asm-offsets.h`). Known to be
   incomplete but the graph reaches ~99% completeness.

The graph is expanded recursively until it reaches version-controlled source
files.

**Phase 2 — build SPDX documents** (`sbom/spdx_graph/`, `sbom/spdx/`): for every
file in the graph the tool parses the `SPDX-License-Identifier` header, computes
file hashes, estimates the file type from extension/path, and records build
relationships. Each root output additionally gets an SPDX `Package` element with
version/license/copyright. Output is serialized to JSON-LD
(`sbom/spdx/serialization.py`).

### Source vs. object tree

Files are classified as **source** when they live in the source tree but **not**
in the object tree. Therefore **out-of-tree builds (`O=objtree`) are
recommended**. For in-tree builds (src == obj) the distinction is unreliable, so
no `sbom-source.spdx.json` is produced; source files are folded into
`sbom-build.spdx.json`, and `sbom.used-files.txt` lists everything.

## 4. Command-line options (from `sbom/config.py`)

| Option | Default | Meaning |
|--------|---------|---------|
| `--src-tree` | `../linux` | Kernel source tree |
| `--obj-tree` | `../linux/kernel_build` | Build output directory |
| `--roots` / `--roots-file` | *(required, mutually exclusive)* | Root artifacts (rel. to obj-tree) |
| `--generate-spdx` | off | Emit the three SPDX docs |
| `--generate-used-files` | off | Emit `sbom.used-files.txt` |
| `--output-directory` | `.` | Where to write outputs |
| `--do-not-fail-on-unknown-build-command` | off (i.e. fail) | Downgrade unknown-command errors to warnings |
| `--write-output-on-error` | off | Write (possibly incomplete) docs despite errors |
| `--spdxId-prefix` | `urn:spdx.dev:` | Prefix for all `spdxId`s |
| `--build-type` | `urn:spdx.dev:Kbuild` | SPDX `buildType` for Build elements |
| `--build-id` | *(spdxId of Build)* | SPDX `buildId` |
| `--package-license` | `NOASSERTION` | License for all Packages |
| `--package-version` | none | Version for all Packages |
| `--package-copyright-text` | `COPYING` if present | Copyright for all Packages |
| `--prettify-json` | off | Pretty-print JSON |

## 4.1 Reproduction result (verified)

Reproduced on 2026-07-04 with **Linux v7.2-rc1**, `x86_64 defconfig`, out-of-tree
(`O=kernel_build`), Python 3.10.12, `make sbom -j16`. Build time **4m17s**. All
three documents were produced and are valid SPDX 3.0.1 JSON-LD
(`@context: https://spdx.org/rdf/3.0.1/spdx-context.jsonld`):

| Document | Size | Elements | Notable |
|----------|------|----------|---------|
| `sbom-source.spdx.json` | 4.5 MB | 13,796 | 7,138 `software_File` |
| `sbom-build.spdx.json` | 27 MB | 15,282 | 3,923 `build_Build` |
| `sbom-output.spdx.json` | 34 KB | 60 | 13 `software_Package` (bzImage + modules) |

Samples are stored under `analysis/` (`sample-sbom-output.spdx.json` is the full
output doc; source/build are truncated excerpts). Reproduce with
`scripts/run-linux-sbom.sh`. Note: `make sbom` does not pass
`--generate-used-files`, so `sbom.used-files.txt` is not produced by that target.

## 5. Limitations

- **Architectures:** x86 and arm64 only at present.
- **Custom JSON-LD `@context`:** to reduce size, outputs define custom prefixes
  for `spdxId` values. This is spec-compliant but only some SPDX tools support
  it; the context may need to be *expanded* before feeding into other tools.
- **Hardcoded-dependency gaps:** ~99% (not 100%) graph completeness.
- **Unknown build commands:** by default the tool *fails* on an unrecognized
  `.cmd` command; use `--do-not-fail-on-unknown-build-command` to continue with
  an incomplete SBOM.

## 6. Why this matters for Xen

The tool's core (the cmd-graph builder) depends on **Kbuild `.cmd` files**. The
Xen hypervisor (`xen/`) uses a **Kbuild-derived** build system that produces the
same `dir/.<name>.cmd` files, which makes the `.cmd`-parsing approach reusable
for the Xen hypervisor. Xen's `tools/` and `libs/` use different build systems
and need a complementary approach. See `02-xen-build-analysis.md`.
