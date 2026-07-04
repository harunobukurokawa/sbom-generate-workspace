# Xen パーサ実装 — 完全なハイパーバイザー SBOM の達成

*Phase B。`03-xen-spdx-design.md` の PoC を踏まえる。上流 Linux KernelSbom を
**無改変**のまま実行時注入で拡張し、ハイパーバイザー SBOM を約99%（ベースライン警告6件）
から **完全（未知コマンド0件・exit 0）** にする Xen 固有処理を実装する。*

## 1. 方針: 実行時注入（上流無改変）

`scripts/xen-sbom-poc/xen_parsers.py` が、上流に足りない Xen 対応を実行時に注入する。
`scripts/xen-sbom-poc/gen_xen_sbom.py` が準備を行い、上流 `sbom.py` を `runpy` で起動する
ため、上流パッケージ（`external/linux/scripts/sbom`）は一切改変しない。実行は
`scripts/xen-sbom-poc/generate-xen-sbom.sh`。

注入ポイント（いずれも呼び出し時に参照される上流のモジュールグローバル）:
- **コマンドパーサレジストリ** — `savedcmd_parser.DEFAULT_COMMAND_PARSER_REGISTRY` を
  `CommandParserRegistry(XEN_COMMAND_PARSERS + base_entries)` に差し替え（Xen を先頭に）。
- **`parse_inputs_from_commands`** — IfBlock/prelude 対応版に差し替え。`cmd_file` は
  import 時（install より前に推移的に発生）にこの名前を束縛するため、パッケージだけでなく
  **`cmd_file` 自身の名前空間**（`sbom.cmd_graph.cmd_file.parse_inputs_from_commands`）も
  差し替える。
- **ハードコード依存** — `hardcoded_dependencies.HARDCODED_DEPENDENCIES` を in-place 更新。
- **存在フィルタ** — ドライバが `xen_parsers.OBJ_TREE` を設定し、解析入力をツリー上に
  実在するファイルへ絞る（§3）。

## 2. ギャップがベースラインの見かけより大きかった理由

無改変 PoC の警告が6件だったのは**早期に失敗**していたため。あるコマンドが解析できないと
（例: `compat-build-header.py`）、グラフはそのファイルの入力へ降りるのを止める。パーサを
追加するたびにグラフは**より深く**辿られ、次の層の Xen 固有レシピが露出した。ゼロ到達は
反復的な作業となった。対応したレシピ群:

| レシピ / コマンド | 件数 | 対応 |
|-------------------|------|------|
| `compat-*.py`（build-header, build-source, xlat-header） | 約280 | `_parse_compat_tool`（汎用: stdin `<`・位置引数、`>`と実行系は除外） |
| `combine_two_binaries.py`（x86 boot） | 2 | `_parse_combine_two_binaries`（ファイル値オプション `--script/--bin1/--bin2/--map`） |
| `tools/binfile`（config 埋め込み） | 2 | `_parse_binfile`（blob + スクリプト、出力`.S`とシンボルは除外） |
| `mv -f X.new X`（生成ヘッダの確定） | 多数 | `_parse_mv_command`（`-f`対応、rename 元が入力） |
| bare `cat FILE`（例: `cat .banner`） | — | `_parse_cat_bare` |
| `*.init.o` セクションサイズ検証（`objdump\|while;do case;done`） | 約80 | split 前に prelude 除去、実体の `objcopy` は保持 |
| `include/xen/compile.h`（`if..then..fi`） | — | IfBlock 対応で then 節入力を保持 + hardcoded 依存 |
| `.banner`（`if..then echo\|figlet; else echo; fi`） | — | figlet/`else echo` は noop（版数文字列でソース来歴なし） |

## 3. 存在フィルタ（一時ファイル）

Xen の「`X.new` に生成してから `X` へ `mv`」というイディオムや、コード生成スクリプトへ
渡す論理的な*名前*引数は、ポストビルド SBOM 実行時にディスク上に存在しないパスを
パーサが参照させる。例: `include/compat/xen.h.new`（rename 済み）や `compat/xen.h`
（ファイルではなく名前）。上流ツールは存在しない依存を致命的エラーとして扱う。

ポストビルド SBOM は実在ファイルのみを参照すべきなので、解析入力を `OBJ_TREE` に対して
フィルタする（`_keep_existing`）。これはコマンド毎の特別扱いではない一般的で妥当な規則で、
一時/名前参照をきれいに除去する。（将来の上流化候補として `mv` を透過化し `X.new` の来歴を
`X` に伝播させる改善が考えられるが、ここでは存在フィルタで十分。）

## 4. 結果（検証済み）

`generate-xen-sbom.sh` を Xen 4.23-unstable（x86_64_defconfig、ルート `prelink.o`）、
fail-on-unknown 有効で実行:

- **exit 0。未知コマンド 0 件。**（ベースライン: 6）
- 残るのは無害な警告のみ（`.i`/`.py` の「primary purpose 推定不可」3件）。
- **カバレッジ: 1,519 ファイル**（無改変ベースライン: 1,442、**+77**）。新規に compat `.i`
  22、xlat `.lst` 20、Xen codegen `.py` 4、boot `.bin` 2、`include/xen/compile.h.in`、
  `.banner`、`tools/process-banner.sed` を含む。
- 妥当な SPDX 3.0.1 JSON-LD: build 3,554 要素（`software_File` 1,518）。
- サンプル: `analysis/xen-full/`。ユニットテスト: `scripts/xen-sbom-poc/tests/`（9件全パス）。

## 5. 上流化に向けて

Xen 対応はすべて `xen_parsers.py` の約200行に収まる。コマンドパーサは上流レジストリの
イディオム（`(pattern, parser)` エントリ）と `hardcoded_dependencies` に素直に対応するため、
Xen アーキ拡張として上流貢献しうる。IfBlock の then 節入力保持と存在フィルタは、より一般的な
改善として KernelSbom メンテナと議論する価値がある。
