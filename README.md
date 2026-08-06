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

## 構成

| パス | 内容 |
|------|------|
| `docs/en/`, `docs/ja/` | 成果物ドキュメント（英 / 日） |
| `worklog/` | 時系列の作業ログと決定記録（日本語） |
| `scripts/` | 再現用・PoC 用スクリプト |
| `analysis/` | 生成した SBOM のサンプル、統計、調査メモ |
| `external/` | clone した Linux / Xen ソース（git 管理外） |

## ドキュメント

1. `docs/{en,ja}/01-linux-sbom-tool.md` — Linux カーネルの SPDX-SBOM ツールの仕組みと実行方法
2. `docs/{en,ja}/02-xen-build-analysis.md` — SBOM 生成の観点での Xen ビルドシステム分析
3. `docs/{en,ja}/03-xen-spdx-design.md` — Xen SPDX 生成の設計と PoC ＋ Safety Case モデル化
4. `docs/{en,ja}/04-xen-parsers-implementation.md` — Xen パーサ拡張の実装
5. `docs/{en,ja}/05-reproduction-runbook.md` — 再現手順書（x86_64 / arm64）
6. `docs/{en,ja}/06-external-validation.md` — 公式 SPDX ツールによる出力の検証
7. `docs/{en,ja}/07-arm64-parser-gap-analysis.md` — arm64 でのパーサ欠落: 原因と是正

## 成果の要約

- **Linux ツールの再現**（v7.2-rc1, x86_64 defconfig, 4分17秒）: 妥当な SPDX 3.0.1
  文書 3 本（source 13,796 / build 15,282 / output 60 要素）。
- **Xen ハイパーバイザー PoC**（4.23-unstable, x86_64_defconfig, ビルド 23 秒）:
  **無改造**の Linux `KernelSbom` が、ハイパーバイザーコアについて妥当な SPDX 3.0.1
  build SBOM を生成。`prelink.o` を起点に **1,442 ファイルを追跡**（`.c` 419、
  `.h` 505、`.S` 23）。この実行ではパーサ不在により **317 コマンドがスキップ**され、
  加えて未対応の `IfBlock` 複合コマンドが 1 件（`analysis/xen-poc/xen-poc.run.log`）。
  これらは 3 系統のコマンド（`mv -f`、`compat-build-header.py`、`compile.h` の
  バナー生成）に集約されるが、後述のとおりこれは最初の 1 層にすぎなかった。
- **ハイパーバイザー SBOM の完全化（Phase B）:** ギャップ解消には上記 3 系統では
  足りなかった。パーサを 1 つ追加するたびにグラフが 1 層深く降り、次の Xen 固有
  レシピ（`combine_two_binaries.py`、`binfile`、素の `cat`、`.banner` の no-op）が
  露出した。さらに Xen の「`X.new` を生成してから `mv`」イディオムに対応する存在
  フィルタも必要だった。結果は約 200 行の Xen 拡張
  （`scripts/xen-sbom-poc/xen_parsers.py`、実行時に注入。上流ツールは無改造のまま）
  で、現時点でレジストリ 8 エントリ / パーサ関数 7 個。うち 1 つ（XSM/FLASK の
  コード生成）は arm64 でのみ使われる。これにより **未知コマンド 0 件、exit 0** に
  到達し、**1,519 ファイル**をカバー（+77: compat `.i`、xlat `.lst`、コード生成
  `.py`、boot `.bin`、compile.h.in、.banner）。SPDX 3.0.1 妥当。
  ユニットテスト **21 件** が通過。
- **結論:** 上流ツールは Xen ハイパーバイザーにそのまま再利用できる。
  アーキテクチャと Safety Case モデルは `docs/{en,ja}/03-xen-spdx-design.md`、
  パーサの詳細は `docs/{en,ja}/04-xen-parsers-implementation.md` を参照。

## 再現手順

```bash
scripts/fetch-sources.sh                 # Linux（torvalds）と Xen（xenbits）を clone
scripts/run-linux-sbom.sh                # カーネルをビルドし make sbom（Linux）

# Xen ハイパーバイザー（x86_64）
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
scripts/xen-sbom-poc/run-xen-poc.sh        # ベースライン: 無改造 KernelSbom（PoC）
scripts/xen-sbom-poc/generate-xen-sbom.sh  # 完全な SBOM（Xen 拡張、未知コマンド 0）

# Xen ハイパーバイザー（arm64、クロスビルド）
# 第 2 引数はリポジトリのルートではなく「ハイパーバイザーのディレクトリ」。
# 詳細は手順書 8 節。
make -C external/xen/xen XEN_TARGET_ARCH=arm64 arm64_defconfig
CROSS_COMPILE=aarch64-linux-gnu- make -C external/xen/xen XEN_TARGET_ARCH=arm64 -j"$(nproc)"
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom external/xen/xen analysis/arm64 prelink.o

# 公式 SPDX ツールでの検証
scripts/validate-spdx.sh --with analysis/xen-full/sbom-build.spdx.json \
                                analysis/xen-full/sbom-output.spdx.json

# 将来のコレクタ（B-3）用に tools/libs のビルドを採取。
# ご自身のシェルで実行すること: `./configure` は `config` という名前の
# ディレクトリを作る必要があり、エージェントのサンドボックスによっては拒否される。
scripts/xen-sbom-poc/run-xen-tools-build.sh
```

前提条件や期待される出力を含む完全な手順は
`docs/{en,ja}/05-reproduction-runbook.md` にあります。

## 状況

**Phase A 完了** — Linux ツールの文書化と再現、Xen ビルドの解析、Xen 適応の設計と
PoC による実証が済んでいる。

**Phase B 完了** — ハイパーバイザー SBOM は `x86_64_defconfig` と `arm64_defconfig`
の両方で未知コマンド 0 件に到達（B-6）。出力は構造検査だけでなく公式 SPDX ツールでも
確認済み（B-1）。

未着手の作業（すべて `worklog/backlog.md` で管理）:

- **B-3** — `tools/`・`libs/`・`stubdom/` 用のコレクタ。これらは autotools で
  `.cmd` を生成しないため、cmd グラフ方式が届かない。採取方式は決定済みだが、
  コレクタ本体は未実装。
- **B-8** — SBOM 要素からソースコードへ遡る照会の仕組み。仕様は確定済み。
- **B-4** — CI 再現のための `xen/` 内 `make sbom` 相当ターゲット。
- **B-5** — Xen 固有でない改善の上流（KernelSbom）への提案。
- **B-9 / B-11** — arm32、および検証済み 2 つ以外の defconfig でのパーサ網羅性。
  arm64 の知見から、欠落はアーキテクチャではなく**コンフィグオプション**
  （XSM/FLASK）に連動するとわかったため、今後の欠落はこちらに出る可能性が高い。
- **B-0 / B-2** — Safety Case リンクは保留。SPDX 3.1 の Safety Profile がまだ
  リリース候補であり、Xen FuSa SIG がそれを必要とするかも未確認のため。

本節は要約です。単一の情報源は `worklog/backlog.md` です。
