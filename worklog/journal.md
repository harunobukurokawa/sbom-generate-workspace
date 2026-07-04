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
- フェーズ0 をコミット（`92f1fcc`）。

### フェーズ1: ソース取得（進行中）
- `scripts/fetch-sources.sh all` を実行。Linux（torvalds mainline, `--depth=1`）と
  Xen（xenbits mainline, `--depth=1`）を `external/` へ clone。

### 追加 Web 調査（フェーズ2/3/4 の当たり付け）
- **Linux ツール（LWN 1055009）**: `CONFIG_SBOM` を有効化し `make sbom` で post-build
  実行。`.cmd`（Kbuild が各出力の完全なビルドコマンドを記録）を解析し、カーネルイメージ
  ／モジュールをルートに依存グラフを再構築。SPDX 3.0.1、JSON-LD 直列化。3文書構成。
  約14コミット・4,086行の Python。現状 x86 / arm64 のみ。
- **Xen ビルドシステム（xen-devel / patchew）**: `xen/` は Kbuild 由来。`.cmd` ファイルを
  `dir/.target.cmd` 形式で生成し、`cmd_and_record` でコマンドライン・依存を記録。
  `xen/Rules.mk`・`xen/scripts/Kbuild.include`。既存ターゲットの `.cmd` を
  `$(foreach f,$(existing-targets),$(dir $(f)).$(notdir $(f)).cmd)` で読み込む。
  → **`xen/`（ハイパーバイザー）では Linux ツールの `.cmd` 解析ロジックが流用しやすい**
  という前提が裏付けられた（実ビルドで最終確認予定）。
  参考: https://lists.xenproject.org/archives/html/xen-devel/2015-12/msg01814.html
  （Kbuild import の初出）, 2020 の build system improvements パッチ群。

### フェーズ1 実績: ソース取得完了
- Linux: torvalds mainline を clone。`Makefile` は **VERSION=7 PATCHLEVEL=2
  SUBLEVEL=0 EXTRAVERSION=-rc1**（= v7.2-rc1）。**v7.0 専用タグは存在せず**、mainline は
  既に 7.2-rc1。ツール `scripts/sbom/` は実在（`sbom.py`, `sbom/`, `tests/`,
  `Documentation/tools/sbom/sbom.rst`）。→ 計画のリスク項目「v7.0 実在性」を解消。
- Xen: xenbits mainline を clone。HEAD `f0161d2`（2026-07-03）。`xen/Makefile` は
  **XEN_VERSION=4 SUBVERSION=23 EXTRAVERSION=-unstable**（= 4.23-unstable）。

### フェーズ2 実績: Linux ツールの精読・再現・文書化
- 精読: `sbom.py`（2フェーズ: cmd グラフ→SPDX グラフ）、`config.py`（全 CLI オプション）、
  `Makefile` の `sbom` ターゲット（約2246行）、`hardcoded_dependencies.py`、
  `cmd_graph/cmd_file.py`（`SAVEDCMD_PATTERN=^(saved)?cmd_.*?:=`）。
- **再現ビルド成功**: `make defconfig O=kernel_build` → `make sbom O=kernel_build -j16`。
  x86_64 defconfig。所要 **4分17秒**。3文書生成:
  - `sbom-source.spdx.json`  4.5MB / 13,796 要素（software_File 7,138 ほか）
  - `sbom-build.spdx.json`  27MB / 15,282 要素（build_Build 3,923 ほか）
  - `sbom-output.spdx.json` 34KB / 60 要素（software_Package 13 = bzImage + modules）
  - **SPDX 3.0.1** 確認（`@context: https://spdx.org/rdf/3.0.1/spdx-context.jsonld`、
    JSON-LD `@graph`）。JSON 妥当性 OK。
  - 注: `make sbom` は `--generate-used-files` を付けないため `sbom.used-files.txt` は
    未生成（仕様どおり）。ビルドログ末尾の exit 2 は最後の `ls` が当該ファイルを探して
    失敗しただけで、生成自体は成功。
- サンプル保存: `analysis/sample-sbom-output.spdx.json`（完全な output 文書 34KB）、
  `analysis/sample-sbom-{source,build}-excerpt.spdx.json`（type 毎2件・配列短縮の抜粋）、
  `analysis/linux-reproduction-stats.md`（統計）。※27MB の build 文書は `external/`
  （git-ignore）に残し、リポジトリには含めない。
- 成果物: `docs/{en,ja}/01-linux-sbom-tool.md`。再現手順は `scripts/run-linux-sbom.sh`。

### フェーズ3 実績: Xen ビルド解析
- `xen/`（ハイパーバイザー）は Kbuild 由来。`xen/scripts/Kbuild.include`:
  `dot-target=$(@D)/.$(@F)`、`if_changed` が `printf 'cmd_$@ := ...' > $(dot-target).cmd`。
- **`xen/tools/fixdep.c` は Linux と同一形式**を出力: `cmd_%s`（397行）、`source_%s`（352行）、
  `deps_%s`（354行）。→ KernelSbom の `cmd_file.py`（`(saved)?cmd_`、`source_` 検査、依存行）と
  **構造的に互換**。唯一差は Linux=`savedcmd_` / Xen=`cmd_` だが正規表現が両対応のため
  **無改変で `.cmd` 行解析が通る**見込み。
- 残ギャップ: `command_parser_registry.py`（gcc/ld/objcopy/`_parse_link_vmlinux_command` 等
  Linux 固有）。Xen の最終リンク（`xen-syms`, `xen.efi`, `mkelf32` 等）は未知コマンドとなり
  既定で失敗 → Xen 用パーサ追加 or `--do-not-fail-on-unknown-build-command`。
- `tools/`・`libs/`・`stubdom/` は autotools + 手書き Makefile で `.cmd` 無し →
  strace / compile_commands.json / パッケージ単位 SBOM の補完機構が必要。
- 成果物: `docs/{en,ja}/02-xen-build-analysis.md`。

### フェーズ4 実績: Xen SPDX 生成 設計 + PoC
- レジストリ精査: `command_parser_registry.py` は CC/LD/AR/NM/OBJCOPY/STRIP を
  **環境変数駆動の汎用パターン**で認識（`env_or_default_pattern`）。→ Xen の
  gcc/ld/objcopy/nm/ar/strip は無改変で認識される見込みと判明。Linux 固有は
  `link-vmlinux.sh`, `syscallhdr.sh`, `bin2c`, `mkuboot.sh` 等のスクリプト。
- **Xen ハイパーバイザー実ビルド成功**: `make -C xen XEN_TARGET_ARCH=x86_64 defconfig`
  → `-j16`。所要 **23秒**。成果物: `xen-syms`(26MB), `xen`(3.1MB)。`.cmd` **624個**生成。
  - `.cmd` 形式確認: `cmd_prelink.o := ld -melf_x86_64 -r -o prelink.o common/built_in.o ...`
  - `xen-syms` は2パスのシンボル埋め込みで特殊リンクされ **`.cmd` 無し** → ルート不適。
    → **ルートは `prelink.o`**（全 built_in.o を集約、`.prelink.o.cmd` あり）を採用。
- **PoC 成功**: 無改変 KernelSbom を Xen に適用（`scripts/xen-sbom-poc/run-xen-poc.sh`）。
  in-tree（src==obj）、`--do-not-fail-on-unknown-build-command --write-output-on-error`。
  exit 0。生成:
  - `sbom-build.spdx.json` 3.1MB / 3,280 要素（software_File **1,441**、build_Build 539）
  - `sbom-output.spdx.json` 25KB / 12 要素（software_Package 1 = prelink.o）
  - `sbom.used-files.txt` **1,442 ファイル**（C 419 / ヘッダ 505 / .o 490 / .S 23 / .a 3）
  - SPDX 3.0.1 妥当。→ **prelink.o からハイパーバイザーコアのソースまで追跡成功**。
- **未知コマンドは6警告のみ** = 必要な Xen 固有パーサは3系統: `mv -f X.new X`(compat
  header)、`python3 ./tools/compat-build-header.py`、`cat .banner; sed ... compile.h`。
  → **無改変で約99%完全、3パーサ追加で完全化**という定量結論。
- サンプル: `analysis/xen-poc/`（output 完全 + build 抜粋 + used-files + run.log）。
  巨大な build 本体(3.1MB)は抜粋化し本体は削除（再生成可能）。
- **Safety（両方対応）**: `analysis/xen-safety-case-relationships.example.spdx.json` に
  生成 SBOM/Package と Safety Case 文書（安全計画・要件・MISRA・変更管理）を SPDX
  Relationships で紐付ける例示モデルを作成。設計は `docs/{en,ja}/03-xen-spdx-design.md`。
- 成果物: `docs/{en,ja}/03-xen-spdx-design.md`（アーキテクチャ [A]再利用/[B]tools補完/
  [C]Safety リンカ、PoC 結果、次段階）。

### フェーズ5 実績: 仕上げ
- `README.md` に「Results at a glance」「Reproduce」節を追加し、各成果物へリンク。
- 本ジャーナルに全経緯を時系列で記録済み（社外説明資料の素材）。

## 2026-07-04（続き）Phase B: ハイパーバイザー SBOM の 100% 化

ユーザー確認: 次の重点は「ハイパーバイザー SBOM を100%化」、方式は「実行時注入」（上流無改変）。

### 実装（`scripts/xen-sbom-poc/`、上流 `external/linux` は無改変）
- `xen_parsers.py`: Xen 固有パーサ + IfBlock/prelude 対応版 `parse_inputs_from_commands`
  + 存在フィルタ + install。`gen_xen_sbom.py`（runpy で上流 sbom.py 起動）、
  `generate-xen-sbom.sh`（fail-on-unknown で実行し未知件数を集計）、`tests/`（9件）。

### 注入の要点（ハマりどころ）
- レジストリ（`DEFAULT_COMMAND_PARSER_REGISTRY`）は呼び出し時参照 → 差し替えが即効。
- だが `parse_inputs_from_commands` は `cmd_file` が import 時に束縛済みのため、
  **`cmd_file` 自身の名前空間も差し替える**必要があった（これに気付くまで IfBlock/prelude が
  効かなかった）。

### 反復的なゼロ到達（早期失敗が深部を隠していた）
無改変 PoC の警告6件は早期失敗の産物。パーサ追加でグラフが深く辿られ次の層が露出:
compat-*.py（約280件）→ combine_two_binaries.py → binfile/objdump検証prelude →
compile.h(if..then..fi) → .banner(if..then..else..fi) の順に潰し、最終的に **未知0件**。
- 一時ファイル問題: `mv X.new X` の `.new`（rename 済で不在）や名前引数 `compat/xen.h` が
  「file does not exist」エラーに → **obj-tree 存在フィルタ**で一括解決（ポストビルド SBOM は
  実在ファイルのみ参照すべき、という一般規則）。

### 結果（検証済み）
- **exit 0 / 未知コマンド 0 件**（ベースライン6件）。残警告は無害な型推定3件のみ。
- カバレッジ **1,442 → 1,519 ファイル（+77）**: compat `.i` 22、xlat `.lst` 20、
  codegen `.py` 4、boot `.bin` 2、compile.h.in、.banner、process-banner.sed 等。
- SPDX 3.0.1 妥当（build 3,554 要素 / software_File 1,518）。ユニットテスト9件全パス。
- サンプル: `analysis/xen-full/`。成果物: `docs/{en,ja}/04-xen-parsers-implementation.md`、
  `docs/{en,ja}/03` §5 と README を更新。

## 2026-07-05 B-2 の必要性調査（優先度の見直し）

「優先すべき B-2（Safety Case リンカ）の必要性は調査済みか？」という問いを受け、未実施だった
ため調査。結果、当初の「P1・FuSa 直結」は推論で**未確立**と判明。
- SPDX: 例の関係型は 3.0.1 core に実在するが、安全専用 **Safety Profile は SPDX 3.1（RC）**。
  → 今 3.0.1 で作ると作り直しリスク。例の `hasDeclaredLicense` 誤用も発見。
- Xen FuSa: ロードマップ wiki は bot 保護で取得不可。公式 FuSa ブログに **SBOM/SPDX 言及なし**。
  → SIG の critical path にある確証なし。
- 対応: `backlog.md` を改訂。B-2 を保留、必要性確認タスク **B-0** を新設、推奨順序を
  **B-1 → B-3 → B-0 →（Yes なら）B-2 → …** に変更。教訓: 優先度は需要と標準成熟度の裏取り後に
  確定する。

## 総括（社外＝Xen コミュニティ向け説明の骨子）

- **問い**: Linux v7 に入った SPDX-SBOM ツール（`scripts/sbom/`）を Xen 自身の SPDX
  自動生成に再利用できるか。目的は Xen FuSa（IEC 61508 / ISO 26262）支援。
- **答え（実証済み）**: **ハイパーバイザー（`xen/`）については、無改変で直接再利用できる。**
  - 根拠1: Xen `xen/` は Linux Kbuild 由来で、`fixdep.c` が `cmd_`/`source_`/`deps_` を
    出力 → KernelSbom の `.cmd` パーサと構造互換。
  - 根拠2: 実 PoC で `prelink.o` を起点に **1,442 ファイル**を追跡し妥当な SPDX 3.0.1 を
    生成。未知コマンドは3系統のみ（`mv` / `compat-build-header.py` / `compile.h`）。
  - 汎用ツール（gcc/ld/objcopy/nm/ar）は環境変数駆動で既に認識される点が効いた。
- **ハイパーバイザーの完全化（Phase B 完了）**: 約200行の Xen 拡張（実行時注入・上流無改変）で
  **未知コマンド0件・exit 0**、1,519 ファイルを網羅。ギャップは当初想定の3コマンドより大きく、
  compat-*/binfile/combine/compile.h/.banner の各ファミリ + 存在フィルタで解消。
- **残作業（次段階）**: (1) 外部 SPDX バリデータでの検証（`@context` 展開後）、(2) `tools/`・
  `libs/` を strace/compile_commands.json で補完、(3) Safety Case を SPDX Relationships で
  紐付けるリンカの正式化（FuSa SIG と整合）、(4) Xen 拡張の上流貢献の検討。
- **成果物**: `docs/en/` `docs/ja/`（01 Linux ツール / 02 Xen ビルド解析 / 03 設計+PoC）、
  再現スクリプト（`scripts/`）、サンプル SBOM（`analysis/`）。
