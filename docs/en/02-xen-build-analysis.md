# Xen Build System Analysis for SPDX-SBOM Generation

*Analysis target: Xen mainline `4.23-unstable` (cloned HEAD `f0161d2`, 2026-07-03).
Compared against the Linux KernelSbom tool described in `01-linux-sbom-tool.md`.*

## 1. Question

Can the Linux kernel's `.cmd`-based SBOM generator (`scripts/sbom/`) be reused
to generate an SPDX SBOM for Xen? Xen is split into two very different build
domains, so we answer per-domain.

| Xen domain | Build system | `.cmd` files? | Reuse outlook |
|------------|--------------|---------------|---------------|
| `xen/` (the hypervisor) | **Kbuild-derived** (imported from Linux) | **Yes** | **High** — parser is largely compatible |
| `tools/`, `stubdom/`, `libs/` | **autotools + hand-written Makefiles** | No | Low — needs a different mechanism |

## 2. The hypervisor (`xen/`) — strongly compatible

Xen's hypervisor build imported Kbuild from Linux years ago. The relevant files
are `xen/Rules.mk` and `xen/scripts/Kbuild.include`. The `.cmd` machinery is
essentially identical to Linux:

- `dot-target = $(@D)/.$(@F)` → produces `dir/.<target>.cmd` (same naming).
- `if_changed` writes the command line:
  `printf '%s\n' 'cmd_$@ := $(make-cmd)' > $(dot-target).cmd`.
- `if_changed_dep` runs `tools/fixdep` to also record dependencies.

Crucially, **Xen's `fixdep` (`xen/tools/fixdep.c`) emits the same line format**
that KernelSbom's parser expects:

| Line emitted by Xen `fixdep.c` | KernelSbom `cmd_file.py` expectation | Match |
|--------------------------------|--------------------------------------|-------|
| `cmd_%s := %s` (line 397) | `SAVEDCMD_PATTERN = ^(saved)?cmd_.*?:=` | ✅ (the `(saved)?` is optional) |
| `source_%s := %s` (line 352) | requires a `source_` entry | ✅ |
| `deps_%s := \` + `<tgt>: $(deps_%s)` (352–382) | dependency line `<output>: <dependency>` | ✅ |

**Only difference:** modern Linux writes `savedcmd_<target> :=` whereas Xen still
writes `cmd_<target> :=`. Because the KernelSbom regex makes the `saved` prefix
optional, **the raw `.cmd` line parsing already works for Xen unchanged.**

### Remaining gap for the hypervisor: the command parser registry

KernelSbom does not just read the dependency list — it also *parses the build
command itself* to recover inputs that are not in the dependency list. This is
done by `sbom/cmd_graph/savedcmd_parser/command_parser_registry.py`, which has
per-command parsers for Linux-specific commands, e.g.:

- generic compile/link (`gcc`, `ld`)
- `objcopy`, `dd`, `cat`, `sed`
- `_parse_link_vmlinux_command` — the Linux **`vmlinux` link** step

Xen's final link targets are different (`xen-syms`, `xen.efi`, `xen` image,
per-arch link scripts), and Xen has its own image-construction steps
(e.g. `arch/x86/boot`, `mkelf32`, `efi`). By default KernelSbom **fails** on an
unknown build command, so these Xen-specific commands must either:

1. be added as new parsers to the registry (preferred, complete graph), or
2. be tolerated via `--do-not-fail-on-unknown-build-command` (quick start,
   incomplete graph).

The `SRCARCH` assumption and the x86/arm64-only limitation also apply; Xen arch
naming (`x86`, `arm`) must be mapped.

## 3. The tools/libs domain — needs a different mechanism

`tools/`, `stubdom/`, and the `libs/` live under autotools (`configure.ac`,
`configure`) plus hand-written Makefiles/`tools/Rules.mk`. They do **not**
generate `.cmd` files, so the cmd-graph approach cannot see them. Options
(in the spirit of the upstream KernelSbom `sbom_analysis/` helpers):

- **compile_commands.json** (via `bear` or a compiler wrapper) to recover
  per-file compile inputs.
- **strace-based file tracking** of the build to capture every file opened for
  read — the most build-system-agnostic option, matching KernelSbom's own
  analysis tooling.
- **Package-level SBOM** (coarser): describe tools/libs as SPDX Packages with
  versions/licenses rather than file-level provenance.

For a functional-safety scope, the **hypervisor is the primary certification
target**, so a phased plan (hypervisor first at file level, tools/libs later /
coarser) is reasonable.

## 4. Conclusion

- **Hypervisor (`xen/`):** the KernelSbom `.cmd`/`fixdep` parsing is reusable
  with **minor changes** — mainly extending the command parser registry with
  Xen-specific link/image commands and arch mapping. This is the recommended
  first target and the basis of the PoC.
- **tools/libs:** require a complementary mechanism (strace or
  compile_commands.json), designed but not implemented in this pass.

See `03-xen-spdx-design.md` for the proposed architecture, the Safety Case
relationship modelling, and PoC results.
