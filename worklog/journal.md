# 作業ジャーナル（日本語のみ）

本ファイルは、本プロジェクトのやり取りと作業を時系列で詳細に記録するものです。
後から社外関係者（Xen コミュニティのエンジニア）へ説明する資料の素材として活用します。

---

## 2026-07-04

### プロジェクト立ち上げ・要件整理

**やりたいこと（ユーザー提示）**
- 最新 Linux v7.0 に取り込まれた SPDX-SBOM ツールの使い方を文書化する。
- 分析結果を Xen ハイパーバイザーに取り込むためのドキュメント・スクリプトを作成する。
- 本作業は Git で管理し、やり取りを詳細にログとして残す。
- ログは後から社外関係者への説明資料作成に活用する。

**確認したやり取り（要点）**
- Xen 取り込みの目的: Xen 自体の SPDX を**自動生成**する仕組みを作ること。Safety
  プロファイルを適用させるため。
- 社外関係者: **Xen コミュニティのエンジニア**。
- ソース: Linux / Xen とも、これから Git で取得する。Linux は Linus（torvalds）
  リポジトリから、Xen は最新コードを取得。

**確認事項への回答（AskUserQuestion）**
- Safety の狙い: **両方**（SBOM 生成 + SPDX Relationships による Safety Case 文書の
  モデル化）。
- 初回スコープ: **文書化 + Linux 再現を先に**。Xen 適応は設計・PoC まで（本体実装は
  次段階）。
- Xen 対象範囲: **Xen 全体**（hypervisor + tools + libs）。
- 成果物の言語: **英語・日本語の両方**。作業ログは**日本語のみ**（成果物の日本語版を
  求めるのは翻訳の手間を減らすため）。
- プロジェクト名: 未定。暫定名 `xen-spdx-sbom` で進行（後から変更可）。

**事前 Web 調査で判明した Linux 側ツールの実態**
- 由来: TNG 製 KernelSbom（https://github.com/TNG/KernelSbom）が upstream 化。
- 配置: カーネルツリー `scripts/sbom/`。`make sbom` で起動（`all` に依存）。
  文書は `Documentation/tools/sbom/sbom.rst`。
- 仕組み: Kbuild が生成する `.<filename>.cmd` から依存関係の有向非巡回グラフ(DAG)を
  構築し、ルート成果物（bzImage・`.ko`）から辿って SPDX 3.0.1 形式の3文書を生成:
  `sbom-source.spdx.json` / `sbom-build.spdx.json` / `sbom-output.spdx.json`。
- 前提: `SRCARCH` 指定、src-tree/obj-tree 分離、`.cmd` の存在。現状 x86 / arm64。
  Python3。開発補助に reuse / pre-commit / ruff。
- 参考: LWN 記事 https://lwn.net/Articles/1058287/ , Phoronix。

**実現性の要点（調査時点の理解・要検証）**
- Xen のハイパーバイザー（`xen/`）は Linux Kbuild 由来のビルドシステムを採用しており、
  `.cmd` 機構が流用しやすい見込み。
- Xen の tools / libs は autotools + 素の Makefile 系で `.cmd` が無いため、別手法
  （compile_commands.json / strace ベース追跡 = KernelSbom の `sbom_analysis/` 相当）が必要。

**計画**
- 承認済み計画: `/home/kurokawa/.claude/plans/humming-chasing-peach.md`
- フェーズ 0（リポジトリ初期化・ログ基盤）→ 1（ソース取得）→ 2（Linux 再現・文書化）
  → 3（Xen ビルド解析）→ 4（Xen SPDX 設計 + PoC）→ 5（仕上げ）。

### フェーズ0: リポジトリ初期化とログ基盤
- `git init` 実施（本リポジトリ = `/home/kurokawa/bldwork/kernel/sbomspdx`）。
- ディレクトリ構成を作成: `docs/{en,ja}`, `worklog`, `scripts/xen-sbom-poc`,
  `analysis`, `external`。
- `.gitignore`（`external/`, `.venv/`, ビルド生成物）、`README.md`（EN/JA）、
  本ジャーナル、`decisions.md` を作成。
