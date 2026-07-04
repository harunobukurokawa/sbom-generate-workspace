# Linux カーネル SPDX-SBOM ツール（KernelSbom）

*分析対象: Linux mainline `v7.2-rc1`（執筆時点でツールを含むツリー。なお `v7.0`
専用タグは存在せず、mainline は既に 7.2-rc1）。ツールのパス: `scripts/sbom/`。*

## 1. 概要

`KernelSbom` は純 Python 製スクリプト（`scripts/sbom/sbom.py`）で、**カーネルビルド
成功後**に実行し、**SPDX 3.0.1** 形式（JSON-LD 直列化）の **SBOM（Software Bill of
Materials）** 文書を生成します。元は TNG Technology Consulting が
[KernelSbom リポジトリ](https://github.com/TNG/KernelSbom)で開発し、mainline カーネル
ツリーに取り込まれたものです。

**最大3つ**の文書と、任意で1つのフラットファイルを生成します。

| ファイル | 内容 |
|----------|------|
| `sbom-source.spdx.json` | ビルドに関与した全ソースファイルと、各々のライセンス式。*（out-of-tree ビルド時のみ）* |
| `sbom-output.spdx.json` | 最終成果物（カーネルイメージ + `.ko` モジュール）とビルドメタデータ（環境変数、`.config` のハッシュ）。 |
| `sbom-build.spdx.json` | 全中間成果物、各々の正確なビルドコマンド、入力→出力の関係。source/output 文書のファイルを取り込む。 |
| `sbom.used-files.txt` | *（任意、`--generate-used-files`）* 使用ソースファイルのフラットな一覧。 |

**要件:** Python **3.10 以上**。サードパーティライブラリ不要。

## 2. 実行方法

### 2.1 `make sbom` ターゲット経由（推奨）

```bash
make defconfig O=kernel_build
make sbom O=kernel_build -j"$(nproc)"
```

`make sbom` はまずカーネルをビルドし（イメージ、`include/generated/autoconf.h`、
`CONFIG_MODULES` 有効時は `modules`/`modules.order` に依存）、その後スクリプトを
起動します。3つの SPDX ファイルは**オブジェクトツリーのルート**（`kernel_build/`）に
出力されます。

Makefile の該当箇所（`Makefile` の `sbom` ターゲット、約2246行目付近）は次のように
展開されます。

```make
cmd_sbom = printf "%s\n" "$(KBUILD_IMAGE)" >"$(tmp-target)"; \
           $(if $(CONFIG_MODULES),sed 's/\.o$$/.ko/' $(objtree)/modules.order >> "$(tmp-target)";) \
           $(PYTHON3) $(srctree)/scripts/sbom/sbom.py \
               --src-tree $(abspath $(srctree)) \
               --obj-tree $(abspath $(objtree)) \
               --roots-file "$(tmp-target)" \
               --output-directory $(abspath $(objtree)) \
               --generate-spdx \
               --package-license "GPL-2.0 WITH Linux-syscall-note" \
               --package-version "$(KERNELVERSION)" \
               --write-output-on-error;
```

他プロジェクト（例: Xen）へ応用する際に押さえるべき点:
- **ルート（roots）** はカーネルイメージ + 全モジュール（`.ko`）。`modules.order` の
  `.o` を `.ko` に書き換えて生成する。
- `--package-license "GPL-2.0 WITH Linux-syscall-note"` と
  `--package-version $(KERNELVERSION)` はカーネル固有で、Makefile から渡される
  （スクリプトにハードコードされていない）。
- `sbom-source.spdx.json` は `building_out_of_srctree`（= `O=` 使用時）のときだけ
  `sbom_targets` に加わる。

### 2.2 スタンドアロン実行

```bash
SRCARCH=x86 python3 scripts/sbom/sbom.py \
    --src-tree . \
    --obj-tree ./kernel_build \
    --roots arch/x86/boot/bzImage \
    --generate-spdx \
    --generate-used-files \
    --prettify-json \
    --debug
```

`make` の外で実行するとコンパイル時の環境変数が得られず、記録できません。少なくとも
`SRCARCH` は設定してください。

モジュールをルートに含める場合:

```bash
echo "arch/x86/boot/bzImage" > sbom-roots.txt
sed 's/\.o$/.ko/' ./kernel_build/modules.order >> sbom-roots.txt
SRCARCH=x86 python3 scripts/sbom/sbom.py \
    --src-tree . --obj-tree ./kernel_build \
    --roots-file sbom-roots.txt --generate-spdx
```

## 3. 仕組み

2フェーズ構成（`scripts/sbom/sbom.py:main`）:

**フェーズ1 — cmd グラフの構築**（`sbom/cmd_graph/`）: ノードがファイル、エッジが
*「ファイル A はファイル B のビルドに使われた」* を表す有向非巡回グラフ。各ルート
成果物から出発し、依存を3つの情報源から収集します。

1. **`.cmd` ファイル**（主）— Kbuild が各出力について `dir/.<name>.cmd` を書き出し、
   正確なコマンドと明示的な依存一覧を記録する。`sbom/cmd_graph/cmd_file.py` +
   `deps_parser.py` が解析。
2. `.S` アセンブリ内の **`.incbin` 文**（`sbom/cmd_graph/incbin_parser.py`）。
3. **ハードコード依存**（`sbom/cmd_graph/hardcoded_dependencies.py`）—
   Makefile/Kbuild で定義され `.cmd`/`.incbin` に現れない依存（例: `asm-offsets.h`）
   の小さな手動マップ。不完全と明記されているが、グラフは約99%の完全性に達する。

グラフはバージョン管理下のソースファイルに到達するまで再帰的に展開されます。

**フェーズ2 — SPDX 文書の生成**（`sbom/spdx_graph/`, `sbom/spdx/`）: グラフ内の各
ファイルについて `SPDX-License-Identifier` ヘッダを解析し、ハッシュを計算し、拡張子・
パスからファイル型を推定し、ビルド関係を記録する。各ルート出力にはさらに
version/license/copyright を持つ SPDX `Package` 要素を付与。出力は JSON-LD に直列化
（`sbom/spdx/serialization.py`）。

### ソースツリー と オブジェクトツリー

ファイルは、ソースツリーにあり**かつ**オブジェクトツリーに**ない**とき「ソース」と
分類されます。したがって **out-of-tree ビルド（`O=objtree`）が推奨**です。in-tree
ビルド（src == obj）では区別が信頼できないため `sbom-source.spdx.json` は生成されず、
ソースは `sbom-build.spdx.json` に統合され、`sbom.used-files.txt` に全ファイルが列挙
されます。

## 4. コマンドラインオプション（`sbom/config.py` より）

| オプション | 既定値 | 意味 |
|-----------|--------|------|
| `--src-tree` | `../linux` | カーネルソースツリー |
| `--obj-tree` | `../linux/kernel_build` | ビルド出力ディレクトリ |
| `--roots` / `--roots-file` | *（必須・排他）* | ルート成果物（obj-tree 相対） |
| `--generate-spdx` | off | 3つの SPDX 文書を生成 |
| `--generate-used-files` | off | `sbom.used-files.txt` を生成 |
| `--output-directory` | `.` | 出力先 |
| `--do-not-fail-on-unknown-build-command` | off（=失敗する） | 未知コマンドエラーを警告に降格 |
| `--write-output-on-error` | off | エラーでも（不完全な）文書を書き出す |
| `--spdxId-prefix` | `urn:spdx.dev:` | 全 `spdxId` の接頭辞 |
| `--build-type` | `urn:spdx.dev:Kbuild` | Build 要素の SPDX `buildType` |
| `--build-id` | *（Build の spdxId）* | SPDX `buildId` |
| `--package-license` | `NOASSERTION` | 全 Package のライセンス |
| `--package-version` | なし | 全 Package のバージョン |
| `--package-copyright-text` | あれば `COPYING` | 全 Package の著作権表記 |
| `--prettify-json` | off | JSON を整形出力 |

## 4.1 再現結果（検証済み）

2026-07-04 に **Linux v7.2-rc1**、`x86_64 defconfig`、out-of-tree
（`O=kernel_build`）、Python 3.10.12、`make sbom -j16` で再現。ビルド所要 **4分17秒**。
3文書すべてが生成され、妥当な SPDX 3.0.1 JSON-LD
（`@context: https://spdx.org/rdf/3.0.1/spdx-context.jsonld`）でした。

| 文書 | サイズ | 要素数 | 特記 |
|------|--------|--------|------|
| `sbom-source.spdx.json` | 4.5 MB | 13,796 | `software_File` 7,138 |
| `sbom-build.spdx.json` | 27 MB | 15,282 | `build_Build` 3,923 |
| `sbom-output.spdx.json` | 34 KB | 60 | `software_Package` 13（bzImage + モジュール） |

サンプルは `analysis/` に保存（`sample-sbom-output.spdx.json` は完全な output 文書、
source/build は短縮抜粋）。再現は `scripts/run-linux-sbom.sh`。注: `make sbom` は
`--generate-used-files` を渡さないため、当ターゲットでは `sbom.used-files.txt` は
生成されません。

## 5. 制約

- **アーキテクチャ:** 現状 x86 と arm64 のみ。
- **カスタム JSON-LD `@context`:** サイズ削減のため `spdxId` にカスタム接頭辞を定義。
  仕様準拠だが対応する SPDX ツールは限られ、他ツールに渡す前に context の *展開* が
  必要な場合がある。
- **ハードコード依存の隙間:** グラフ完全性は約99%（100%ではない）。
- **未知のビルドコマンド:** 既定では未知の `.cmd` コマンドで*失敗*する。
  `--do-not-fail-on-unknown-build-command` で不完全な SBOM を許容して続行可能。

## 6. Xen にとっての意味

本ツールの中核（cmd グラフ生成部）は **Kbuild の `.cmd` ファイル**に依存します。Xen
ハイパーバイザー（`xen/`）は **Kbuild 由来**のビルドシステムを採用し、同じ
`dir/.<name>.cmd` を生成するため、`.cmd` 解析のアプローチを Xen ハイパーバイザーに
再利用できます。Xen の `tools/`・`libs/` は別のビルドシステムであり、補完的な手法が
必要です。`02-xen-build-analysis.md` を参照してください。
