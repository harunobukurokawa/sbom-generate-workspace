# 06. ARM64 SBOM 生成のパーサー欠落分析と是正

**対象ビルド**: Xen 4.23-unstable, `arm64_defconfig`, `aarch64-linux-gnu-gcc 11.4.0`
**KernelSbom**: Linux mainline `scripts/sbom`（**無改造**）
**測定日**: 2026-08-06
**結論**: ARM64 固有の欠落はコマンドパーサー **2 種のみ**。ランタイム注入で解消し、
未知コマンド 0 件で SBOM 生成が完走した。KernelSbom 本体の変更は不要。

---

## 1. サマリ

| 項目 | 是正前 | 是正後 |
|------|--------|--------|
| 未知コマンド | （計測不能） | **0 件** |
| `sbom.used-files.txt` | 1 件 | **895 パス**（`wc -l` は末尾改行が無いため 894 と出力） |
| `sbom-build.spdx.json` | 7 elements / 2.2 KB | **1,951 elements / 1.5 MB** |
| KernelSbom への変更 | なし | **なし（維持）** |

是正後の内訳（`sbom-build.spdx.json`, 1,951 elements）:

| 型 | 件数 |
|----|------|
| `software_File` | 894 |
| `Relationship` | 758 |
| `build_Build` | 290 |
| `simplelicensing_LicenseExpression` | 5 |
| その他（Document / Agent / CreationInfo / Sbom） | 4 |

追跡されたファイル種別（895 パスの内訳、重複あり）: `.h` 359 / `.c` 222 / `.o` 281 /
`.S` 19 / `.a` 2。

895 パスのうち `software_File` 要素になるのは 894 個。差の 1 個はルート成果物
`prelink.o` で、これは `sbom-output.spdx.json` 側に置かれる。また
`../../../usr/bin/dash`（`/bin/sh` の実体）が含まれる — コード生成を実行した
シェル自身が依存として追跡されたもので、異常ではない。

---

## 2. 根本原因: `--obj-tree` の指定階層ずれ

当初 SBOM は 7 elements・追跡ファイル 1 件（`prelink.o` 自身のみ）しか生成されず、
これを「パーサーがシェル構文を解析できていない」と誤診していた。**実際の原因は
呼び出し側の引数ミスであり、パーサーの能力とは無関係だった。**

Xen のハイパーバイザは Xen リポジトリの `xen/` サブディレクトリでビルドされる。
`.cmd` ファイル内のパスは、この**ビルドディレクトリ相対**で記録される。

```
リポジトリ root : /workspace/xen
ビルドディレクトリ: /workspace/xen/xen      ← .cmd 内のパスはここが基準
.prelink.o.cmd  : cmd_prelink.o := aarch64-linux-gnu-ld ... common/built_in.o ...
```

`--obj-tree /workspace/xen`（リポジトリ root）を渡すと、`common/built_in.o` は
`/workspace/xen/common/built_in.o` へ解決される。これは存在しない。

```
✗ /workspace/xen/common/built_in.o        （誤った解決先・非存在）
✓ /workspace/xen/xen/common/built_in.o    （実体）
```

### 2.1 なぜ無警告で全滅したか

`xen_parsers.OBJ_TREE` が設定されている場合、`_keep_existing()` が解析済み入力を
「ディスク上に実在するファイル」へ絞り込む。この絞り込みは**警告を出さない**
（本来は `X.new` → `mv` → `X` のような一時パスを落とすための機構）。

結果として、パーサーは正しく入力を抽出していたのに、直後に全件が静かに捨てられて
いた。パーサーを疑う材料だけが残り、原因が隠蔽された。

```
ld パーサーの抽出結果（正しい）:
  ['prelink.o', 'common/built_in.o', 'drivers/built_in.o', 'lib/built_in.o',
   'xsm/built_in.o', 'arch/arm/built_in.o', 'arch/arm/arm64/lib/lib.a', 'lib/lib.a']
        ↓ _keep_existing()（obj-tree が誤りのため全件非存在）
  []                                    ← 無警告で全滅
```

### 2.2 副作用として現れた症状

`Cannot compute hash for /workspace/xen/.config because file does not exist` も
同一原因である（実体は `/workspace/xen/xen/.config`）。調査途中でこれを
`/workspace/xen/.config` へコピーして回避したが、これは対症療法であり、
obj-tree の是正にあわせて撤去した。

### 2.3 正しい呼び出し

`gen_xen_sbom.py` の第 2 引数（`<xen_hv_dir>`）は名前どおり
**ハイパーバイザディレクトリ**を指す。リポジトリ root ではない。

```bash
# 正しい
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom  /path/to/xen/xen  analysis/arm64  prelink.o

# 誤り（本件の原因）
#   ... /path/to/xen  analysis/arm64  xen/prelink.o
```

---

## 3. ARM64 固有の真の欠落: XSM/FLASK ポリシーコード生成

obj-tree を是正すると、グラフが実際に走査され、未知コマンドは **2 種のみ**に
絞られた。

```
/bin/sh ./xsm/flask/policy/mkflask.sh awk xsm/flask/include \
    ./xsm/flask/policy/security_classes ./xsm/flask/policy/initial_sids

/bin/sh ./xsm/flask/policy/mkaccess_vector.sh awk xsm/flask/include \
    ./xsm/flask/policy/access_vectors
```

これが x86 PoC で現れなかった理由は明確である: **`arm64_defconfig` は XSM/FLASK
を有効化するが、x86_64 の `defconfig` は有効化しない。** アーキテクチャ差ではなく
**コンフィグ差**が欠落の実体であり、ARM64 対応の本質は「ARM64 用パーサー」ではなく
「有効化される機能に応じたパーサーの網羅」である。

### 3.1 引数構造と実装上の注意

```
/bin/sh  <script>.sh  <awk>  <output_dir>  <policy_file>...
   [0]        [1]      [2]       [3]           [4:]
```

入力はスクリプト自身とポリシー定義ファイル。`awk`（インタプリタ名）と
**出力ディレクトリ**は入力ではない。

出力ディレクトリの除外は明示的に行う必要がある。`_keep_existing()` は
`os.path.exists()` で判定するが、**これはディレクトリにも True を返す**ため、
除外しないと `xsm/flask/include` が「ファイル」として SBOM に混入する。
この落とし穴はユニットテスト
`TestFlaskCodegenParser.test_awk_and_output_directory_are_dropped` で固定した。

---

## 4. tree-sitter-bash の実測評価: 本ビルドでは不採用

本 PoC の当初動機は「複雑なシェル構文（`if-then-else` / `while` / パイプ）が
正規表現ベースでは解析できない」という仮説だった。**実測はこの仮説を支持しなかった。**

### 4.1 測定方法

ARM64 ビルドの全 `.cmd` から `savedcmd` **303 件**を抽出し、
「Xen 拡張あり」と「当該パーサーを外した版」で、各コマンドをどのパーサーが
獲得するかを比較した。

### 4.2 結果

| 追加パーサー | 未知を救済 | 上流から奪取 | 評価 |
|--------------|-----------|-------------|------|
| `_parse_ld_command` | 0 件 | **23 件** | 純粋な退行 |
| `_parse_complex_shell_command`（tree-sitter） | 0 件（下記 4.3） | **7 件** | 純粋な退行 |

**`_parse_ld_command` は不要だった。** 上流 KernelSbom は既に
`^([^\s]+-)?ld\b` を持つ（上流レジストリは全 61 エントリ）。追加は上流の
実装を弱い自作実装で置き換えるだけだった。

さらに、追加したパターン `.*aarch64-linux-gnu-ld\b|.*ld\b` は**過剰マッチ**する。
`.*ld\b` は「`build` を含む任意のコマンド」に一致してしまう:

```
match=True   gcc -Ibuild/include -c foo.c -o foo.o        ← gcc を ld パーサーが奪う
```

Xen 拡張は上流レジストリ全体より**先に**評価されるため、緩いパターンは上流が
正しく処理できるコマンドを無警告で奪う。これは警告の出ない退行であり、
回帰テスト `TestXenPatternsDoNotShadowUpstream` で固定した。

### 4.3 tree-sitter の「救済 19 件」が実体を持たない理由

レジストリ単体でのパターンマッチ計測では、`objdump -h X | while read ...` 形式
19 件を tree-sitter が「救済」しているように見える。しかし**実パイプラインでは
これらはレジストリに到達しない。**

`xen_parse_inputs_from_commands()` は、コマンド分割の**前**に
`_VALIDATION_PRELUDE` 正規表現で `*.init.o` のセクションサイズ検証ループを除去する。
同様に `if..then..fi` は `IfBlock` として分岐が処理される。すなわち既存実装が
これらのシェル構文を先に吸収しており、tree-sitter が寄与する余地はなかった。

実証: `_VALIDATION_PRELUDE` と `IfBlock` 処理を持つ既存実装のまま、tree-sitter を
外して本番ドライバを実行 → **未知コマンド 0 件で完走**。

### 4.4 既存 PR ドキュメントの数値訂正

`TREE_SITTER_INTEGRATION.md` に記載の以下の数値は**実測値ではない**（実装前の
期待値であり、本 PoC の測定で否定された）。同ファイルに訂正を追記済み。

| 記載 | 実測 |
|------|------|
| 解析成功率 48% → 99.6% | 是正前の 48% は未検証。既存実装のまま未知 0 件 |
| files 1,847 / relationships 2,156 / 3.2 MB | files **894** / relationships **758** / **1.5 MB** |

### 4.5 tree-sitter-bash の扱い（実装は未完成）

レジストリへの登録は**撤去**した（本ビルドでは純粋な退行のため）。加えて、
実装自体が**未完成**であることを測定で確認した。

| 機能 | 状態 |
|------|------|
| AST 構築・制御フロー抽出 | ✓ 動作（`then_body` / `else_body` を復元できる） |
| I/O ファイル抽出 | ✗ **未実装**。`src/shell_parser.js` の `extractIOFiles()` が常に空配列を返す |
| Python ラッパーの JSON 分離 | ✗ **バグ**。Node 側が pretty-print された JSON を 2 ブロック出力するが、`shell_parser_wrapper.py` は `lines[0]`（1 行目のみ）を `json.loads()` するため失敗し、無警告で正規表現フォールバックに落ちる |

結果として `ParseResult.inputs` / `outputs` は常に空であり、
`tests/test_tree_sitter_parser.py` の 5 件が失敗する。これらのテストは
**将来の実装が満たすべき仕様**として保持し、クラス全体に理由付きの
`@unittest.skip` を付与した（CI を壊さず、未完成であることを可視化する）。

- 保持するコード: `src/shell_parser.js`、`scripts/shell_parser_wrapper.py`、
  `scripts/xen-sbom-poc/tree_sitter_parser.py`。Node.js 12 系での互換性修正
  （オプショナルチェーニング撤去）は適用済みで、AST 解析部分は動作する。
- **完成は critical path ではない。** tree-sitter なしで未知コマンド 0 件を
  達成しているため、投資対効果が現時点では無い。
- 再評価の条件: `_VALIDATION_PRELUDE` の正規表現で扱いきれないシェル構文が将来の
  ビルドに現れた場合。**その際は本節の測定手順（4.1）で「救済 > 奪取」を実証し、
  かつ上記 3 点を完成させてから**採用すること。

---

## 5. 是正内容（KernelSbom 無改造の維持）

「KernelSbom は無改造」という本プロジェクトの設計原則は維持されている。
是正はすべて既存のランタイム注入機構
（`install_xen_extensions()` による `DEFAULT_COMMAND_PARSER_REGISTRY` への前置）
の内側で完結した。

`scripts/xen-sbom-poc/xen_parsers.py`:

1. `_parse_flask_codegen()` を追加し、`XEN_COMMAND_PARSERS` に登録（狭いパターン
   `.*xsm/flask/policy/mk(flask|access_vector)\.sh\b`）。
2. `_parse_ld_command()` を削除（上流に既存・過剰マッチ）。
3. tree-sitter パーサーのレジストリ登録を撤去。
4. `XEN_COMMAND_PARSERS` に「パターンを狭く保つ」旨のコメントを追記。

テスト（`scripts/xen-sbom-poc/tests/test_xen_parsers.py`, 計 13 件パス）:

- `TestFlaskCodegenParser`（3 件）— 実ビルドで観測したコマンド文字列を使用。
  出力ディレクトリ混入の回帰も固定。
- `TestXenPatternsDoNotShadowUpstream`（1 件）— 上流所有コマンドを Xen 側の
  パターンが奪わないことを検証。`build` 部分文字列を含む gcc コマンドを含む。

---

## 6. 再現手順

```bash
# 1. ARM64 Xen をビルド（中間 .o を残す＝clean せずに実行）
cd <xen>/xen
XEN_TARGET_ARCH=arm64 make arm64_defconfig
CROSS_COMPILE=aarch64-linux-gnu- XEN_TARGET_ARCH=arm64 make -j"$(nproc)"

# 2. SBOM 生成（第 2 引数はハイパーバイザ dir = <xen>/xen）
cd <workspace>
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom  <xen>/xen  analysis/arm64  prelink.o

# 3. ユニットテスト
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/ -q
```

`gen_xen_sbom.py` は `--do-not-fail-on-unknown-build-command` を渡さないため、
未知コマンドが 1 件でもあれば出力されずに失敗する。**出力が生成されること自体が
「未知コマンド 0 件」の証明**である。

### 6.1 前提ツール

| ツール | 本測定での版 | 備考 |
|--------|-------------|------|
| `aarch64-linux-gnu-gcc` | 11.4.0 | `gcc-aarch64-linux-gnu` |
| Python | 3.10.12 | KernelSbom は 3.10+ |
| Node.js | 12.22.9 | tree-sitter 実験用。SBOM 生成には**不要** |

---

## 7. 教訓

1. **無警告のフィルタは誤診を生む。** `_keep_existing()` の静かな全件削除が、
   引数ミスをパーサー欠陥に見せかけた。今後この機構が全件を落とした場合は
   警告を出す価値がある（バックログ B-9）。
2. **上流レジストリを確認してから追加する。** 61 エントリの既存パーサーを
   確認せずに `ld` パーサーを書き、退行を作り込んだ。
3. **前置レジストリのパターンは狭くする。** Xen エントリは上流全体より先に
   評価されるため、緩いパターンは無警告で上流を奪う。
4. **アーキテクチャ差ではなくコンフィグ差を見る。** 欠落の実体は「ARM64」ではなく
   「XSM/FLASK が有効」だった。他の defconfig でも同種の欠落が予想される
   （バックログ B-10）。
5. **期待値を実測値として文書化しない。** `TREE_SITTER_INTEGRATION.md` の
   「99.6%」は測定されておらず、実測は仮説を否定した。
