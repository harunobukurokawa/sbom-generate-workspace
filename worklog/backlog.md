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

### B-6 ⬜ P3 — arm ビルドでの検証
- 現状 x86 のみ。arm64/arm ハイパーバイザーで同手順を検証し、arch 依存差を洗い出す。
- 完了条件: arm ビルドでも未知コマンド 0 に近い結果を確認、差分を文書化。

### B-8 ⬜ P2 — SBOM ↔ ソースコード トレーサビリティ照会の仕組み
- 生成済み SPDX JSON-LD は既に「成果物 → 入力ソース」の関係を持つ
  （`prelink.o` から辿れる `contains`/`generatedFrom` 系）。これを
  **逆方向（ソースファイル → 影響を受けるビルド成果物・パッケージ）**に
  照会できる簡易ツール（例: `scripts/xen-sbom-poc/query_traceability.py`）
  を用意する。
- ユースケース: 「この `.c` ファイルを変更したら、どの SBOM 上のパッケージ／
  成果物が影響を受けるか」を FuSa の変更管理プロセスから参照できるように
  する（B-2 の Safety Case リンクとは別に、コード変更影響のトレーサビリティ
  そのものを扱う）。
- 前提: B-1（外部バリデーション）で SBOM の関係性が正しいことを確認済みで
  あることが望ましい。
- 完了条件: 任意のソースファイルパスを入力すると、依存する/依存される
  SBOM 要素（ファイル・パッケージ）の一覧が得られる。

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

## 推奨順序（2026-07-22 改訂: B-1 完了）
標準が安定し必要性が明確なものを優先: **B-1（完了） → B-3 → B-8 → B-0 →（B-0=Yes なら）B-2 → B-4 → B-6 → B-5**。
次の着手は **B-3**（tools/libs コレクタ）。
- 旧案（B-2 先行）は撤回。B-2 は必要性未確立 + SPDX 3.1 Safety Profile が RC のため保留。
- B-1（外部検証）は Phase B の締め、B-3（tools/libs）は「Xen 全体」方針に必要で標準安定。
- B-8（トレーサビリティ照会）は B-3 でカバレッジが Xen 全体に広がってから着手する方が
  手戻りが少ないため、B-3 の直後に配置。
- B-0（必要性確認）を並行し、結果次第で B-2 を起票。
- Arm（B-6）は「アーキ依存差の洗い出し」が目的のため、x86 側の外部検証（B-1）・
  カバレッジ拡大（B-3）が固まってから着手する方が、差分の原因切り分けがしやすい。
  優先度を繰り上げる場合は理由（納期等）をここに追記する。

## 2026-07-08 のレビュー: ユーザー提示項目とバックログの対応
ユーザーから次段階の候補として「Arm でのビルド」「Safety の追加」「code との連携
（トレーサビリティ）」の3点が挙がった。バックログと突き合わせた結果:
- Arm でのビルド → **B-6** に対応済み。ただし推奨順序では最後尾（P3）であり、
  今すぐ着手する場合は他の項目より優先する理由を記録すること。
- Safety の追加 → **B-2** に対応するが、**保留中（⏸）**。2026-07-05 の調査で
  「Xen FuSa SIG が SBOM/SPDX を必要とする」との根拠は未確立、かつ SPDX 3.1
  Safety Profile はまだ RC。着手前に **B-0** を完了させる必要がある。
- code との連携（トレーサビリティ）→ 既存項目になかったため **B-8** として新規起票。
