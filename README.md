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

## Status

Phase A (in progress): document the Linux tool, reproduce it, analyse the Xen
build, and design + PoC the Xen adaptation. Full implementation is a later
phase.

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
