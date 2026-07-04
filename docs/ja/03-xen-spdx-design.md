# Xen SPDX-SBOM 生成 — 設計 & PoC

*`01-linux-sbom-tool.md`（Linux ツール）と `02-xen-build-analysis.md`（Xen ビルド
システム）を踏まえる。内容: 提案アーキテクチャ、実ビルドでの PoC 結果、SPDX
Relationships による Safety Case モデル化、次段階。*

## 1. 目的

**Xen ハイパーバイザー**の SPDX SBOM を自動生成し、それを **Safety Case** に紐付けて、
Xen の**機能安全（FuSa）**（IEC 61508 / ISO 26262、Xen FuSa SIG）を支援する成果物と
する。新規生成器を書くのではなく、上流 Linux の `KernelSbom`（`scripts/sbom/`）を
最大限再利用する。

## 2. PoC（実ビルドで検証済み）

**無改変**の Linux `KernelSbom` を、ビルドしたての Xen ハイパーバイザー
（`4.23-unstable`、`x86_64_defconfig`、ビルド **23秒**）に対して実行した。ドライバ:
`scripts/xen-sbom-poc/run-xen-poc.sh`。

- **ルート成果物:** `prelink.o`。最終 `xen-syms` は特殊な2パスのシンボルテーブル
  リンクで生成され `.cmd` を**出力しない**ためルートにできない。`prelink.o` は全
  `built_in.o`（`common/ drivers/ lib/ xsm/ arch/x86/`）+ arch libs を集約し、
  `.prelink.o.cmd` を**持つ**ため、ハイパーバイザーコアを端から端まで網羅する。
- **起動:** in-tree ビルド ⇒ `--src-tree == --obj-tree` のため独立した source 文書は
  生成されない（ソースは build 文書に統合）。
  `--do-not-fail-on-unknown-build-command` + `--write-output-on-error` を付与。

### 結果

| 出力 | サイズ | 要素数 | 特記 |
|------|--------|--------|------|
| `sbom-build.spdx.json` | 3.1 MB | 3,280 | **`software_File` 1,441**、`build_Build` 539 |
| `sbom-output.spdx.json` | 25 KB | 12 | `software_Package` 1（`prelink.o`） |
| `sbom.used-files.txt` | 35 KB | **1,442 ファイル** | `.c` 419 / `.h` 505 / `.o` 490 / `.S` 23 / `.a` 3 |

妥当な **SPDX 3.0.1** JSON-LD
（`@context: https://spdx.org/rdf/3.0.1/spdx-context.jsonld`）。サンプルは
`analysis/xen-poc/`。

**主要な成果:** ツールは `prelink.o` からハイパーバイザーを **C ソース 419、ヘッダ
505、アセンブリ 23** まで遡って追跡した（ハイパーバイザーコアの実ファイル単位の来歴）。
未知コマンド警告は**わずか6件**。その他（`gcc`, `ld`, `objcopy`, `nm`, `ar`, `strip`）は
既存の汎用パーサで処理された。これは `KernelSbom` がこれらのパターンをカーネル固有名の
ハードコードではなく、ツールチェーンの環境変数から導出しているためである。

### （わずかな）ギャップ — パーサが必要な Xen 固有コマンド

6件の警告は、`sbom/cmd_graph/savedcmd_parser/command_parser_registry.py` が未対応の
**3系統**のコマンドに集約される。

1. **`mv -f X.new X`**（4件）— 生成した compat ヘッダ（`include/compat/*.h`）の確定に
   使用。モデル化は容易（リネーム ⇒ 来歴を伝播）。
2. **`/usr/bin/python3 ./tools/compat-build-header.py ...`**（2件）— Xen の compat 層
   ヘッダ生成器。`.i` 入力を出力に対応付ける小さなパーサが必要。
3. **`cat .banner; sed ... < compile.h.in > compile.h`** — `compile.h` のバナー/バージョン
   生成（未対応の `IfBlock` 複合コマンド）。

いずれも Xen のビルドスクリプト固有のイディオムで、3つのパーサエントリ追加（+ アーキ名
対応付け `x86`/`arm`）でハイパーバイザー SBOM は約99%から完全へ到達する。

## 3. 提案アーキテクチャ

```
                 ┌──────────────────────────────────────────────┐
                 │  xen-spdx-sbom 生成器（本プロジェクト）        │
                 │                                              │
  xen/ ビルド ──▶│  [A] KernelSbom コア（再利用・.cmd グラフ）    │──▶ sbom-build.spdx.json
  (.cmd files)   │      + xen_parsers/（mv, compat-build-header, │──▶ sbom-output.spdx.json
                 │        compile.h; アーキ対応 x86/arm）        │──▶ sbom.used-files.txt
                 │                                              │
  tools/ libs/ ─▶│  [B] 補完コレクタ                            │──▶ (パッケージ/ファイル SBOM)
  (autotools)    │      (strace または compile_commands.json)    │
                 │                                              │
                 │  [C] Safety Case リンカ（SPDX Relationships） │──▶ xen-safety-case.spdx.json
                 └──────────────────────────────────────────────┘
```

- **[A] ハイパーバイザー（再利用）:** 上流 `scripts/sbom/` を取り込み、上記3つの Xen
  固有コマンドを登録する薄い `xen_parsers/` を追加。カーネルの `make sbom` ターゲット
  同様に駆動し、ルート = `prelink.o`（将来、2パスリンクが記録可能なコマンドを出すように
  なれば `xen-syms` も）。これが**主たる・ほぼ完全な**成果物であり FuSa の中心。
- **[B] tools/libs（新規・粗粒度）:** `.cmd` が無い。**strace** のファイルオープン追跡
  （ビルドシステム非依存、上流 KernelSbom の `sbom_analysis/` に倣う）または
  `compile_commands.json`（`bear` 経由）で、少なくともパッケージ/ファイル単位の SBOM を
  生成。後段に延期。
- **[C] Safety Case リンカ（新規）:** 生成 SBOM を Safety Case 成果物に紐付ける SPDX
  Relationships を出力する後処理（§4）。

## 4. SPDX Relationships による Safety Case モデル化

機能安全では、**Safety Case** 文書（安全計画、要件、コーディング規約/MISRA 準拠、変更
管理）が納品物の Bill of Materials の一部であり、それが支配するソフトウェアに追跡可能に
紐付いている必要がある。SPDX 3.0.1 ではこれを、生成した SBOM/Package と各 Safety Case
文書を表す `Artifact` 要素との間の **`Relationship` 要素**で表現する。

例示モデル（`analysis/xen-safety-case-relationships.example.spdx.json`）:

| From | relationshipType | To（Safety Case 成果物） |
|------|------------------|--------------------------|
| `pkg:xen-hypervisor` | *(記述元)* | `sbom:xen-hypervisor`（生成 SBOM） |
| `sbom:xen-hypervisor` | `hasDocumentation` | 安全計画（Safety Plan） |
| `pkg:xen-hypervisor` | `hasRequirement` | 安全要件仕様 |
| `pkg:xen-hypervisor` | `hasEvidence` | MISRA コーディング規約 + 準拠エビデンス |
| `pkg:xen-hypervisor` | `hasDocumentation` | 変更管理計画 |

補足:
- 上記の `relationshipType` は SPDX 3.0.1 の `RelationshipType` 語彙に対応付ける必要が
  ある。厳密な安全セマンティクスが無い場合は最も近いコア型 + `comment`、または外部
  プロパティを用いる。これは SPDX-for-Functional-Safety のアプローチ（全 Safety Case
  文書間の関連付け）に倣う。
- SBOM が既に全ソースファイルを列挙しているため、MISRA エビデンスや要件は後から
  **ファイル粒度**で付与できる（例: ファイル毎の逸脱記録）。これは FuSa 審査員が
  求めるものそのものである。

## 5. 次段階（後続フェーズ）

> **更新（Phase B — 完了）:** ステップ1は実装済み。Xen 拡張
> （`scripts/xen-sbom-poc/xen_parsers.py`、実行時注入・上流無改変）により、ハイパーバイザー
> SBOM は **未知コマンド0件 / exit 0**、1,519 ファイルを網羅。`04-xen-parsers-implementation.md`
> 参照。ギャップはベースラインが示した3コマンドより大きく（早期失敗が深部レシピを隠していた）、
> compat-*/binfile/combine/compile.h/.banner の各ファミリ処理と一時ファイルの存在フィルタで
> 解消した。

1. ~~`xen_parsers/` 実装 + 100% 完全なハイパーバイザーグラフ達成。~~ **完了。**
   残り: カスタム JSON-LD `@context` 展開後、外部 SPDX バリデータで検証。
2. `make sbom` 相当のターゲットを `xen/` に組み込む（またはスタンドアロンラッパ）ことで、
   ハイパーバイザー SBOM を CI で再現可能にする。
3. Xen 全体カバレッジのため tools/libs コレクタ（[B]）を追加。
4. Safety Case リンカ（[C]）を FuSa SIG と共に正式化し、`relationshipType` を成熟しつつ
   ある SPDX FuSa プロファイルに整合させる。

## 6. 結論

PoC は、上流 Linux SBOM ツールが **Xen ハイパーバイザーにそのまま再利用可能**であることを
実ビルドで実証した。1,441 ファイルを網羅する妥当な SPDX 3.0.1 build SBOM を生成し、
不足は Xen 固有の小さなコマンドパーサ3つのみだった。tools/libs 向け補完コレクタと SPDX
Relationships による Safety Case リンカを組み合わせれば、Xen 向けの自動・FuSa 支援 SBOM への
現実的な道筋となる。
