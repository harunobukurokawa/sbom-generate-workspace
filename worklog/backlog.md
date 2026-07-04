# バックログ（次にやるべきこと・単一の追跡リスト）

本ファイルが「次段階」の**唯一の追跡リスト**です。`docs/{en,ja}/03 §5` と
`worklog/journal.md` の総括に散っていた項目を統合・重複排除したもの。

- 状態: ⬜ 未着手 / 🔄 進行中 / ✅ 完了
- 優先度: P1（高・FuSa 直結）〜 P3（低・将来）

## 完了済み（参考）
- ✅ Phase A: Linux ツール文書化・再現、Xen ビルド解析、Xen 適応の設計 + PoC
- ✅ Phase B: ハイパーバイザー SBOM の 100% 化（未知コマンド0件・1,519 ファイル）

## 次段階

### B-1 ⬜ P2 — 生成 SBOM の外部バリデータ検証
- 現状は JSON-LD の構造検証のみ。SPDX の公式ツールで妥当性を確認する。
- 前提: カスタム JSON-LD `@context` の**展開**が必要（`docs/…/01 §5` の制約）。
- 想定: `pyspdxtools` 等（pip / ネットワーク要）。展開スクリプトを `scripts/` に用意。
- 完了条件: 展開後の 3 文書が公式バリデータで pass。

### B-2 ⬜ P1 — Safety Case リンカの実装
- 現状は例示のみ（`analysis/xen-safety-case-relationships.example.spdx.json`）。
- 生成 SBOM（build/output）と Safety Case 文書（安全計画・要件・MISRA・変更管理）を
  SPDX Relationships で紐付ける**生成器**を実装する（FuSa 直結。ユーザー決定「両方」）。
- `relationshipType` を SPDX 3.0.1 語彙へ対応付け。FuSa SIG と整合。
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

## 推奨順序
FuSa 目的を優先し **B-2 → B-1 → B-3 → B-4 → B-6 → B-5**。
（B-2 が機能安全に直結。B-1 は Phase B の締め。以降は全体化・整備・上流化。）
