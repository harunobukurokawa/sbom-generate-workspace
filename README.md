# xen-spdx-sbom

> Working name — the official project name is not yet fixed.

Documentation and tooling to **generate an SPDX SBOM for the Xen hypervisor**,
based on the analysis of the SPDX-SBOM generation tool merged into the Linux
kernel (`scripts/sbom/`, v7.0). The goal is to support the **Xen functional
safety (FuSa)** effort (IEC 61508 / ISO 26262, Xen FuSa SIG) by producing
SBOMs and modelling the Safety Case with SPDX relationships.

Deliverables are provided in **English** (`docs/en/`) and **Japanese**
(`docs/ja/`). A detailed **work log** (Japanese only) is kept under `worklog/`
and is intended as source material for explaining the effort to the Xen
community.

## Layout

| Path | Contents |
|------|----------|
| `docs/en/`, `docs/ja/` | Deliverable documents (EN / JA) |
| `worklog/` | Chronological work log & decision records (JA) |
| `scripts/` | Reproduction & PoC scripts |
| `analysis/` | Generated SBOM samples, graphs, investigation notes |
| `external/` | Cloned Linux / Xen sources (git-ignored) |

## Documents

1. `docs/{en,ja}/01-linux-sbom-tool.md` — How the Linux kernel SPDX-SBOM tool works and how to run it
2. `docs/{en,ja}/02-xen-build-analysis.md` — Xen build system analysis for SBOM generation
3. `docs/{en,ja}/03-xen-spdx-design.md` — Design & PoC for Xen SPDX generation + Safety Case modelling
4. `docs/{en,ja}/04-xen-parsers-implementation.md` — The Xen parser extensions as implemented
5. `docs/{en,ja}/05-reproduction-runbook.md` — Step-by-step reproduction (x86_64 and arm64)
6. `docs/{en,ja}/06-external-validation.md` — Validating the output with the official SPDX tools
7. `docs/{en,ja}/07-arm64-parser-gap-analysis.md` — The arm64 gap: root cause and remediation

## Results at a glance

- **Linux tool reproduced** (v7.2-rc1, x86_64 defconfig, 4m17s): three valid
  SPDX 3.0.1 documents (source 13,796 / build 15,282 / output 60 elements).
- **Xen hypervisor PoC** (4.23-unstable, x86_64_defconfig, 23s build): the
  *unmodified* Linux `KernelSbom` produced a valid SPDX 3.0.1 build SBOM for the
  hypervisor core — **1,442 files traced** (419 `.c`, 505 `.h`, 23 `.S`) from
  `prelink.o`. The run skipped **317 commands** for want of a parser, plus one
  unsupported `IfBlock` compound command (`analysis/xen-poc/xen-poc.run.log`).
  Those instances surface **three** command families (`mv -f`,
  `compat-build-header.py`, and the `compile.h` banner recipe) — but see below:
  they were only the first layer.
- **Complete hypervisor SBOM (Phase B):** closing the gap took more than those
  three families. Each parser added let the graph descend further and exposed the
  next Xen recipe (`combine_two_binaries.py`, `binfile`, bare `cat`, `.banner`
  no-ops), plus an existence filter for Xen's "write `X.new`, then `mv`" idiom.
  The result is ~200 lines of Xen extensions
  (`scripts/xen-sbom-poc/xen_parsers.py`, injected at runtime, upstream tool still
  unmodified) — today 8 registry entries over 7 parser functions, one of which
  (XSM/FLASK codegen) is arm64-only. The hypervisor SBOM reaches **zero unknown
  commands, exit 0**, covering **1,519 files** (+77: compat `.i`, xlat `.lst`,
  codegen `.py`, boot `.bin`, compile.h.in, .banner). Valid SPDX 3.0.1;
  **21 unit tests** pass.
- **Conclusion:** the upstream tool is directly reusable for the Xen hypervisor.
  See `docs/{en,ja}/03-xen-spdx-design.md` for the architecture and Safety Case
  model, and `docs/{en,ja}/04-xen-parsers-implementation.md` for the parsers.

## Reproduce

```bash
scripts/fetch-sources.sh                 # clone Linux (torvalds) + Xen (xenbits)
scripts/run-linux-sbom.sh                # build kernel + make sbom (Linux)

# Xen hypervisor, x86_64
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
scripts/xen-sbom-poc/run-xen-poc.sh        # baseline: unmodified KernelSbom (PoC)
scripts/xen-sbom-poc/generate-xen-sbom.sh  # complete SBOM (Xen extensions, zero unknowns)

# Xen hypervisor, arm64 (cross-build). Note the second argument is the
# hypervisor dir, not the repo root -- see runbook section 8.
make -C external/xen/xen XEN_TARGET_ARCH=arm64 arm64_defconfig
CROSS_COMPILE=aarch64-linux-gnu- make -C external/xen/xen XEN_TARGET_ARCH=arm64 -j"$(nproc)"
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom external/xen/xen analysis/arm64 prelink.o

# Validate against the official SPDX tools
scripts/validate-spdx.sh --with analysis/xen-full/sbom-build.spdx.json \
                                analysis/xen-full/sbom-output.spdx.json

# Capture the tools/libs build for the future collector (B-3).
# Run from your own shell: ./configure needs to write a dir named `config`,
# which some agent sandboxes hard-deny.
scripts/xen-sbom-poc/run-xen-tools-build.sh
```

The full procedure, including prerequisites and expected output, is in
`docs/{en,ja}/05-reproduction-runbook.md`.

## Status

**Phase A complete** — the Linux tool is documented and reproduced, the Xen build
is analysed, and the Xen adaptation is designed and proven with a PoC.

**Phase B complete** — the hypervisor SBOM reaches zero unknown commands on both
`x86_64_defconfig` and `arm64_defconfig` (B-6), and the output has been checked
with the official SPDX tools rather than by structural inspection alone (B-1).

Open work, all tracked in `worklog/backlog.md`:

- **B-3** — a collector for `tools/`, `libs/` and `stubdom/`. These are autotools
  and emit no `.cmd` files, so the cmd-graph approach does not reach them. The
  capture method is settled; the collector itself is unwritten.
- **B-8** — a query mechanism linking SBOM elements back to source, spec'd.
- **B-4** — a `make sbom` equivalent inside `xen/`, for CI reproducibility.
- **B-5** — proposing the non-Xen-specific fixes upstream to KernelSbom.
- **B-9 / B-11** — arm32, and parser coverage on defconfigs other than the two
  verified. The arm64 work showed gaps track *config options* (XSM/FLASK), not
  architecture, so this is the more likely place for further gaps.
- **B-0 / B-2** — the Safety Case link, on hold. SPDX 3.1's Safety Profile is
  still a release candidate, and whether Xen FuSa SIG needs it is unconfirmed.

This section only summarises; `worklog/backlog.md` is the single source of truth.

---

# xen-spdx-sbom（日本語）

> 暫定名です。正式なプロジェクト名は未定です。

Linux カーネル v7.0 に取り込まれた SPDX-SBOM 生成ツール（`scripts/sbom/`）を
分析し、その知見をもとに **Xen ハイパーバイザー自身の SPDX SBOM を自動生成**する
ためのドキュメントとツールを整備します。目的は Xen の **機能安全（FuSa）**
（IEC 61508 / ISO 26262、Xen FuSa SIG）を、SBOM 生成と Safety Case の
SPDX Relationships モデル化の面から支援することです。

成果物は**英語**（`docs/en/`）と**日本語**（`docs/ja/`）の両方で提供します。
詳細な**作業ログ**（日本語のみ）は `worklog/` に時系列で残し、後から Xen
コミュニティへ説明する資料の素材とします。
