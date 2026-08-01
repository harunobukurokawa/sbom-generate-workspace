# Xen SPDX-SBOM Generation — Design & PoC

*Builds on `01-linux-sbom-tool.md` (the Linux tool) and `02-xen-build-analysis.md`
(the Xen build system). Covers: proposed architecture, PoC results on a real Xen
build, Safety Case modelling with SPDX relationships, and next steps.*

## 1. Goal

Automatically generate an SPDX SBOM for the **Xen hypervisor** and link it to the
**Safety Case** so that the artefacts support the Xen **functional safety (FuSa)**
effort (IEC 61508 / ISO 26262, Xen FuSa SIG). Reuse the upstream Linux
`KernelSbom` tool (`scripts/sbom/`) as much as possible rather than writing a new
generator.

## 2. Proof of concept (verified on a real build)

The **unmodified** Linux `KernelSbom` tool was run against a freshly built Xen
hypervisor (`4.23-unstable`, `x86_64_defconfig`, built in **23 s**). Driver:
`scripts/xen-sbom-poc/run-xen-poc.sh`.

- **Root artifact:** `prelink.o`. The final `xen-syms` is produced by a special
  two-pass symbol-table link recipe that does **not** emit a `.cmd` file, so it
  cannot be a root. `prelink.o` aggregates every `built_in.o`
  (`common/ drivers/ lib/ xsm/ arch/x86/`) plus arch libs and **does** have
  `.prelink.o.cmd`, so it covers the hypervisor core end-to-end. See
  [`docs/img/xen-build-prelink.drawio`](../img/xen-build-prelink.drawio) for a
  diagram of `prelink.o` → `xen-syms` → `xen` and where `.cmd` coverage stops.
- **Invocation:** in-tree build ⇒ `--src-tree == --obj-tree`, so no separate
  source document is produced (source files are folded into the build document).
  Passed `--do-not-fail-on-unknown-build-command` + `--write-output-on-error`.

### Result

| Output | Size | Elements | Notable |
|--------|------|----------|---------|
| `sbom-build.spdx.json` | 3.1 MB | 3,280 | **1,441 `software_File`**, 539 `build_Build` |
| `sbom-output.spdx.json` | 25 KB | 12 | 1 `software_Package` (`prelink.o`) |
| `sbom.used-files.txt` | 35 KB | **1,442 files** | 419 `.c`, 505 `.h`, 490 `.o`, 23 `.S`, 3 `.a` |

Valid **SPDX 3.0.1** JSON-LD
(`@context: https://spdx.org/rdf/3.0.1/spdx-context.jsonld`). Samples are in
`analysis/xen-poc/`.

**Key outcome:** the tool traced the hypervisor from `prelink.o` back to **419 C
source files, 505 headers, and 23 assembly files** — real, file-level provenance
for the hypervisor core — with **only 6 unknown-command warnings**. Everything
else (`gcc`, `ld`, `objcopy`, `nm`, `ar`, `strip`) was handled by the existing
generic parsers, because `KernelSbom` derives those patterns from the toolchain
environment variables rather than hardcoding kernel-only names.

### The (small) gaps — Xen-specific commands needing parsers

The 6 warnings reduce to **three** command families not yet understood by
`sbom/cmd_graph/savedcmd_parser/command_parser_registry.py`:

1. **`mv -f X.new X`** (4×) — used to finalise generated compat headers
   (`include/compat/*.h`). Trivial to model (rename ⇒ propagate provenance).
2. **`/usr/bin/python3 ./tools/compat-build-header.py ...`** (2×) — Xen's compat
   layer header generator. Needs a small parser mapping the `.i` input to output.
3. **`cat .banner; sed ... < compile.h.in > compile.h`** — the `compile.h`
   banner/version generation (an `IfBlock` compound command not yet supported).

Each is a Xen build-script idiom; adding three parser entries (plus arch-name
mapping `x86`/`arm`) would take the hypervisor SBOM from ~99% to complete.

## 3. Proposed architecture

```
                 ┌──────────────────────────────────────────────┐
                 │  xen-spdx-sbom generator (this project)       │
                 │                                              │
  xen/  build ──▶│  [A] KernelSbom core (reused, .cmd graph)     │──▶ sbom-build.spdx.json
  (.cmd files)   │      + xen_parsers/ (mv, compat-build-header, │──▶ sbom-output.spdx.json
                 │        compile.h; arch map x86/arm)           │──▶ sbom.used-files.txt
                 │                                              │
  tools/ libs/ ─▶│  [B] complementary collector                 │──▶ (package/file SBOM)
  (autotools)    │      (strace or compile_commands.json)        │
                 │                                              │
                 │  [C] Safety Case linker (SPDX Relationships)  │──▶ xen-safety-case.spdx.json
                 └──────────────────────────────────────────────┘
```

- **[A] Hypervisor (reuse):** vendor the upstream `scripts/sbom/` and add a thin
  `xen_parsers/` module registering the three Xen-specific commands above. Drive
  it like the kernel's `make sbom` target: roots = `prelink.o` (and, once the
  two-pass link emits a recordable command, `xen-syms`). This is the **primary,
  near-complete** deliverable and the FuSa focus.
- **[B] tools/libs (new, coarser):** these have no `.cmd` files. Use **strace**
  file-open tracking (build-system-agnostic, mirrors upstream KernelSbom's own
  `sbom_analysis/`) or `compile_commands.json` (via `bear`) to produce at least a
  package/file-level SBOM. Deferred to a later phase.
- **[C] Safety Case linker (new):** post-process step that emits SPDX
  Relationships tying the generated SBOM to Safety Case artefacts (see §4).

## 4. Safety Case modelling with SPDX relationships

Functional safety requires the **Safety Case** documents (safety plan,
requirements, coding guidelines / MISRA compliance, change management) to be part
of the delivered Bill of Materials and traceably linked to the software they
govern. In SPDX 3.0.1 this is expressed with **`Relationship` elements** between
the generated SBOM/Package and `Artifact` elements representing each Safety Case
document.

An illustrative model (see `analysis/xen-safety-case-relationships.example.spdx.json`):

| From | relationshipType | To (Safety Case artefact) |
|------|------------------|---------------------------|
| `pkg:xen-hypervisor` | *(described by)* | `sbom:xen-hypervisor` (generated SBOM) |
| `sbom:xen-hypervisor` | `hasDocumentation` | Safety Plan |
| `pkg:xen-hypervisor` | `hasRequirement` | Safety Requirements Specification |
| `pkg:xen-hypervisor` | `hasEvidence` | MISRA Coding Guidelines + compliance evidence |
| `pkg:xen-hypervisor` | `hasDocumentation` | Change Management Plan |

Notes:
- The `relationshipType` values above must be mapped to the SPDX 3.0.1
  `RelationshipType` vocabulary; where a precise safety semantic is missing, use
  the closest core type plus a `comment`, or an external property. This mirrors
  the SPDX-for-Functional-Safety approach (relationships across all Safety Case
  documentation artefacts).
- Because the SBOM already enumerates every source file, MISRA evidence and
  requirements can be attached at **file granularity** later (e.g. per-file
  deviation records), which is exactly what a FuSa assessor wants.

## 5. Next steps (later phases)

> **Update (Phase B — done):** step 1 is implemented. The Xen extensions
> (`scripts/xen-sbom-poc/xen_parsers.py`, runtime-injected, upstream unmodified)
> take the hypervisor SBOM to **zero unknown commands / exit 0**, covering 1,519
> files. See `04-xen-parsers-implementation.md`. The gap turned out larger than
> the 3 commands the baseline suggested (early-failure hid deeper recipes), and
> was closed by handling the whole compat-*/binfile/combine/compile.h/.banner
> families plus an existence filter for transient files.

1. ~~Implement `xen_parsers/` + reach a 100%-complete hypervisor graph.~~ **Done.**
   Remaining: validate with an external SPDX validator after expanding the custom
   JSON-LD `@context`.
2. Wire a `make sbom`-style target into `xen/` (or a standalone wrapper) so the
   hypervisor SBOM is reproducible in CI.
3. Add the tools/libs collector ([B]) for whole-Xen coverage.
4. Formalise the Safety Case linker ([C]) with the FuSa SIG and align
   `relationshipType`s with the SPDX FuSa profile as it matures.

## 6. Conclusion

The PoC demonstrates, on a real build, that the upstream Linux SBOM tool is
**directly reusable for the Xen hypervisor**: it produced a valid SPDX 3.0.1
build SBOM covering 1,441 files with only three small Xen-specific command
parsers missing. Combined with a complementary collector for tools/libs and an
SPDX-Relationship Safety Case linker, this is a viable path to an automated,
FuSa-supporting SBOM for Xen.
