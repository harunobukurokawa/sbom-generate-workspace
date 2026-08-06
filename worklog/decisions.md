# 決定記録（ADR風・日本語のみ）

意思決定を1件1エントリで記録します。後から経緯を追えるよう、背景・決定・理由を残します。

---

## ADR-0001: プロジェクトの目的とスコープ
- **日付**: 2026-07-04
- **状態**: 採用
- **背景**: Linux v7.0 の SPDX-SBOM ツールを分析・文書化し、その知見を Xen 自体の
  SPDX 自動生成に応用したい。目的は Xen の機能安全（FuSa）認証支援。
- **決定**:
  - 初回は「文書化 + Linux 再現」を先に行い、Xen 適応は設計・PoC までとする。
  - Xen 対象範囲は Xen 全体（hypervisor + tools + libs）。
  - Safety は SBOM 生成と Safety Case の SPDX Relationships モデル化の**両方**を扱う。
- **理由**: 作業規模が大きいため段階分けし、まず Linux ツールの正確な理解と再現性を
  確立してから Xen へ展開する方が確実。

## ADR-0002: 成果物・ログの言語方針
- **日付**: 2026-07-04
- **状態**: 採用
- **背景**: 社外の読み手は Xen コミュニティのエンジニア（国際的）。
- **決定**: 成果物ドキュメントは英語・日本語の両方。作業ログは日本語のみ。
- **理由**: コミュニティ向けは英語が必要。日本語版も用意することで社内での翻訳の
  手間を減らす。ログは内部用途のため日本語のみで足りる。

## ADR-0003: ソース取得方針
- **日付**: 2026-07-04
- **状態**: 採用
- **背景**: Linux / Xen のソースが手元に無い。
- **決定**: Linux は Linus（torvalds）mainline から、Xen は xenbits の最新から
  clone する。clone 先は `external/`（git-ignore）。
- **理由**: 上流の一次情報に基づくため。巨大なため本リポジトリには含めない。

## ADR-0004: 暫定プロジェクト名
- **日付**: 2026-07-04
- **状態**: 暫定
- **決定**: 暫定名 `xen-spdx-sbom`。正式名は未定で後から変更可。
- **理由**: 内容（Xen 向け SPDX-SBOM 自動生成）を端的に表すため。

## ADR-0005: SBOM ↔ ソースコード トレーサビリティ照会（B-8）の新設
- **日付**: 2026-07-08
- **状態**: 採用
- **背景**: 次段階の相談で「code との連携」＝「トレーサビリティ関係でコードと
  SBOM の依存関係が分かる仕組み」がほしいとの要望が出た。既存の cmd グラフは
  成果物→ソースファイルの向きの関係（`contains`/`generatedFrom`）は既に持つが、
  ソースファイルを起点に「どの成果物・パッケージが影響を受けるか」を逆引きする
  利用者向けの仕組みは用意していなかった。B-2（Safety Case リンカ）・B-3
  （tools/libs カバレッジ）のいずれにも該当しない別ニーズと判断。
- **決定**: `worklog/backlog.md` に新規項目 **B-8** として起票する。推奨順序は
  B-3（Xen 全体へのカバレッジ拡大）の直後、B-0（Safety 必要性確認）の前に配置。
- **理由**: 逆引きツールはカバレッジが Xen 全体に広がってから作る方が手戻りが
  少ない。また FuSa の変更管理プロセスでは「ソース変更が何に影響するか」を
  追える仕組みが実務上有用であり、Safety Profile の成熟（B-0/B-2）を待たずに
  着手できる。

## ADR-0006: B-1 外部バリデータの選定 — `check-jsonschema` + `pyshacl`（`spdx-tools` は不採用）
- **日付**: 2026-07-22
- **状態**: 採用
- **背景**: B-1（生成 SBOM の外部バリデータ検証）着手にあたり、当初バックログの
  想定は「`pyspdxtools` 等」だった。実際に `pip install spdx-tools`（0.8.5）で
  導入・ソースを確認したところ、`spdx3` サブパッケージは SPDX 2.x 文書の
  パース・検証と、そこから SPDX 3.0 プロトタイプへの一方向 bump/エクスポート
  のみを提供し、**既存の SPDX 3.0.1 JSON-LD を読み込んで検証する経路が存在
  しない**ことが判明した（ドキュメントではなく `parse_anything.py`・
  `pyspdxtools3.py` の実装を直接確認）。
- **決定**: `spdx-tools`/`pyspdxtools` は本用途で不採用。代わりに SPDX 3.0.1
  モデルの正典リポジトリ `spdx/spdx-3-model`（`3.0.1` タグ）が公式に文書化
  している2ツールを採用する: 構造検証に `check-jsonschema`
  （`spdx-json-schema.json` を URL 参照）、意味検証に `pyshacl`
  （`spdx-model.ttl` を URL 参照、SHACL）。両者ともスキーマ/モデルを
  ローカルに持たずURL直接参照で動作し、当初想定していた手動の JSON-LD
  展開ステップは（`@context` を一時的に文字列化する軽微な前処理を除き）
  不要だった。
- **理由**: 想定ツールが実際には目的に使えないと判明したため、SPDX 3.0.1
  モデル自身が「動作確認済み」として明記している手段に切り替えるのが最も
  確実。実データ（`analysis/xen-full/`）で検証した結果、2つの既知ツール制約
  （`@context` 配列形式への JSON Schema 非対応／`pyshacl` の文書間参照非対応）
  以外の逸脱は無く、生成データ自体の妥当性を確認できた。詳細と再現手順は
  `docs/{en,ja}/06-external-validation.md`、再現スクリプトは
  `scripts/validate-spdx.sh`。

## ADR-0007: 「KernelSbom の `sbom_analysis/`」という記述の訂正（実在しない）
- **日付**: 2026-08-01
- **状態**: 採用（訂正）
- **背景**: `worklog/journal.md`（フェーズ0の事前 Web 調査時点）、
  `docs/{en,ja}/02-xen-build-analysis.md` §3、`docs/{en,ja}/03-xen-spdx-design.md`
  §3 の3箇所で、tools/libs（autotools 系、`.cmd` 非対応）向けの strace/
  `compile_commands.json` 方式を「上流 KernelSbom 自身の `sbom_analysis/` に
  倣う」と記述していた。ユーザーからの指摘を受けて `external/linux/scripts/sbom/`
  を再確認したところ、そのようなディレクトリ・機構は実在しない
  （実在するのは `cmd_graph/`, `spdx/`, `spdx_graph/`, `tests/` のみ）。公式文書
  `Documentation/tools/sbom/sbom.rst` にも strace ベースの代替手段への言及は無い。
- **決定**: 3箇所すべての記述を訂正し、「upstream に前例が無く、本プロジェクト
  独自の提案である」旨を明記した。合わせて、tools/libs が実際に `.cmd` を
  生成しないことを再検証した（`tools/libxl` 等の autotools コンポーネントは
  `.cmd` 0件。`tools/` 配下で見つかる468件の `.cmd` はすべて
  `tools/firmware/xen-dir/xen-root/` — ファームウェア用にネストされた別の
  Kbuild ビルド — 由来で、autotools 部分とは無関係。B-3 の前提は正しい）。
- **理由**: KernelSbom は `.cmd` の無い部分を補完する機能を持たず、単に
  スコープ外として扱う設計である。Linux の `make sbom` はそもそも Kbuild
  産物のみをルートにするため、このギャップは Linux 自身では表面化しない。
  一方 Xen は tools/libs も含めてカバレッジを広げたい（本プロジェクトの
  スコープ）ため、Linux には無い追加作業（B-3）が必要になる、というのが
  正しい理解。誤った先例への言及は、読者に「upstream が既に解決策を提示して
  いる」という誤解を与えるため、要出典なき記述は残さない方針で全箇所修正した。

## ADR-0008: B-8（トレーサビリティ照会）が前提とする relationshipType の訂正
- **日付**: 2026-08-01
- **状態**: 採用（訂正）
- **背景**: ADR-0005（B-8起票）および `worklog/backlog.md` の B-8 項目は、
  生成済み SPDX JSON-LD が「成果物 → 入力ソース」の関係を `contains`/
  `generatedFrom` という `relationshipType` で持っていると記述していたが、
  これは実際の生成物を確認せずに書かれた未検証の記述だった。
- **確認方法**: `analysis/xen-full/sbom-build.spdx.json`（`--fail-on-unknown`
  ありの完全版 PoC 出力）と `analysis/xen-full/sbom-output.spdx.json` を実際に
  読み、`Relationship` 要素の `relationshipType` を集計・個々の `from`/`to`
  を実データで追跡した。
- **判明した事実**:
  1. 使われている `relationshipType` は `hasOutput`（583）・`hasInput`
     （580）・`hasDeclaredLicense`（279）・`dependsOn`（2、`.incbin` 由来）・
     `ancestorOf`（1）・`hasDistributionArtifact`（output文書側）。
     `contains`/`generatedFrom` は**1件も存在しない**。
  2. 実際のグラフ形は `software_File --(hasInput)--> build_Build
     --(hasOutput)--> software_File` の繰り返し連鎖。ファイル同士が直接
     `contains`/`generatedFrom` で結ばれているのではなく、`build_Build`
     （1コマンド1ノード）を必ず経由する。
  3. 連鎖の最上流（root artifact側）では `sbom-output.spdx.json` の
     `o:` 接頭辞IDへ越境参照する（例:
     `b:1523 hasOutput → o:5`＝`prelink.o`）。トレーサビリティ照会ツールは
     `sbom-build.spdx.json` 単独ではなく `sbom-output.spdx.json` も読み、
     ID接頭辞をまたいで解決する必要がある。
  4. 逆引き（ソース→成果物）の実現可能性を実測で確認: 共通ヘッダ
     `include/xen/bitops.h` は346個の `build_Build` の入力になっており
     （多数の `.c` から include されるため）、想定内の fan-out。
     `Relationship` 一覧（全1445件）を一度スキャンして
     ファイル名→`spdxId`、`spdxId`→関連`Relationship`の逆引きインデックスを
     作れば、任意のソースファイルからのグラフ探索は軽量に実装できる。
- **決定**: `worklog/backlog.md` の B-8 項目を、実測した `relationshipType`
  名（`hasInput`/`hasOutput`）とグラフ形（`build_Build`経由・文書間越境参照）
  に基づいて訂正した。B-3 は技術的な必須前提ではない
  （既存グラフを辿るだけのツールであるため、`xen/` のみの現状カバレッジでも
  動作する）が、スキーマの手戻りを避けるため B-3 完了後に着手する、という
  既存の順序判断自体は妥当と判断し維持した。
- **理由**: relationshipType 名を誤って設計・実装の前提にすると、
  `query_traceability.py` 実装時に存在しないエッジ種別を探して空振りする
  （＝着手後すぐに手戻りする）ため、着手前の事実確認で先に訂正する方が安価。
  ADR-0007 と同種の「未検証の言及が複数箇所に伝播する」パターンであり、
  再発防止のため一次データ（生成済みJSON-LD）を直接確認する方針を踏襲した。

## ADR-0009: B-8 実装仕様の確定（ADR-0008 への指摘5点の検証結果）
- **日付**: 2026-08-01
- **状態**: 採用
- **背景**: ADR-0008（B-8の前提となる relationshipType の訂正）に対し、並行作業中の
  もう一方のセッションから実装時の懸念5点のフィードバックを受けた。いずれも
  「実装後に踏むと手戻りになる」類のため、着手前に実データ
  （`analysis/xen-full/sbom-build.spdx.json` 全1445 Relationship / 1518 File）で
  一次確認し、B-8 の実装仕様として確定させる。

### 検証結果（5点すべて指摘は妥当。うち2点は指摘より深刻、1点は数値を訂正）

1. **`dependsOn`/`ancestorOf` の扱い — 指摘より深刻。`dependsOn` は必須。**
   実体を確認したところ両者は全く性質が異なる。
   - `dependsOn`（2件）は **`software_File` → `software_File`** の直接エッジで、
     `build_Build` を経由しない。内訳は
     (a) `common/config_data.S → common/config.gz`（`.incbin` 由来）、
     (b) `include/xen/compile.h → {compile.h.in, .banner, tools/process-banner.sed}`。
   - 決定的な事実: **`tools/process-banner.sed` は `hasInput` エッジを1本も持たない**
     （hasInput出現数0）。つまり `hasInput`/`hasOutput` のみを辿る実装では、この
     ファイルを照会すると「影響を受ける成果物なし」と返る = **確実な偽陰性**。
     `dependsOn` は件数が少ないから無視してよい、ではなく **無視すると特定の
     ファイルが完全にグラフから消える**。逆引きロジックに必ず含める。
   - `ancestorOf`（1件）は逆に **トレーサビリティ用エッジではない**。
     `from: o:3`（output文書側のルート `build_Build`）→ `to:` 583件の
     `build_Build` 全部、という単なるグルーピング／文書構造エッジ
     （`completeness: complete` 付き）。探索に含めると全 `build_Build` が
     1ホップで繋がってしまい、影響範囲が無意味に全件へ発散する。**明示的に除外**する。

2. **逆引きインデックスは `to` 側で作る — 指摘の通り。**
   `hasInput` は `from: build_Build`, `to: [software_File, ...]`（Buildが主語）。
   したがってソースファイル起点の逆引きは「`to` 配列に当該 `spdxId` を含む
   Relationship を探す」形になる。`from` だけをキーにインデックスを作ると
   `hasInput` の検索が常に空振りする。実装では
   `to`側索引（`spdxId → [Relationship]`）と `from`側索引の**両方**を作り、
   辿る方向ごとに使い分ける。
   - 上流方向（この成果物は何から作られたか）: Build の `hasInput` を `from` 索引で引く
   - 下流方向（このソースは何に影響するか）: File の `spdxId` を `to` 索引で引いて
     Build を得る → その Build の `hasOutput` を `from` 索引で引いて成果物を得る
   - `dependsOn` は File→File のため `to` 索引で引くと下流方向になる（向きが
     `hasInput` と揃うので同じ探索ループに載せられる）

3. **`hasDeclaredLicense` は必ず relationshipType でフィルタ — 指摘の通り。**
   実体は `from: software_File` → `to: simplelicensing_LicenseExpression`
   （例: `include/xen/stdint.h → GPL-2.0-only`）。279件と全体の約19%を占め、
   `from` 側索引を無フィルタで作ると各ファイルから `LicenseExpression` へ
   1ホップ生えるため、探索結果に無関係なライセンス要素が「影響を受ける成果物」
   として混入する。探索対象の relationshipType は
   **`hasInput` / `hasOutput` / `dependsOn` の3種のみ**にホワイトリスト化する
   （ブラックリストではなくホワイトリスト。将来 upstream が新種を足しても
   意図せず混入しないため）。

4. **ファイル指定は相対パス完全一致のみ — 指摘は妥当、ただし数値を訂正。**
   実測では `software_File` 1518件に対し `name` のユニーク数も1518件で
   **フルパスの重複は0件**。一方 **ベース名の衝突は207種**あり、
   `built_in.o` は**42件**（フィードバックの「5箇所」は主要な `built_in.o` の
   数であり、実際にはサブディレクトリ分を含め42件）。他に `private.h` 9件、
   `xen.h`・`grant_table.h` 各7件など。
   → 照会APIは **obj-tree 相対パスの完全一致**を正とする。ベース名での検索を
   提供する場合は「複数ヒット時は候補一覧を提示して曖昧なまま結果を返さない」
   仕様とし、暗黙に先頭1件を選ぶ実装は禁止。

5. **「該当なし」とカバレッジ外の区別 — 指摘の通りで、かつ想定より罠が深い。**
   FuSa の変更管理で使う以上、偽陰性が最も危険という指摘に同意。加えて実データで
   **パス名前空間の落とし穴**を発見した:
   - SBOM 内のパスは obj-tree（`external/xen/xen/`）相対。トップレベルディレクトリ
     の内訳は `arch` 719, `include` 337, `common` 211, `drivers` 151, `lib` 89,
     **`tools` 6**, `xsm` 3。
   - この **`tools/` 6件は `xen/tools/`**（ハイパーバイザーのビルド補助スクリプト:
     `binfile`, `combine_two_binaries.py`, `compat-build-*.py`, `compat-xlat-header.py`,
     `process-banner.sed`）であり、**B-3 が対象とする `xen.git/tools/`**
     （`xl`, `libxl`, `console` 等の autotools ユーザ空間）とは**全くの別物**。
   - つまり利用者が `tools/...` を照会したとき、`tools/binfile` はヒットするのに
     `tools/xl/xl.c` は0件になる。プレフィックスが同じに見えるため、
     「ヒットしない = 影響がない」と誤読する危険が単なるカバレッジ外より高い。
   → **決定**: 照会ツールは結果が空のとき、必ず次を区別して報告する。
     (a) SBOM に当該パスが `software_File` として存在し、かつ下流エッジが無い
         → 真に「影響を受ける成果物なし」（例: 最終成果物そのもの）
     (b) SBOM に当該パスが存在しない → **`UNKNOWN / OUT-OF-COVERAGE` として
         警告付きで返す**（終了コードも成功と分ける）。「影響なし」とは絶対に
         表示しない。
     (c) 併せて、現在の SBOM カバレッジ範囲（obj-tree のルートと、
         `xen/` ハイパーバイザーのみで `xen.git/tools/`・`libs/` は B-3 未完了に
         つき対象外である旨）を出力に明記する。

- **決定**: 上記1〜5を B-8 の実装仕様として確定し、`worklog/backlog.md` の B-8
  完了条件に反映する。特に (1) `dependsOn` 必須・`ancestorOf` 除外、
  (3) relationshipType ホワイトリスト、(5) カバレッジ外の明示的区別の3点は
  完了条件に含める。
- **理由**: いずれも実装してから気づくと探索ロジックとインデックス構造の作り直しに
  なる。特に (5) は FuSa の文脈で偽陰性を生む安全上の欠陥であり、機能ではなく
  仕様として最初から埋め込む必要がある。ADR-0007・ADR-0008 に続き、記述ではなく
  一次データ（生成済み JSON-LD）で確認する方針を継続した。

## ADR-0010: tree-sitter-bash を採用しない（arm64 実測に基づく）
- **日付**: 2026-08-06
- **状態**: 採用（不採用の決定）
- **背景**: 「Xen のビルドコマンドには `if-then-else`・`while`・パイプが含まれ、
  正規表現ベースでは解析できない。AST パーサー（tree-sitter-bash, MIT）が必要」という
  仮説のもと、Node.js 実装 + Python ラッパー + KernelSbom 統合層を実装した。
- **決定**: `xen_parsers.py` のパーサーレジストリへの**登録は行わない**。さらに、
  未使用のコードと npm 依存を本流に持ち込まないため、実験成果一式（Node.js パーサー、
  Python ラッパー、KernelSbom 統合シム、そのテスト、`package.json`、元の提案文書）は
  `experiment/tree-sitter-bash` ブランチに分離して保存する。
- **理由**: arm64 ビルドの全 303 savedcmd で定量評価した結果、tree-sitter パーサーは
  **未知コマンドを 1 件も救済せず、上流が正しく処理していたコマンドを 7 件奪った**
  （純粋な退行）。既存の `_VALIDATION_PRELUDE`（`objdump | while` 除去）と `IfBlock`
  分岐処理が対象構文を先に吸収しており、寄与の余地が無かった。実際、tree-sitter を
  外した状態で未知コマンド 0 件を達成している。
  - 仮説の前提だった「arm64 SBOM 生成の失敗」は、実際には `--obj-tree` の引数ミスに
    起因しており、シェル構文の解析能力とは無関係だった（`docs/*/07` §2）。
  - 導入根拠として示されていた「解析成功率 48% → 99.6%」は**一度も測定されておらず**、
    実装前の期待値だった。実測はこれを否定した（`docs/*/07` §4.4）。
- **再評価の条件**: `_VALIDATION_PRELUDE` の正規表現で表現できないシェル構文が将来の
  ビルドに現れた場合。その際は `docs/*/07` §4.1 の測定手順で**「救済 > 奪取」を実証し、
  かつ実装の未完成 3 点（B-10）を解消してから**採用する。
- **副次的な決定**: 前置レジストリのパターンは**狭く保つ**ことを制約として明文化した。
  Xen エントリは上流レジストリ全 61 エントリより先に評価されるため、緩いパターンは
  上流の処理を無警告で奪う。実際に追加した `ld` パーサーは `.*ld\b` が「`build` を
  含む任意コマンド」に過剰マッチし、gcc コマンドを奪っていた。回帰テスト
  `TestXenPatternsDoNotShadowUpstream` で固定。

## ADR-0011: arm 対応の実体は「コンフィグ網羅」であり「arch 対応」ではない
- **日付**: 2026-08-06
- **状態**: 採用
- **背景**: B-6（arm ビルドでの検証）を実施した。バックログでは「arch 依存差を
  洗い出す」ことを目的として記述していた。
- **決定**: arm64 の欠落として実装したのは XSM/FLASK ポリシーコード生成パーサー
  1 個（`mkflask.sh` / `mkaccess_vector.sh`）のみ。今後は arch 別ではなく
  **コンフィグ別**にパーサー網羅性を確認する（B-11 として起票）。
- **理由**: 実測された未知コマンドは XSM/FLASK の 2 種のみで、これは
  `arm64_defconfig` が XSM/FLASK を有効化し x86_64 `defconfig` が有効化しないという
  **コンフィグ差**に起因する。aarch64 のコンパイラ・リンカコマンド自体は上流パーサーが
  そのまま処理できた（`^([^\s]+-)?(gcc|clang|ld|objcopy)\b` 等がツールチェーン
  プレフィクスを吸収する）。
- **帰結**:
  - 「arm 対応 SBOM」というフレーミング自体が的を外していた。バックログ B-6 の
    「arch 依存差の洗い出し」という前提も同様。
  - Xen コミュニティへの説明も「arch 対応」ではなく「有効化される機能に応じた
    パーサー網羅」として提示する。
  - 副作用として、`--obj-tree` の誤指定が無警告で全入力を捨てる問題を発見し、
    検出用の警告を追加した（`docs/*/07` §2.1）。
