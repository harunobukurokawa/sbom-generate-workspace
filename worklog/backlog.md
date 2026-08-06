# バックログ（次にやるべきこと・単一の追跡リスト）

本ファイルが「次段階」の**唯一の追跡リスト**です。`docs/{en,ja}/03 §5` と
`worklog/journal.md` の総括に散っていた項目を統合・重複排除したもの。

- 状態: ⬜ 未着手 / 🔄 進行中 / ✅ 完了
- 優先度: P1（高・FuSa 直結）〜 P3（低・将来）

## 完了済み（参考）
- ✅ Phase A: Linux ツール文書化・再現、Xen ビルド解析、Xen 適応の設計 + PoC
- ✅ Phase B: ハイパーバイザー SBOM の 100% 化（未知コマンド0件・1,519 ファイル）

## 必要性調査の知見（2026-07-05）
B-2 の必要性を調べた結果、当初の「P1・FuSa 直結」は**推論であり未確立**と判明した。
- **SPDX 側**: 例示で使った関係型（`hasDocumentation`/`hasEvidence`/`hasRequirement`/
  `hasSpecification`/`hasTest`）は 3.0.1 core に実在（確認済み）。ただし機能安全専用の
  **Safety Profile（REQUIREMENT/VERIFICATION/EVIDENCE クラス）は SPDX 3.1 で、まだ
  Release Candidate**（FOSDEM 2026 段階）。→ 3.0.1 core で作ると 3.1 で作り直しリスク。
  例の誤り: pkg→sbom を `hasDeclaredLicense` で繋いだのは意味誤り（B-2 実施時に修正）。
- **Xen FuSa SIG 側**: ロードマップ wiki は bot 保護でフェッチ不可（未確認）。代替の Xen 公式
  FuSa 更新ブログには **SBOM/SPDX の言及なし**。可視な優先は文書化・防御的プログラミング・
  安全機能・safety-only プロセス。→ SBOM が SIG の critical path にある確証は得られず。
- 参考: SPDX RelationshipType 3.0.1 / SPDX Safety Profile RC（ELISA, Nicole Pappler）/
  Zephyr の Safety Profile 適用（FOSDEM 2024）。

→ **結論: B-2 は時期尚早。標準が安定し需要も明確な B-1・B-3 を先行させる。**

## 次段階

### B-0 ⬜ P1（B-2 の前提）— B-2 の必要性確認
- Xen FuSa SIG のロードマップ/議事（wiki は bot 保護のため `!curl` 等で取得 or ML 確認）を
  読み、SBOM/SPDX Safety Profile が SIG の計画にあるか確認する。
- SPDX 3.1 Safety Profile の最終化状況を追跡（RC→正式化の時期）。
- 完了条件: 「Xen FuSa が SBOM/SPDX を必要とするか」に根拠を持って Yes/No を出す。
  Yes かつ 3.1 が実用段階なら B-2 を起票、そうでなければ保留。

### B-1 ✅ P2 — 生成 SBOM の外部バリデータ検証
- 現状は JSON-LD の構造検証のみ。SPDX の公式ツールで妥当性を確認する。
- 前提: カスタム JSON-LD `@context` の**展開**が必要（`docs/…/01 §5` の制約）。
- 想定: `pyspdxtools` 等（pip / ネットワーク要）。展開スクリプトを `scripts/` に用意。
- 完了条件: 展開後の 3 文書が公式バリデータで pass。
- **2026-07-22 完了**: `spdx-tools`（pyspdxtools）は SPDX 3.0.1 JSON-LD の
  読み込み・検証経路自体を持たず（2.x→3.0 の一方向エクスポートのみ）使用不可と
  判明。代わりに `spdx/spdx-3-model`（3.0.1タグ）公式手順の
  `check-jsonschema`（構造）＋`pyshacl`（意味、SHACL）を採用。両ツールとも
  スキーマ/モデルをURLから直接参照でき、事前の手動 context 展開は不要だった。
  `analysis/xen-full/` の実データで検証した結果、`sbom-output.spdx.json` は
  無改変で SHACL に conform。`sbom-build.spdx.json` は他文書
  （`sbom-output.spdx.json`）への参照3件が `pyshacl` の既知の制約
  （文書間 import 非対応、公式ドキュメントに明記）で違反表示されたが、両文書の
  グラフを結合すると violations 0 件で conform し、データ自体に欠陥がないことを
  確認。JSON Schema 側は `@context` が配列（公式 + 独自プレフィックス）である
  ことをスキーマが文字列リテラル前提で拒否する既知の制約があり、一時的に
  文字列へ平坦化すれば両文書ともエラー0件で pass。
  再現用スクリプト `scripts/validate-spdx.sh` と依存
  `scripts/validate-spdx-requirements.txt` を追加。詳細は
  `docs/{en,ja}/06-external-validation.md`。

### B-2 ⏸ P?（B-0 待ち）— Safety Case リンカの実装
- **保留**: 必要性未確立（上記知見）。B-0 で Yes かつ SPDX 3.1 が実用段階になってから起票。
- 現状は例示のみ（`analysis/xen-safety-case-relationships.example.spdx.json`）。
- 実施時: 生成 SBOM と Safety Case 文書（安全計画・要件・MISRA・変更管理）を紐付ける生成器。
  可能なら **SPDX 3.1 Safety Profile（REQUIREMENT/VERIFICATION/EVIDENCE）** を採用し、
  3.0.1 core の関係型は暫定手段とする。例の `hasDeclaredLicense` 誤用を修正。
- 完了条件: SBOM + Safety Case を結合した SPDX 文書を自動生成でき、バリデータで pass。

### B-3 ⬜ P2 — tools/libs コレクタ（Xen 全体カバレッジ）
- `.cmd` を持たない `tools/`・`libs/`・`stubdom/` を strace もしくは
  compile_commands.json（bear）で収集し、パッケージ/ファイル単位 SBOM を生成。
- 完了条件: hypervisor 以外の主要コンポーネントの SBOM が生成できる。

### B-4 ⬜ P2 — xen/ への `make sbom` 相当ターゲット統合（CI 再現）
- 現状は外部ドライバ（`generate-xen-sbom.sh`）。Xen ビルドに組み込み CI で再現可能に。
- 完了条件: Xen ツリー内のターゲット/ラッパで SBOM がワンステップ生成。

### B-5 ⬜ P3 — Xen 拡張の上流貢献の検討
- `xen_parsers.py` の各パーサ（compat-*/binfile/combine 等）を KernelSbom へ、
  IfBlock-then 入力保持・存在フィルタは一般改善として提案。
- 完了条件: 上流への提案方針（Issue/パッチ）を整理。

### B-6 ✅ P3 — arm ビルドでの検証（2026-08-06 完了、arm64 のみ）
- arm64（`arm64_defconfig`, `aarch64-linux-gnu-gcc 11.4.0`）で検証。**未知コマンド 0 件**、
  895 パス / 1,951 elements / 1.4 MB。KernelSbom は無改造を維持。
- 洗い出した差分は **arch 依存ではなくコンフィグ依存**（XSM/FLASK 有効化）だった。
  `mkflask.sh` / `mkaccess_vector.sh` 用パーサー 1 個をランタイム注入して解消。
  aarch64 のコンパイラ・リンカコマンド自体は上流パーサーがそのまま処理できた。
- 文書: `docs/{ja,en}/07-arm64-parser-gap-analysis.md`、手順書 8 節（手順6）。
- 副産物: tree-sitter-bash を実測評価し**不採用**（ADR-0010）。救済 0 件・上流から奪取
  7 件で純粋な退行だった。実験コードは `experiment/tree-sitter-bash` ブランチに分離。
- **arm32 は未検証**（B-9 として起票）。

### B-8 ⬜ P2 — SBOM ↔ ソースコード トレーサビリティ照会の仕組み
- 生成済み SPDX JSON-LD は既に「成果物 → 入力ソース」の関係を持つ。
  **訂正（2026-08-01、ADR-0008）**: 具体的な `relationshipType` は
  `contains`/`generatedFrom` ではなく **`hasInput`/`hasOutput`**（`build_Build`
  ↔ `software_File` 間）。`analysis/xen-full/sbom-build.spdx.json` で実測:
  `hasOutput` 583件・`hasInput` 580件・`hasDeclaredLicense` 279件・`dependsOn`
  2件・`ancestorOf` 1件（`contains`/`generatedFrom` は0件、そもそも未使用）。
  グラフ形は `software_File --(hasInput)--> build_Build --(hasOutput)-->
  software_File` の繰り返しで、末端（root artifact側）は `sbom-output.spdx.json`
  側の `o:`接頭辞IDへ越境参照する。この向きを逆にたどれば
  **逆方向（ソースファイル → 影響を受けるビルド成果物・パッケージ）**の照会が
  作れる（実測: 共通ヘッダ `include/xen/bitops.h` は346個の `build_Build` の
  入力になっており、fan-outは想定内の規模）。照会できる簡易ツール
  （例: `scripts/xen-sbom-poc/query_traceability.py`）を用意する。
- ユースケース: 「この `.c` ファイルを変更したら、どの SBOM 上のパッケージ／
  成果物が影響を受けるか」を FuSa の変更管理プロセスから参照できるように
  する（B-2 の Safety Case リンクとは別に、コード変更影響のトレーサビリティ
  そのものを扱う）。
- 前提: B-1（外部バリデーション）で SBOM の関係性が正しいことを確認済みで
  あることが望ましい（✅ 完了済み）。B-3（tools/libs カバレッジ）は技術的な
  必須前提ではない（このツールは既存グラフをそのまま辿るだけで、`xen/` のみの
  現状カバレッジでも動く）が、スキーマの手戻りを避けるため B-3 完了後に着手する
  という順序上の判断は妥当。
- **実装仕様（2026-08-01 確定、ADR-0009 — 別セッションからの指摘5点を実データで
  検証した結果）**:
  1. 探索する relationshipType は **`hasInput` / `hasOutput` / `dependsOn` の3種
     のみをホワイトリスト**指定する。
     - `dependsOn`（File→File の直接エッジ、2件）は**必須**。
       `tools/process-banner.sed` は `hasInput` エッジを1本も持たず
       `dependsOn` 経由でしか到達できないため、除外すると確実な偽陰性になる。
     - `ancestorOf`（1件）は**除外**。`o:3` → 583 `build_Build` 全件という
       文書構造上のグルーピングエッジであり、含めると影響範囲が全件に発散する。
     - `hasDeclaredLicense`（279件、File→LicenseExpression）は探索対象外。
       フィルタしないと結果にライセンス要素が混入する。
  2. 逆引きインデックスは **`to` 側索引と `from` 側索引の両方**を作る。
     `hasInput` は `from: build_Build, to: [File]`（Buildが主語）のため、
     ソース起点の下流探索は `to` 側索引が必要。`from` だけで索引を作ると
     `hasInput` の検索が常に空振りする。
  3. ファイル指定は **obj-tree 相対パスの完全一致**。フルパスは一意
     （1518件中重複0）だがベース名衝突は207種あり `built_in.o` は42件存在する。
     ベース名検索を提供する場合は複数ヒット時に候補一覧を返し、暗黙に先頭を
     選ばない。
  4. 結果が空のとき、**「影響なし」と「カバレッジ外」を必ず区別**する（FuSa
     観点で最重要 / 偽陰性防止）。SBOM に `software_File` として存在しない
     パスは `UNKNOWN / OUT-OF-COVERAGE` として警告＋非ゼロ終了コードで返す。
     特に SBOM 内の `tools/` 6件は `xen/tools/`（ハイパーバイザーのビルド補助
     スクリプト）であり、B-3 対象の `xen.git/tools/`（`xl`/`libxl` 等の
     autotools ユーザ空間）とは別物のため、プレフィックスが同じに見えて
     誤読を招きやすい。出力に現在のカバレッジ範囲を明記する。
- 完了条件: 任意のソースファイルパスを入力すると、`hasInput`/`hasOutput`/
  `dependsOn` を辿って依存する/依存される SBOM 要素（`build_Build`・ファイル・
  パッケージ）の一覧が得られる。かつ上記実装仕様の 1（ホワイトリストと
  `dependsOn` 対応）・4（カバレッジ外の明示的区別）を満たすこと。

### B-7 ✅ P2 — 再現手順書（英語版）の作成
- `docs/ja/05-reproduction-runbook.md`（2026-07-08 作成、日本語版のみ）の内容を
  英語化し `docs/en/05-reproduction-runbook.md` として作成する（CLAUDE.md の
  bilingual 同期規約に合わせる）。
- 前提: 日本語版が実際の追試でレビュー・確定していること（数値・手順の誤りが
  あれば先に日本語版を修正してから翻訳する）。
- 完了条件: `docs/en/05-reproduction-runbook.md` が `docs/ja/05-reproduction-runbook.md`
  と内容同期している。
- **2026-07-22 完了**: 日本語版（既に追試済み・実績値記載済み）をそのまま英訳し
  `docs/en/05-reproduction-runbook.md` を新規作成。章構成・数値・警告文はすべて
  日本語版と対応。

### B-9 ⬜ P3 — arm32 での検証
- B-6 で arm64 は完了したが arm32 は未検証。`docs/*/07` §4.1 の測定手順を再利用する。
- arm64 の知見（欠落はコンフィグ依存）から、arm32 でも有効化される機能次第で
  未知コマンドが残る可能性がある。
- 完了条件: arm32 での未知コマンド数を一覧化し、必要なパーサーを起票。

### B-10 ⬜ P3 — tree-sitter-bash 実装の完成（採用は別判断）
- 背景: 実装が未完成（`docs/*/07` §4.5）。現状 AST 解析のみ動作。コードは
  `experiment/tree-sitter-bash` ブランチにある（以下のパスはそのブランチ上）。
- 残作業:
  1. `src/shell_parser.js` の `extractIOFiles()` を実装（現在は常に空配列）。
  2. `scripts/shell_parser_wrapper.py` の JSON 分離バグ修正（`lines[0]` のみを
     `json.loads()` している。`JSONDecoder.raw_decode` で逐次デコードすべき）。
     現状は失敗しても無警告で正規表現フォールバックに落ちる。
  3. `tests/test_tree_sitter_parser.py` の `@unittest.skip` を解除し 5 件を通す。
  4. `else_body` に `else` と `;` が混入している問題を整える。
- **注意**: 完成しても**採用は別判断**。ADR-0010 のとおり、レジストリ登録には
  `docs/*/07` §4.1 の手順で「救済 > 奪取」の実証が必要。優先度は低い。

### B-11 ⬜ P2 — 他 defconfig でのパーサー網羅性確認
- 背景: arm64 の欠落は「arm64 だから」ではなく「XSM/FLASK が有効だから」だった
  （ADR-0011）。同種のコンフィグ依存の欠落が他にも存在すると予想される。
- 対象案: `x86_64` + XSM/FLASK 有効、`CONFIG_HVM`/`CONFIG_SHADOW_PAGING` 等の
  コード生成を伴うオプション。
- 手法: `docs/*/07` §4.1 の測定手順（全 savedcmd に対する獲得パーサー比較）を再利用。
- 完了条件: 対象コンフィグごとの未知コマンド数を一覧化し、必要なパーサーを起票。
- B-5（上流貢献）の説得材料になる（「arch 差ではなくコンフィグ差」は上流にも有用）。

## 推奨順序（2026-08-06 改訂: B-6 完了）
標準が安定し必要性が明確なものを優先: **B-3 → B-8 → B-11 → B-0 →（B-0=Yes なら）B-2 → B-4 → B-5 → B-9 → B-10**。
次の着手は **B-3**（tools/libs コレクタ）— B-6 完了により変わらず。
- B-1（外部検証）と B-6（arm ビルド）は完了。B-6 から B-9/B-10/B-11 が派生した。
- B-11（他 defconfig の網羅性）は B-8 の後。arm64 の知見が「欠落はコンフィグ依存」を
  示したため、上流貢献（B-5）の説得材料としても効く。
- 旧案（B-2 先行）は撤回。B-2 は必要性未確立 + SPDX 3.1 Safety Profile が RC のため保留。
- B-1（外部検証）は Phase B の締め、B-3（tools/libs）は「Xen 全体」方針に必要で標準安定。
- B-8（トレーサビリティ照会）は B-3 でカバレッジが Xen 全体に広がってから着手する方が
  手戻りが少ないため、B-3 の直後に配置。
- B-0（必要性確認）を並行し、結果次第で B-2 を起票。
- Arm（B-6）は当初「アーキ依存差の洗い出しが目的なので x86 側の外部検証（B-1）・
  カバレッジ拡大（B-3）が固まってから」としていたが、2026-08-06 に先行実施した。
  結果、洗い出されたのは arch 依存差ではなく**コンフィグ依存差**であり、
  「アーキ依存差の切り分け」という当初の前提自体が的を外していた（ADR-0011）。
  残る arm32 は B-9。

## 2026-07-08 のレビュー: ユーザー提示項目とバックログの対応
ユーザーから次段階の候補として「Arm でのビルド」「Safety の追加」「code との連携
（トレーサビリティ）」の3点が挙がった。バックログと突き合わせた結果:
- Arm でのビルド → **B-6** に対応済み。ただし推奨順序では最後尾（P3）であり、
  今すぐ着手する場合は他の項目より優先する理由を記録すること。
- Safety の追加 → **B-2** に対応するが、**保留中（⏸）**。2026-07-05 の調査で
  「Xen FuSa SIG が SBOM/SPDX を必要とする」との根拠は未確立、かつ SPDX 3.1
  Safety Profile はまだ RC。着手前に **B-0** を完了させる必要がある。
- code との連携（トレーサビリティ）→ 既存項目になかったため **B-8** として新規起票。
