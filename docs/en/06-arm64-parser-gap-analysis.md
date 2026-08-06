# 06. ARM64 SBOM Parser Gap Analysis and Remediation

**Build under test**: Xen 4.23-unstable, `arm64_defconfig`, `aarch64-linux-gnu-gcc 11.4.0`
**KernelSbom**: Linux mainline `scripts/sbom` (**unmodified**)
**Measured**: 2026-08-06
**Conclusion**: The ARM64-specific gap is **exactly two command parsers**. Adding them
via the existing runtime-injection layer yields a complete SBOM with **zero unknown
commands**. No change to KernelSbom is required.

---

## 1. Summary

| Metric | Before remediation | After |
|--------|--------------------|-------|
| Unknown build commands | (not measurable) | **0** |
| `sbom.used-files.txt` | 1 entry | **895 paths** (`wc -l` prints 894: no trailing newline) |
| `sbom-build.spdx.json` | 7 elements / 2.2 KB | **1,951 elements / 1.5 MB** |
| Changes to KernelSbom | none | **none (preserved)** |

Element breakdown after remediation (1,951 elements):

| Type | Count |
|------|-------|
| `software_File` | 894 |
| `Relationship` | 758 |
| `build_Build` | 290 |
| `simplelicensing_LicenseExpression` | 5 |
| Document / Agent / CreationInfo / Sbom | 4 |

Tracked file types (within the 895 paths, overlapping counts): `.h` 359, `.c` 222,
`.o` 281, `.S` 19, `.a` 2.

894 of the 895 paths become `software_File` elements. The one difference is the root
artifact `prelink.o`, which lives in `sbom-output.spdx.json` instead. The list also
contains `../../../usr/bin/dash` (the real path behind `/bin/sh`) — the shell that ran
the codegen scripts, tracked as a dependency. That is expected, not an anomaly.

---

## 2. Root cause: `--obj-tree` pointed one directory too high

The SBOM initially contained 7 elements and exactly one tracked file (`prelink.o`
itself). This was misdiagnosed as "the parsers cannot handle complex shell
constructs". **The actual cause was a caller-side argument error, unrelated to
parser capability.**

The Xen hypervisor is built in the `xen/` subdirectory of the Xen repository, and
paths inside `.cmd` files are recorded **relative to that build directory**.

```
repository root : /workspace/xen
build directory : /workspace/xen/xen      <- .cmd paths are relative to this
.prelink.o.cmd  : cmd_prelink.o := aarch64-linux-gnu-ld ... common/built_in.o ...
```

Passing `--obj-tree /workspace/xen` (the repository root) resolves
`common/built_in.o` to `/workspace/xen/common/built_in.o`, which does not exist.

```
✗ /workspace/xen/common/built_in.o        (wrong resolution, nonexistent)
✓ /workspace/xen/xen/common/built_in.o    (actual file)
```

### 2.1 Why this failed silently

When `xen_parsers.OBJ_TREE` is set, `_keep_existing()` filters parsed inputs down to
files that exist on disk. **This filter emits no warning** — its purpose is to drop
transient paths from Xen's "generate `X.new`, then `mv` to `X`" idiom.

So the parsers were extracting inputs correctly, and every one of them was then
discarded in silence. Only the symptom pointing at the parsers remained visible.

```
ld parser output (correct):
  ['prelink.o', 'common/built_in.o', 'drivers/built_in.o', 'lib/built_in.o',
   'xsm/built_in.o', 'arch/arm/built_in.o', 'arch/arm/arm64/lib/lib.a', 'lib/lib.a']
        v  _keep_existing()  (all nonexistent under the wrong obj-tree)
  []                                    <- silently emptied
```

### 2.2 A secondary symptom from the same cause

`Cannot compute hash for /workspace/xen/.config because file does not exist` had the
same root cause (the real file is `/workspace/xen/xen/.config`). During
investigation this was worked around by copying the file to the repository root;
that workaround was a band-aid and has been removed along with the obj-tree fix.

### 2.3 Correct invocation

The second argument of `gen_xen_sbom.py` (`<xen_hv_dir>`) means what its name says:
the **hypervisor directory**, not the repository root.

```bash
# correct
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom  /path/to/xen/xen  analysis/arm64  prelink.o

# wrong (the bug in this investigation)
#   ... /path/to/xen  analysis/arm64  xen/prelink.o
```

---

## 3. The real ARM64 gap: XSM/FLASK policy code generation

With the obj-tree corrected, the graph is actually traversed and the unknown-command
set collapses to **two** recipes:

```
/bin/sh ./xsm/flask/policy/mkflask.sh awk xsm/flask/include \
    ./xsm/flask/policy/security_classes ./xsm/flask/policy/initial_sids

/bin/sh ./xsm/flask/policy/mkaccess_vector.sh awk xsm/flask/include \
    ./xsm/flask/policy/access_vectors
```

Why the x86 PoC never saw these is straightforward: **`arm64_defconfig` enables
XSM/FLASK, while the x86_64 `defconfig` does not.** The gap is therefore a
**configuration** difference, not an architecture difference. The general lesson for
ARM64 support is not "write ARM64 parsers" but "cover the parsers for whatever
features a given defconfig turns on".

### 3.1 Argument shape, and one implementation trap

```
/bin/sh  <script>.sh  <awk>  <output_dir>  <policy_file>...
   [0]        [1]      [2]       [3]           [4:]
```

Inputs are the generator script and the policy definition files. The `awk`
interpreter name and the **output directory** are not inputs.

Excluding the output directory must be explicit: `_keep_existing()` tests with
`os.path.exists()`, **which returns True for directories**, so without an explicit
skip, `xsm/flask/include` would survive into the SBOM as a bogus "file". This trap is
pinned by the unit test
`TestFlaskCodegenParser.test_awk_and_output_directory_are_dropped`.

---

## 4. tree-sitter-bash: measured, and not adopted for this build

The original motivation for this PoC was the hypothesis that complex shell constructs
(`if-then-else`, `while`, pipes) cannot be parsed with regex-based patterns.
**Measurement did not support that hypothesis.**

### 4.1 Method

All **303** `savedcmd` strings were extracted from the ARM64 build's `.cmd` files.
For each candidate parser, we compared which parser wins each command with the parser
present versus absent, against the full upstream registry (61 entries).

### 4.2 Results

| Added parser | Commands rescued from UNKNOWN | Commands stolen from upstream | Verdict |
|--------------|------------------------------|-------------------------------|---------|
| `_parse_ld_command` | 0 | **23** | pure regression |
| `_parse_complex_shell_command` (tree-sitter) | 0 (see 4.3) | **7** | pure regression |

**`_parse_ld_command` was unnecessary.** Upstream KernelSbom already ships
`^([^\s]+-)?ld\b`. The addition merely replaced a working upstream implementation
with a weaker local one.

Worse, the added pattern `.*aarch64-linux-gnu-ld\b|.*ld\b` **over-matches**: `.*ld\b`
matches *any* command containing the word-ending `build`:

```
match=True   gcc -Ibuild/include -c foo.c -o foo.o   <- a gcc command hijacked by the ld parser
```

Xen entries are evaluated **before** the entire upstream registry, so a loose pattern
silently steals commands that upstream handles correctly. This is a regression that
produces no warning; it is now pinned by the regression test
`TestXenPatternsDoNotShadowUpstream`.

### 4.3 Why tree-sitter's apparent "19 rescues" are not real

Measuring pattern matches against the raw registry suggests tree-sitter rescues 19
commands of the form `objdump -h X | while read ...`. **In the real pipeline those
commands never reach the registry.**

`xen_parse_inputs_from_commands()` strips the `*.init.o` section-size validation loop
with the `_VALIDATION_PRELUDE` regex *before* command splitting, and handles
`if..then..fi` via `IfBlock` branch parsing. The existing implementation already
absorbs these constructs, leaving nothing for tree-sitter to contribute.

Demonstrated: with `_VALIDATION_PRELUDE` and `IfBlock` handling as-is and tree-sitter
removed, the production driver completes with **zero unknown commands**.

### 4.4 Correcting the numbers in the existing PR document

The following figures in `TREE_SITTER_INTEGRATION.md` are **not measurements** — they
were pre-implementation expectations, and this PoC contradicts them. A correction has
been appended to that file.

| As documented | Measured |
|---------------|----------|
| Parse success 48% → 99.6% | The 48% baseline was never verified; the existing implementation already reaches zero unknown commands |
| 1,847 files / 2,156 relationships / 3.2 MB | **894** files / **758** relationships / **1.5 MB** |

### 4.5 Disposition of tree-sitter-bash (the implementation is incomplete)

Registry integration is **removed** (a pure regression for this build). Beyond that,
measurement showed the implementation itself is **incomplete**:

| Capability | Status |
|------------|--------|
| AST construction / control-flow extraction | ✓ works (`then_body` / `else_body` are recovered) |
| I/O file extraction | ✗ **not implemented** — `extractIOFiles()` in `src/shell_parser.js` always returns empty lists |
| Python wrapper JSON handling | ✗ **broken** — the Node script emits two pretty-printed JSON blocks, but `shell_parser_wrapper.py` calls `json.loads()` on `lines[0]` (line 1 only), which fails and silently falls back to regex |

Consequently `ParseResult.inputs` / `outputs` are always empty, and 5 tests in
`tests/test_tree_sitter_parser.py` fail. Those tests are retained as **the
specification a future implementation must satisfy**; the class carries an
`@unittest.skip` with that reason (keeping CI green while making the incompleteness
visible rather than hiding it).

- Retained code: `src/shell_parser.js`, `scripts/shell_parser_wrapper.py`,
  `scripts/xen-sbom-poc/tree_sitter_parser.py`. The Node.js 12 compatibility fix
  (removing optional chaining) is applied and the AST layer does work.
- **Completing it is not on the critical path**: zero unknown commands is achieved
  without tree-sitter, so there is currently no return on the investment.
- If revisited (a future build introducing shell constructs `_VALIDATION_PRELUDE`
  cannot express): **reproduce the measurement in 4.1, demonstrate rescues > steals,
  and finish the three items above before adopting it.**

---

## 5. Remediation (KernelSbom left unmodified)

The project's core principle — KernelSbom is used unmodified — is preserved. Every
fix lives inside the existing runtime-injection layer, which prepends Xen entries to
`DEFAULT_COMMAND_PARSER_REGISTRY` from `install_xen_extensions()`.

In `scripts/xen-sbom-poc/xen_parsers.py`:

1. Added `_parse_flask_codegen()` and registered it with a narrow pattern
   (`.*xsm/flask/policy/mk(flask|access_vector)\.sh\b`).
2. Removed `_parse_ld_command()` (already upstream; over-matching).
3. Removed the tree-sitter registry entry.
4. Documented the "keep these patterns narrow" constraint on `XEN_COMMAND_PARSERS`.

Tests (`scripts/xen-sbom-poc/tests/test_xen_parsers.py`, 13 passing):

- `TestFlaskCodegenParser` (3) — uses the exact command strings observed in the real
  build, and pins the output-directory leak.
- `TestXenPatternsDoNotShadowUpstream` (1) — asserts no Xen pattern claims an
  upstream-owned command, including a gcc command containing the `build` substring.

---

## 6. Reproduction

```bash
# 1. Build ARM64 Xen (do not `make clean` afterwards: the intermediate .o files
#    must remain on disk for a post-build SBOM)
cd <xen>/xen
XEN_TARGET_ARCH=arm64 make arm64_defconfig
CROSS_COMPILE=aarch64-linux-gnu- XEN_TARGET_ARCH=arm64 make -j"$(nproc)"

# 2. Generate the SBOM (2nd argument is the hypervisor dir = <xen>/xen)
cd <workspace>
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom  <xen>/xen  analysis/arm64  prelink.o

# 3. Unit tests
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/ -q
```

`gen_xen_sbom.py` deliberately does not pass
`--do-not-fail-on-unknown-build-command`, so a single unknown command aborts output.
**The existence of the output documents is itself the proof of zero unknown
commands.**

### 6.1 Toolchain

| Tool | Version used | Note |
|------|--------------|------|
| `aarch64-linux-gnu-gcc` | 11.4.0 | `gcc-aarch64-linux-gnu` |
| Python | 3.10.12 | KernelSbom requires 3.10+ |
| Node.js | 12.22.9 | tree-sitter experiment only; **not needed** for SBOM generation |

---

## 7. Lessons

1. **Silent filters cause misdiagnosis.** `_keep_existing()` dropping every input
   without a warning made an argument error look like a parser defect. Warning when
   this filter empties a non-empty set is worth adding (backlog B-9).
2. **Check the upstream registry before adding a parser.** The `ld` parser was
   written without reviewing the 61 existing entries, introducing a regression.
3. **Keep prepended patterns narrow.** Xen entries outrank the whole upstream
   registry, so a loose pattern steals upstream commands silently.
4. **Look at config differences, not architecture differences.** The gap was
   "XSM/FLASK enabled", not "ARM64". Other defconfigs likely expose comparable gaps
   (backlog B-10).
5. **Never document expectations as measurements.** The "99.6%" in
   `TREE_SITTER_INTEGRATION.md` was never measured, and the measurement refuted the
   hypothesis behind it.
