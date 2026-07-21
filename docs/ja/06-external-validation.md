# 生成 SPDX 3.0.1 文書の外部バリデータ検証（B-1）

*これまで、生成 SBOM の「妥当性」は簡易な JSON-LD 構造検証（`@graph` の存在、
要素数の確認）のみで確認されてきた。本書は、実際に生成した文書
（`analysis/xen-full/`）を SPDX 公式ツールで検証した結果と、その過程で
判明した2つの注意点（既知・無害）を記録する。*

## 1. `spdx-tools`（pip: `spdx-tools`、通称 "pyspdxtools"）が使えない理由

`spdx-tools` は SPDX プロジェクト自身の Python 実装（`spdx/tools-python`）
である。本調査時点の最新版（0.8.5）の `spdx3` サブパッケージは以下のみを
サポートする:

- **SPDX 2.x** 文書（tag-value / RDF-XML / 2.x JSON / XML / YAML —
  `spdx_tools.spdx.parser.parse_anything.parse_file`）のパース、
- それを SPDX 2.x として検証（`validate_full_spdx_document`）、
- **プロトタイプ**の SPDX 3.0 モデルへの「bump」変換と JSON-LD 出力
  （`spdx_tools.spdx3.writer.json_ld`）。

つまり SPDX-3 対応は一方向の**2.x → 3.0 移行エクスポート**であり、
**既存の SPDX 3.0.1 JSON-LD を読み込んで検証する経路は存在しない**。
本プロジェクトが生成するような SPDX 3.0.1 JSON-LD ファイルを読むコードパスは
このライブラリに一切なく、B-1 の目的には使用できない。

（`spdx_tools/spdx3/clitools/pyspdxtools3.py` と
`spdx_tools/spdx/parser/parse_anything.py` をインストール済みパッケージ内で
直接読んで確認済み。ドキュメントの記載だけに依拠した結論ではない。）

## 2. 実際に使えるツール

SPDX 3.0.1 モデルの正典である `spdx/spdx-3-model` リポジトリは、
`serialization/jsonld/validation.md`（`3.0.1` タグで確認）に、相補的な
2つの検証手段を明記している:

| 観点 | ツール | 検証内容 |
| --- | --- | --- |
| 構造（構文） | `check-jsonschema`（または `ajv`）、`https://spdx.org/schema/3.0.1/spdx-json-schema.json` に対して | 正しいフィールドが正しい型・カーディナリティで存在するか |
| 意味（モデル） | `pyshacl`、`https://spdx.org/rdf/3.0.1/spdx-model.ttl`（`--shacl` と `--ont-graph` の両方として指定）に対して | クラス・プロパティが SPDX 3.0.1 オントロジーの定義通りに使われているか |

両ツールとも公式URLからスキーマ/モデルを直接取得するため、`spdx-3-model` を
ローカルにチェックアウトしたり、手動で「context の展開」を行う必要は
着手時点では不要だった。インストール:

```bash
pip install -r scripts/validate-spdx-requirements.txt
```

ラッパースクリプト `scripts/validate-spdx.sh` が1つ以上の `*.spdx.json`
ファイルに対して両方の検証を実行する（使い方と、下記2つの注意点への
自動対処/記録はスクリプト冒頭のコメント参照）。

## 3. `analysis/xen-full/` に対する実際の結果

| 文書 | JSON Schema（構造） | SHACL（意味） |
| --- | --- | --- |
| `sbom-output.spdx.json` | pass（下記注意点1の対処後） | **Conforms: True**（無改変） |
| `sbom-build.spdx.json` | pass（下記注意点1の対処後。ファイルサイズ3.2MBのため約8分） | 3件の違反（下記注意点2）；`sbom-output.spdx.json` のグラフと結合すると **Conforms: True** |

両文書とも、実質的には SPDX 公式ツールによる基準を満たしている。現れた
2つの逸脱はいずれも、ツール側の既知の制約であり、生成データの欠陥ではない
（詳細は以下）。

### 注意点1: `@context` を配列にするのは有効な JSON-LD だが、JSON Schema は文字列リテラルを要求する

本プロジェクトのジェネレータは `@context` を配列で出力する: 公式context の
URL に加え、`spdxId` を短縮してファイルサイズを抑えるための短いプレフィックス
定義（`p:`、`b:`、`o:`）を持つオブジェクトを続ける（`docs/ja/01 §5` 参照）。
`sbom-output.spdx.json` からの例:

```json
"@context": [
  "https://spdx.org/rdf/3.0.1/spdx-context.jsonld",
  {
    "o": "urn:xenproject.org:.../output/",
    "p": "urn:xenproject.org:.../"
  }
]
```

これは有効な JSON-LD（context の配列指定は標準の JSON-LD 構文であり、
SPDX 3.0.1 仕様自体もコアcontextへの独自プレフィックス追加をこの形で
推奨している）であり、`pyshacl`（文書自身の `@context` を使って RDF として
パースする）は問題なく処理できる（上記の SHACL 結果が示す通り）。しかし
`spdx-json-schema.json` の公式 JSON Schema は `@context` が
*文字列リテラル* `"https://spdx.org/rdf/3.0.1/spdx-context.jsonld"` である
ことを要求しており、配列形式をそのまま拒否する:

```
$['@context']: 'https://spdx.org/rdf/3.0.1/spdx-context.jsonld' was expected
```

これは本プロジェクトの文書側の欠陥ではなく、JSON Schema 側の想定漏れ
（配列形式のcontextを想定していない）と見られる。この背後に他の構造的
問題が隠れていないかを確認するため、`validate-spdx.sh` は
`check-jsonschema` 実行前に `@context` を一時的（使い捨ての一時コピー。
実ファイルは変更しない）に文字列へ平坦化している。この1点の変更のみで、
両文書とも**他のエラーなく**きれいに JSON Schema 検証を通過する。

### 注意点2: `pyshacl` は別文書への参照を解決できない

`sbom-build.spdx.json` では、同じ形の `ClassConstraintComponent` 違反が
3件報告された:

```
Source Shape: [ sh:class ns1:Element ... sh:path ns1:from ]
Focus Node: b:1520
Value Node: o:3
Message: Value does not have class ns1:Element
```

`o:3` と `o:5` は確かに `Element` 型を持つ `spdxId` だが、それは
`sbom-build.spdx.json` 自身の中ではなく、**同伴文書** `sbom-output.spdx.json`
（`o:` はその文書の名前空間）の中で定義されている。関係する3つのプロパティ
— `Relationship.from`・`Relationship.to`・`SpdxDocument.rootElement` — は
まさに SPDX がある文書の要素を別文書の要素に結び付けるために使うプロパティ
である。`spdx-3-model` 自身の検証ガイドもこの制約を明記している:

> pyshacl will produce warnings if you are referencing SpdxIds that are
> outside of your document, as it cannot understand the use of `import` in
> `SpdxDocument`. For the time being, you will need to manually verify these
> references and ignore the warnings.
> （文書外の SpdxId を参照している場合、pyshacl は警告を出す。
> `SpdxDocument` の `import` の使用を理解できないためである。現時点では、
> これらの参照を手動で確認し、警告を無視する必要がある。）

これがまさに起きている事象であり（本当に宛先が存在しない参照ではないこと）
を確認するため、`scripts/validate-spdx.sh --with FILE1 FILE2 ...` は
与えた文書群の `@graph` を検証前に結合する機能を持つ。
`sbom-build.spdx.json` と `sbom-output.spdx.json`（結合後3,566要素）に
適用すると:

```
Validation Report
Conforms: True
```

となり違反は0件——build文書の3件の違反は、`pyshacl` が単一文書だけを
単独で検証したことによる副作用であり、関係性そのものの欠陥ではないことが
証明された。

## 4. B-1 の結論

生成した Xen SBOM（`analysis/xen-full/`）は、上記2つのツール側の既知の
制約を踏まえれば、SPDX 公式ツール（`check-jsonschema` + `pyshacl`）による
構造・意味の両面で妥当である。`spdx-tools`／`pyspdxtools` はこの用途の
バリデータとして使えないため、これ以上の追求は不要と判断する。

**今回の範囲外・未実施:**

- `sbom-source.spdx.json` は Xen の in-tree ビルドでは生成されない
  （`docs/ja/05 §6` 参照）ため、本検証の対象外。Linux側のサンプル文書
  （`analysis/sample-sbom-*.spdx.json`）も抜粋であり全文書の検証は
  今回は行っていない。
- 本検証は機械生成された JSON-LD が SPDX 3.0.1 モデルに準拠していることを
  確認するものであり、**意味内容**（例: 個々の `relationshipType` の選択が
  FuSa 目的に最適なモデリングかどうか）の妥当性までは検証していない。
  これは別途継続課題（backlog B-2/B-8 参照）。
