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

### B-1 ⬜ P2 — 生成 SBOM の外部バリデータ検証
- 現状は JSON-LD の構造検証のみ。SPDX の公式ツールで妥当性を確認する。
- 前提: カスタム JSON-LD `@context` の**展開**が必要（`docs/…/01 §5` の制約）。
- 想定: `pyspdxtools` 等（pip / ネットワーク要）。展開スクリプトを `scripts/` に用意。
- 完了条件: 展開後の 3 文書が公式バリデータで pass。

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

### B-6 ✅ P3 — arm ビルドでの検証（2026-08-06 完了）
- arm64 (`arm64_defconfig`, `aarch64-linux-gnu-gcc 11.4.0`) で検証。**未知コマンド 0 件**、
  894 ファイル / 1,951 elements / 1.5 MB。KernelSbom は無改造を維持。
- 洗い出した差分は arch 依存ではなく**コンフィグ依存**（XSM/FLASK 有効化）だった。
  `mkflask.sh` / `mkaccess_vector.sh` の 2 パーサーをランタイム注入して解消。
- 文書: `docs/{ja,en}/06-arm64-parser-gap-analysis.md`。
- 副産物: tree-sitter-bash は実測で純粋な退行と判明し不採用（同文書 §4）。

### B-7 ✅ P2 — 再現手順書（英語版）の作成（2026-08-06 完了）
- `docs/en/05-reproduction-runbook.md` を新規作成。これで `01`〜`06` すべてが
  ja/en 揃い、CLAUDE.md の bilingual 同期規約における非同期は解消した。
- 翻訳の前に日本語版の古い記述を修正した。11節に「arm/arm64 での検証は未実施」が
  残っていたが B-6 完了により虚偽だったため、「arm64 は検証済み・**arm32 は未検証**」に
  是正し、B-10（他 defconfig の網羅性未確認）も限界として追記。2節のフロー図にも
  手順6 を追加した。
- 1.3 の所要時間表に arm64 を実測して追加: **ビルド 8.0 秒**（12コア）、
  **SBOM 生成 0.8 秒**。「9 秒は速すぎる」と疑い `make clean` の実効性
  （`prelink.o`・`.cmd`・`built_in.o` がすべて消えること）を検証したうえで確定した値。
- 同期の機械的検証: 見出し数 20=20、節番号の並びが全 20 箇所一致、コードブロック
  26=26、主要な数値 30 種の出現回数が両版で一致、相互参照の `docs/ja`↔`docs/en` も確認。
- 英語版の記述どおりに実機実行して照合（8.3 の生成・確認コマンド、10 節の検証
  スクリプト、9 節のテスト）。すべて記載値と一致。

### B-8 ✅ P2 — arm64 検証結果の再現手順書への反映（2026-08-06 完了）
- `docs/ja/05-reproduction-runbook.md` に「手順6: arm64 版での再現」を 8 節として追加
  （後続 8〜11 節を 9〜12 に繰り下げ）。旧番号体系のまま残っていた相互参照 3 箇所と
  「上記10節」も修正した。
- 手順書どおり（相対パス・引数そのまま）にリモートで実行し期待値と照合済み。
  elements 1,951 / software_File 894 / Relationship 758 / build_Build 290 / 拡張子内訳が一致。
- 明記した要点: 第2引数はハイパーバイザ dir でリポジトリ root ではない（枠囲み）、
  ビルド後に `make clean` しない、想定内の警告2種と件数、テスト期待値を
  「23 passed, 10 skipped」に更新（failed が1件でもあれば再現失敗）。
- 照合中に `used-files` の 894/895 の揺れの原因を特定（末尾改行なしで `wc -l` が1少ない。
  差の1個はルート成果物 `prelink.o`）。`docs/{ja,en}/06` にも反映。
- 残: 英語版への同期は B-7。

### B-9 ✅ P2 — `_keep_existing()` の無警告全件削除に警告を出す（2026-08-06 完了）
- 背景: `--obj-tree` を 1 階層誤ると全入力が非存在パスへ解決され、`_keep_existing()` が
  **無警告で全件削除**する。結果 SBOM は「ファイル 1 件」になり、原因がパーサー欠陥に
  見えた（`docs/*/06` §2.1）。デバッグに相当の時間を要した。
- 実装前に発生頻度を計測: 健全な arm64 ビルドでは 292 回の呼び出し中 全件削除は
  **1 回のみ**（`.banner.tmp`）。誤った obj-tree では約 290 回。判別力十分と判断。
- 実装は 2 段構え（いずれも `xen_parsers.py` 内で完結。KernelSbom は無改造）:
  1. **事前検証** `_validate_obj_tree()`（`install_xen_extensions()` から呼ぶ）。
     `<OBJ_TREE>/.config` が無く `<OBJ_TREE>/xen/.config` が有れば
     「`pass <OBJ_TREE>/xen instead`」と具体的に提案。ビルド1回分を無駄にする前に検出。
  2. **事後警告** 非空の入力が全件削除された際に、パス一覧と obj-tree を含めて警告。
- テスト 9 件追加（全件削除で警告 / 部分削除・空入力・OBJ_TREE 未設定で無警告 /
  事前検証 4 パターン）。誤った obj-tree で事前警告が出ることも実機確認済み。

### B-10 ⬜ P2 — 他 defconfig でのパーサー網羅性確認
- 背景: arm64 の欠落は「arm64 だから」ではなく「XSM/FLASK が有効だから」だった。
  同様にコンフィグ依存の欠落が他にも存在すると予想される。
- 対象案: `x86_64` + XSM/FLASK 有効、`arm32`、`CONFIG_HVM`/`CONFIG_SHADOW_PAGING` 等の
  コード生成を伴うオプション。
- 手法: `docs/*/06` §4.1 の測定手順（全 savedcmd に対する獲得パーサー比較）を再利用。
- 完了条件: 対象コンフィグごとの未知コマンド数を一覧化し、必要なパーサーを起票。

### B-11 ⬜ P3 — tree-sitter-bash 実装の完成（採用は別判断）
- 背景: 実装が未完成のまま放置されている（`docs/*/06` §4.5）。現状 AST 解析のみ動作。
- 残作業:
  1. `src/shell_parser.js` の `extractIOFiles()` を実装（現在は常に空配列）。
     リダイレクト（`<`, `>`, `>>`）とコマンド引数からの入出力抽出。
  2. `scripts/shell_parser_wrapper.py` の JSON 分離バグ修正。Node 側は
     pretty-print された JSON を 2 ブロック出力するが、`lines[0]` のみを
     `json.loads()` している。`JSONDecoder.raw_decode` で逐次デコードすべき。
     現状は失敗しても無警告で正規表現フォールバックに落ちる（要ログ出力）。
  3. `tests/test_tree_sitter_parser.py` の `@unittest.skip` を解除し 5 件を通す。
  4. `else_body` に `else` と `;` が混入している（`['else ld -r base.o -o final.o;']`）。
     トークン境界の処理が雑なので整える。
- **注意**: 完成しても**採用は別判断**。ADR-0005 のとおり、レジストリ登録には
  `docs/*/06` §4.1 の手順で「救済 > 奪取」の実証が必要。現状 arm64 は tree-sitter
  なしで未知 0 件なので、優先度は低い（P3）。

## 推奨順序（2026-08-06 改訂）

**B-1 → B-10 → B-3 → B-0 →（B-0=Yes なら）B-2 → B-4 → B-5 → B-11**

- 2026-08-06 に **B-6 → B-9 → B-8 → B-7** を完了。B-6（arm64 検証）の過程で
  B-8/B-9/B-10/B-11 が派生し、うち B-8/B-9 を同日消化。さらに B-7 まで到達した。
- ドキュメントの bilingual 同期は現時点で完了（`01`〜`06` すべて ja/en 揃い）。
  以後 `docs/` を編集する際は対応版の更新を忘れないこと。
- **次は B-1**（外部バリデータ検証）。Phase B の締めであり、「SPDX として妥当」と
  社外に主張するための最後の欠落。現状の検証は JSON-LD の構造チェックのみで、
  公式ツールによるスキーマ検証は未実施（手順書 11節にも限界として明記済み）。
- B-10 は B-5（上流貢献）の説得材料になる（「arch 差ではなくコンフィグ差」という
  知見は上流にとっても価値がある）。
- B-11 は最後。arm64 が tree-sitter なしで未知 0 件を達成しているため、現時点で
  投資対効果が無い（ADR-0005）。
- 旧案（B-2 先行）は撤回のまま。B-2 は必要性未確立 + SPDX 3.1 Safety Profile が RC。
