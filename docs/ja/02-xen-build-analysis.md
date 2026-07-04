# SPDX-SBOM 生成のための Xen ビルドシステム解析

*解析対象: Xen mainline `4.23-unstable`（clone HEAD `f0161d2`、2026-07-03）。
`01-linux-sbom-tool.md` の Linux KernelSbom ツールと比較。*

## 1. 問い

Linux カーネルの `.cmd` ベース SBOM 生成器（`scripts/sbom/`）を、Xen の SPDX SBOM
生成に再利用できるか？ Xen は性質の異なる2つのビルド領域に分かれるため、領域ごとに
回答します。

| Xen 領域 | ビルドシステム | `.cmd` 生成 | 再利用の見込み |
|----------|----------------|-------------|----------------|
| `xen/`（ハイパーバイザー） | **Kbuild 由来**（Linux から移植） | **あり** | **高** — パーサはほぼ互換 |
| `tools/`, `stubdom/`, `libs/` | **autotools + 手書き Makefile** | なし | 低 — 別機構が必要 |

## 2. ハイパーバイザー（`xen/`）— 高い互換性

Xen のハイパーバイザービルドは数年前に Linux から Kbuild を移植しています。関連ファイルは
`xen/Rules.mk` と `xen/scripts/Kbuild.include`。`.cmd` 機構は Linux とほぼ同一です。

- `dot-target = $(@D)/.$(@F)` → `dir/.<target>.cmd` を生成（命名も同じ）。
- `if_changed` がコマンドラインを書き出す:
  `printf '%s\n' 'cmd_$@ := $(make-cmd)' > $(dot-target).cmd`。
- `if_changed_dep` は `tools/fixdep` を実行し依存も記録する。

決定的な点として、**Xen の `fixdep`（`xen/tools/fixdep.c`）は KernelSbom のパーサが
期待するのと同じ行形式**を出力します。

| Xen `fixdep.c` が出力する行 | KernelSbom `cmd_file.py` の期待 | 一致 |
|------------------------------|--------------------------------|------|
| `cmd_%s := %s`（397行目） | `SAVEDCMD_PATTERN = ^(saved)?cmd_.*?:=` | ✅（`(saved)?` は任意） |
| `source_%s := %s`（352行目） | `source_` エントリを要求 | ✅ |
| `deps_%s := \` + `<tgt>: $(deps_%s)`（352–382） | 依存行 `<output>: <dependency>` | ✅ |

**唯一の差:** 新しい Linux は `savedcmd_<target> :=`、Xen は依然 `cmd_<target> :=` を
書く。KernelSbom の正規表現は `saved` 接頭辞を任意にしているため、**`.cmd` 行の素の
解析は Xen でも無改変で動作する。**

### ハイパーバイザーに残るギャップ: コマンドパーサレジストリ

KernelSbom は依存一覧を読むだけでなく、*ビルドコマンド自体を解析*して依存一覧に無い
入力を復元します。これは
`sbom/cmd_graph/savedcmd_parser/command_parser_registry.py` が担い、Linux 固有コマンド
ごとのパーサを持ちます。例:

- 汎用のコンパイル/リンク（`gcc`, `ld`）
- `objcopy`, `dd`, `cat`, `sed`
- `_parse_link_vmlinux_command` — Linux の **`vmlinux` リンク**手順

Xen の最終リンクターゲットは異なり（`xen-syms`, `xen.efi`, `xen` イメージ、アーキ別の
リンクスクリプト）、独自のイメージ構築手順（例: `arch/x86/boot`, `mkelf32`, `efi`）を
持ちます。KernelSbom は既定で未知のビルドコマンドで**失敗**するため、これら Xen 固有
コマンドは次のいずれかで対応が必要です。

1. レジストリに新規パーサとして追加する（推奨・完全なグラフ）、または
2. `--do-not-fail-on-unknown-build-command` で許容する（手早く開始・不完全なグラフ）。

`SRCARCH` の前提と x86/arm64 のみという制約も該当します。Xen のアーキ名（`x86`, `arm`）の
対応付けが必要です。

## 3. tools/libs 領域 — 別機構が必要

`tools/`, `stubdom/`, `libs/` は autotools（`configure.ac`, `configure`）+ 手書き
Makefile/`tools/Rules.mk` の下にあり、`.cmd` を生成**しません**。したがって cmd グラフ
方式では捕捉できません。選択肢（上流 KernelSbom の `sbom_analysis/` の発想に沿う）:

- **compile_commands.json**（`bear` またはコンパイララッパ経由）でファイル毎の
  コンパイル入力を復元。
- ビルドの **strace ベースのファイル追跡**で、読み取りのために開かれた全ファイルを
  捕捉 — 最もビルドシステム非依存で、KernelSbom 自身の解析ツールと一致。
- **パッケージ単位 SBOM**（粗粒度）: tools/libs をファイル来歴ではなく、バージョン・
  ライセンスを持つ SPDX Package として記述。

機能安全のスコープでは**ハイパーバイザーが主たる認証対象**であるため、段階的な計画
（まずハイパーバイザーをファイル単位、tools/libs は後段・粗粒度）が妥当です。

## 4. 結論

- **ハイパーバイザー（`xen/`）:** KernelSbom の `.cmd`/`fixdep` 解析は**小改修**で
  再利用可能 — 主に Xen 固有のリンク/イメージコマンドのパーサ追加とアーキ対応付け。
  これを最初の対象とし、PoC の基礎とする。
- **tools/libs:** 補完機構（strace または compile_commands.json）が必要。今回のパスでは
  設計のみで未実装。

提案アーキテクチャ、Safety Case の関連付けモデル、PoC 結果は `03-xen-spdx-design.md` を
参照してください。
