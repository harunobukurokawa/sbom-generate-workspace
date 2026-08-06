# 再現手順書（人間による追試・社外報告準備用）

*`01`〜`04` が「ツール・設計の説明」であるのに対し、本書は**手を動かして再現する人向けの
通し手順書**。目的は (1) 記録済みの手順に誤りがないかの確認、(2) 記録済みと同じ／類似の
結果が得られるかの検証、(3) 内容を理解した上で Xen コミュニティ等の社外エンジニアへ
説明できるようになること。数値・警告文はすべて `analysis/` 配下の実行ログ・統計ファイル
から転記した実績値であり、本書を実行した結果と突き合わせて使う。*

## 0. 対象読者と使い方

- 想定読者: 本プロジェクトの手順を自分の手で追試する社内メンバー。将来的に Xen
  コミュニティへ説明する担当者。
- 各ステップは「コマンド」→「期待される結果（実績値）」の順で示す。実行結果が
  実績値と大きくズレる場合（要素数が大幅に異なる、未知の警告が出る等）は再現に
  失敗している可能性が高いので、該当ステップの前提（ソースの版、ビルド設定）を
  見直すこと。
- 本書はハイパーバイザー本体（`xen/`）のみを対象とする。`tools/`・`libs/` 等は
  未対応（`worklog/backlog.md` の B-3）。

## 1. 前提条件

### 1.1 検証済み環境（実績）

`analysis/xen-poc/xen-poc.run.log` に埋め込まれたビルド情報（Xen の `compile.h`
生成コマンド）から採取した、この手順を実際に通した際の環境:

- OS: Ubuntu 22.04（`gcc (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`）
- Python: 3.10.12（KernelSbom は **Python 3.10 以上が必須**。`run-linux-sbom.sh` が
  実行時にバージョンをアサートする）
- Linux: v7.2-rc1 相当（`torvalds/linux` を fetch した時点の master）
- Xen: 4.23-unstable（`xenbits/xen` HEAD、changeset `f0161d2` 時点）

厳密に同一バージョンでなくても手順は再現できるはずだが、大きく古い/新しい版では
`.cmd` フォーマットやビルドコマンドが変わっている可能性がある点に留意する。

### 1.2 必要なツール

- `git`（ソース取得）
- Linux カーネルのビルドに必要な標準ツール一式: `gcc`, `make`, `bc`, `flex`,
  `bison`, `libssl-dev`, `libelf-dev` など（通常の kernel defconfig ビルドが
  通る環境であれば十分）
- Xen ハイパーバイザーのビルドに必要なツール一式（`gcc`, `make`, バイナリユーティリティ）
- `python3`（3.10+）、`pytest`（単体テスト実行時のみ）

### 1.3 ディスク容量・所要時間の目安（実績）

| 作業                                | 所要時間（実績）  | 備考                              |
| ----------------------------------- | ----------------- | --------------------------------- |
| Linux ソース取得（shallow clone）   | 数分（回線依存）  | `FULL=1` を付けない限り shallow |
| Xen ソース取得（shallow clone）     | 数分（回線依存）  | 同上                              |
| Linux カーネルビルド +`make sbom` | **4分17秒** | x86_64 defconfig, out-of-tree     |
| Xen ハイパーバイザービルド          | **23秒**    | x86_64_defconfig                  |
| Xen PoC（無改変ツール）             | 数秒〜数十秒      | ビルド済み前提                    |
| Xen 完全版 SBOM 生成                | 数秒〜数十秒      | ビルド済み前提                    |

## 2. 全体の流れ

```
scripts/fetch-sources.sh
        │
        ▼
scripts/run-linux-sbom.sh  ──────────► Linux 側 SBOM 3文書（再現ゴール1）
        │
        ▼
make -C external/xen/xen ... defconfig
make -C external/xen/xen ... -jN        ──► Xen ハイパーバイザー実ビルド
        │
        ▼
scripts/xen-sbom-poc/run-xen-poc.sh      ──► Xen PoC（無改変ツール、警告あり）
        │
        ▼
scripts/xen-sbom-poc/generate-xen-sbom.sh ──► Xen 完全版 SBOM（未知コマンド0件）
        │
        ▼
（検証）JSON-LD の構造確認 + 単体テスト実行
```

## 3. 手順1: ソース取得

```bash
scripts/fetch-sources.sh          # Linux + Xen を shallow clone
```

- 個別に取得したい場合: `scripts/fetch-sources.sh linux` / `scripts/fetch-sources.sh xen`
- タグを打つ等で完全な履歴が必要な場合のみ `FULL=1 scripts/fetch-sources.sh`
  （shallow clone よりかなり時間がかかる）

**期待される結果:**

- `external/linux/.git`、`external/xen/.git` が作成される
- 標準出力にそれぞれの `HEAD` コミットハッシュとログ1行が表示される
- 既にクローン済みの場合は `already present ... (skipping clone)` と表示され
  スキップされる（再実行しても安全）

## 4. 手順2: Linux KernelSbom の再現

```bash
scripts/run-linux-sbom.sh                 # ARCH=host, DEFCONFIG=defconfig
```

内部では `make defconfig O=kernel_build` → `make sbom O=kernel_build -j$(nproc)`
を実行し、末尾で Python ワンライナーによる簡易検証（各文書の `@graph` 要素数と
`@context`）を表示する。

**期待される結果（実績値、x86_64 defconfig, v7.2-rc1 相当, 4分17秒）:**

| 出力ファイル              | サイズ           | 要素数           | 内訳（主なもの）                                                                |
| ------------------------- | ---------------- | ---------------- | ------------------------------------------------------------------------------- |
| `sbom-source.spdx.json` | 4,513,615 bytes  | **13,796** | software_File 7,138 / Relationship 6,611 / simplelicensing_LicenseExpression 43 |
| `sbom-build.spdx.json`  | 27,440,983 bytes | **15,282** | Relationship 7,378 / software_File 3,977 / build_Build 3,923                    |
| `sbom-output.spdx.json` | 34,960 bytes     | **60**     | Relationship 27 / software_File 14 / software_Package 13（bzImage + modules）   |

いずれも `@context` が `https://spdx.org/rdf/3.0.1/spdx-context.jsonld` を指す
SPDX 3.0.1 JSON-LD であることをスクリプトの出力で確認する。

出力先: `external/linux/kernel_build/sbom-{source,build,output}.spdx.json`
（`external/` は git-ignore のため、リポジトリに含まれるのは
`analysis/sample-sbom-*.spdx.json`、`analysis/linux-reproduction-stats.md` の
サンプル・統計のみ）。

## 5. 手順3: Xen ハイパーバイザーのビルド

```bash
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 defconfig
make -C external/xen/xen XEN_TARGET_ARCH=x86_64 -j"$(nproc)"
```

**期待される結果:**

- `external/xen/xen/xen-syms`（実績: 約26MB）、`external/xen/xen/xen`（約3.1MB）が生成される
- `external/xen/xen/prelink.o` と、その `.cmd` ファイル `.prelink.o.cmd` が存在する
  （これが次段の SBOM 生成のルート成果物になる）
- ビルド全体で `.cmd` ファイルが多数生成される（実績: 624個）。これらが KernelSbom の
  依存グラフの入力になる

**確認コマンド例:**

```bash
ls -la external/xen/xen/prelink.o external/xen/xen/.prelink.o.cmd
```

## 6. 手順4: Xen PoC（無改変 KernelSbom によるベースライン検証）

```bash
scripts/xen-sbom-poc/run-xen-poc.sh          # ROOT_ARTIFACT=prelink.o（省略可）
```

上流 `sbom.py` を**一切変更せずに**、`--do-not-fail-on-unknown-build-command`
`--write-output-on-error` を付けて Xen ハイパーバイザーに適用する。出力先は
`analysis/xen-poc/`。

**期待される結果（実績値）:**

| 出力                      | サイズ | 要素数                   | 特記                                                        |
| ------------------------- | ------ | ------------------------ | ----------------------------------------------------------- |
| `sbom-build.spdx.json`  | 3.1 MB | 3,280                    | software_File 1,441 / build_Build 539                       |
| `sbom-output.spdx.json` | 25 KB  | 12                       | software_Package 1（`prelink.o`）                         |
| `sbom.used-files.txt`   | 35 KB  | **1,442 ファイル** | `.c` 419 / `.h` 505 / `.o` 490 / `.S` 23 / `.a` 3 |

- exit code: **0**（`--do-not-fail-on-unknown-build-command` により、未知コマンドが
  あってもツール自体は正常終了する設計）
- in-tree ビルド（`--src-tree == --obj-tree`）のため、独立した source 文書は生成
  されない旨の `[INFO]` ログが出る（仕様どおり、異常ではない）

**期待される警告（既知・無害、6系統・約300件超）:**

以下は実行ログ末尾の `Summarize warnings:` にまとまって出力される。これらが
出ていれば想定どおりであり、社外説明でも「既知の未対応コマンド」として言及できる。

1. `Skipped parsing command /usr/bin/python3 ./tools/compat-build-header.py ... because no matching parser was found`（約280件以上）
2. `Skipped parsing command mv -f include/compat/xen.h.new include/compat/xen.h because no matching parser was found`
3. `Skipped parsing command mv -f include/compat/xlat.h.new include/compat/xlat.h because no matching parser was found`
4. `Skipped parsing command cat .banner; sed -e ... < include/xen/compile.h.in > ...; mv -f ... include/xen/compile.h because input files in IfBlock 'then' statement are not supported`
5. `Could not infer primary purpose for .../include/hypercall-defs.i`（型推定不可、パース失敗ではない）

**もし異なる結果になったら:** 未知コマンドの種類が上記と大きく異なる（新しい
コマンド種別が出る等）場合は、Xen のバージョンが記録時（4.23-unstable,
`f0161d2`）と離れており、ビルドコマンドが変化している可能性がある。

## 7. 手順5: Xen 完全版 SBOM 生成（実行時注入した Xen 拡張を使用）

```bash
scripts/xen-sbom-poc/generate-xen-sbom.sh    # ROOT_ARTIFACT=prelink.o（省略可）
```

`scripts/xen-sbom-poc/gen_xen_sbom.py` が上流 `sbom.py` を `runpy` 経由で起動する
前に `xen_parsers.install_xen_extensions()` を呼び、Xen 専用パーサ・改良版
`parse_inputs_from_commands`・存在フィルタを注入する。**上流 `external/linux/scripts/sbom/`
自体は無改変のまま**。手順4と異なり fail-on-unknown（未知コマンドが1件でもあれば
エラー）で実行される。出力先は `analysis/xen-full/`。

**期待される結果（実績値）:**

- **exit code 0、未知コマンド発生数 0**（スクリプトが末尾で
  `>> unknown-command occurrences: 0  (target: 0)` および
  `>> RESULT: complete SBOM, zero unknown commands.` を表示する）
- 網羅ファイル数: **1,519**（手順4のベースライン1,442から+77）
  - 内訳: h:506, o:490, c:440, S:24, i:22, lst:20, py:4, a:3, (noext):2, bin:2,
    gz:1, banner:1, in:1, sed:1
  - 新規に捕捉されたのは主に: compat `.i`（22）、xlat `.lst`（20）、Xen codegen
    `.py`（4）、boot `.bin`（2）、`include/xen/compile.h.in`、`.banner`、
    `tools/process-banner.sed`
- 残存する警告（**無害・想定内**）: `Could not infer primary purpose for ...`
  形式が約52件（`compat-build-header.py` 本体や `.i` ファイルなど、型を自動推定
  できないだけでパース自体は成功している）

**もし exit code が非0、または unknown-command occurrences が0でない場合:**
再現に失敗している。手順3（ビルド）が正しく完了しているか、`prelink.o` が
最新か（ビルドをやり直した場合は `.cmd` も更新されているか）を確認する。

## 8. 手順6: arm64 版での再現（クロスビルド）

手順1〜5 は x86_64 が対象。ここでは arm64 で同じことを行う。詳細な分析は
`docs/ja/06-arm64-parser-gap-analysis.md` にある。

### 8.1 追加で必要なツール

```bash
sudo apt-get install -y gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu
```

実績: `aarch64-linux-gnu-gcc 11.4.0`、`aarch64-linux-gnu-ld` (binutils 2.38)。
Node.js は**不要**（tree-sitter 実験用のみ。SBOM 生成には使わない）。

### 8.2 ビルド

```bash
make -C external/xen/xen XEN_TARGET_ARCH=arm64 arm64_defconfig
CROSS_COMPILE=aarch64-linux-gnu- make -C external/xen/xen XEN_TARGET_ARCH=arm64 -j"$(nproc)"
```

**期待される結果:**

- `external/xen/xen/prelink.o`（実績: 約16MB）と `.prelink.o.cmd` が存在する
- `.cmd` ファイル数は実績 **303個**（x86_64 の 624個より少ない。有効な機能が異なるため）

> **重要: ビルド後に `make clean` を実行しないこと。** 本ツールは*ビルド後*に
> ディスク上の中間ファイル（`common/built_in.o` 等）をハッシュ化するため、
> クリーンすると SBOM 生成に失敗する。

### 8.3 SBOM 生成

```bash
python3 scripts/xen-sbom-poc/gen_xen_sbom.py \
    external/linux/scripts/sbom  external/xen/xen  analysis/arm64  prelink.o
```

> **最重要の注意点: 第2引数はハイパーバイザーディレクトリ（`external/xen/xen`）で
> あり、Xen リポジトリの root（`external/xen`）ではない。** `.cmd` 内のパスは
> ハイパーバイザーのビルドディレクトリ相対で記録されているため、1階層でもずれると
> 全入力が存在しないパスへ解決され、**追跡ファイル1件だけの SBOM** ができあがる。
> これは実際に発生し、原因の特定に相当の時間を要した
> （`docs/ja/06-arm64-parser-gap-analysis.md` の2節）。
>
> 現在はこの誤りを検出する警告が入っている。以下が出たら第2引数を見直すこと:
>
> ```
> [WARNING] obj-tree <...> has no .config, but <...>/xen/.config does.
>           ... pass <...>/xen instead.
> ```

**期待される結果（実績値）:**

- `analysis/arm64/sbom-build.spdx.json`: **1,951 elements**（約1.4MB）
  - `software_File` 894 / `Relationship` 758 / `build_Build` 290 /
    `simplelicensing_LicenseExpression` 5 / その他4
- `analysis/arm64/sbom.used-files.txt`: `wc -l` が **894** を出力する
  （末尾に改行が無いため。実際に列挙されているパスは **895個**）
  - 拡張子別: `.h` 359 / `.c` 222 / `.o` 281 / `.S` 19 / `.a` 2
  - 895個のうち `software_File` 要素になるのは894個。差の1個は `prelink.o` で、
    これはルート成果物のため `sbom-output.spdx.json` 側に置かれる
  - `../../../usr/bin/dash` という項目が入る（`/bin/sh` の実体）。コード生成を
    実行したシェル自身が依存として追跡されたもので、異常ではない
- 未知コマンド **0件**
- 想定内の警告:
  - `All 1 parsed input(s) were dropped ... .banner.tmp` — **1件のみ**なら正常
    （一時ファイルのため）。多数出る場合は第2引数の階層ずれを疑う
  - `Could not infer primary purpose for ...` — 実績10件（型を推定できないだけ）

`gen_xen_sbom.py` は fail-on-unknown で動作するため、**出力ファイルが生成された
こと自体が「未知コマンド0件」の証明**になる。

**確認コマンド例:**

```bash
wc -l analysis/arm64/sbom.used-files.txt
grep -E "flask/policy" analysis/arm64/sbom.used-files.txt
```

後者は XSM/FLASK のポリシーファイル5件（`mkflask.sh`, `security_classes`,
`initial_sids`, `mkaccess_vector.sh`, `access_vectors`）を表示する。これらは
arm64 で追加したパーサーが機能している証拠であり、x86_64 の SBOM には現れない
（`arm64_defconfig` が XSM/FLASK を有効化するため）。

### 8.4 x86_64 との差分の要点

arm64 で追加が必要だったのは **XSM/FLASK ポリシーコード生成のパーサー1個のみ**。
これは arch の差ではなく**コンフィグの差**であり、`aarch64-linux-gnu-*` の
コンパイラ・リンカコマンド自体は上流パーサーがそのまま処理できる。詳細と
測定手順は `docs/ja/06-arm64-parser-gap-analysis.md`。

## 9. 検証: 単体テストの実行

Xen 拡張パーサ自体の単体テストも実行し、実装が壊れていないことを確認する。

```bash
PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
    python3 -m pytest scripts/xen-sbom-poc/tests/ -q
```

**期待される結果:** **23 passed, 10 skipped**（2026-08-06 時点の実績）。

- skip の10件は `test_tree_sitter_parser.py`。tree-sitter-bash 統合は**未完成**で
  採用もしていないため、意図的に skip している（理由は skip メッセージに記載。
  `docs/ja/06-arm64-parser-gap-analysis.md` の4.5節、バックログ B-11）。
- **failed が1件でもあれば再現失敗**。skip は想定内だが failed は想定外。

## 10. 検証: 生成された SPDX 文書の中身を自分の目で確認する

`run-linux-sbom.sh` が Linux 側で自動実行している検証と同じ考え方を、Xen 側の
出力にも手動で適用できる。

```bash
python3 - <<'PY'
import json
for path in [
    "analysis/xen-full/sbom-build.spdx.json",
    # 実行結果の生成先に合わせてパスを調整すること
]:
    d = json.load(open(path))
    g = d.get("@graph", [])
    ctx = d.get("@context", [""])
    ver = ctx[0] if isinstance(ctx, list) else ctx
    print(f"{path}: {len(g):,} elements, context={ver}")
    # 要素種別ごとの件数
    from collections import Counter
    c = Counter(e.get("type") for e in g)
    for t, n in c.most_common():
        print(f"  {t}: {n}")
PY
```

**「同じ／類似の結果」と判断する目安:**

- `@context` が `https://spdx.org/rdf/3.0.1/spdx-context.jsonld` を指していること
- 要素種別ごとの件数が本書に記載した実績値と概ね一致すること（ソースの
  コミットが完全一致しないため多少の増減は許容範囲。大きく桁が違う、
  ある種別が0件になっている等は異常の兆候）
- ログに本書「期待される警告」以外の `[WARNING]`（特に `no matching parser` や
  `IfBlock` 関連）が新規に出ていないこと

## 11. 既知の限界（社外報告時に明記すべき事項）

再現手順自体は成功しても、以下は**未実施・未確立**であることを認識し、報告時に
過大に主張しないよう注意する（`worklog/backlog.md` 参照、状態は本書作成時点）。

- **外部 SPDX バリデータでの検証は未実施**（backlog B-1）。現状の「妥当性確認」は
  JSON-LD の構造チェック（`@graph` の存在・要素数のカウント）のみであり、SPDX の
  公式ツール（例: `pyspdxtools`）による正式なスキーマ検証は行っていない。
  カスタム JSON-LD `@context` の展開が前提条件として必要。
- **`tools/`・`libs/`・`stubdom/` は未対応**（backlog B-3）。本手順書がカバーするのは
  ハイパーバイザー本体（`xen/`）のみ。
- **Safety Case とのリンク（backlog B-2）は保留中**。SPDX 3.1 の Safety Profile が
  まだ Release Candidate 段階であり、Xen FuSa SIG 側でも SBOM/SPDX 活用の必要性が
  文書上は未確認のため。`analysis/xen-safety-case-relationships.example.spdx.json`
  はあくまで例示であり、生成 SBOM と自動的に紐付いてはいない。
- **arm/arm64 での検証は未実施**（backlog B-6）。本書の手順・数値はすべて x86_64。
- CI 組み込み（backlog B-4）や上流貢献（backlog B-5）も未着手。

## 12. 社外説明のための要点（参考）

Xen コミュニティ等への説明時に接続すべき骨子（詳細は `worklog/journal.md` 末尾の
「総括」を参照）:

- **問い:** Linux v7 に入った SPDX-SBOM ツール（`scripts/sbom/`）を Xen 自身の SPDX
  自動生成に再利用できるか。
- **答え（本書の再現で確認できること）:** ハイパーバイザー本体については、上流
  ツールを無改変のまま直接適用できる（手順4の PoC）。約200行の実行時注入拡張
  （`xen_parsers.py`）を加えると、未知コマンド0件・exit 0 の完全な SBOM が得られる
  （手順5）。
- **根拠:** Xen の `xen/` は Linux Kbuild 由来で `fixdep.c` が同一形式の `.cmd` を
  出力するため、KernelSbom の依存グラフ解析がそのまま通る。
- **残作業:** 外部バリデータ検証、`tools/`・`libs/` の補完、Safety Case リンクの
  正式化（上記11節）。
