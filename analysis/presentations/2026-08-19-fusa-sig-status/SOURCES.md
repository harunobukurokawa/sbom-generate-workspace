# Provenance for `xen-sbom-status-report.pptx` / `-en.pptx` (2026-08-19)

This file records, for every number and log/code excerpt shown in the slide
deck (Japanese: `xen-sbom-status-report.pptx`; English: `xen-sbom-status-report-en.pptx`,
same content and figures, translated), exactly which repository file and
commit it came from, and how it was verified. Kept alongside the decks so the
figures remain traceable after they are shared outside the repo (e.g. posted
to a wiki).

Verification method: each number below was re-derived directly from the
committed artifact in this session (JSON element counts via `json.load` +
`Counter`, byte sizes via `ls -la`, warning counts via `grep -c`), not copied
from an earlier doc without checking.

## Slide "実績① 結果サマリ" (x86_64 / arm64 hypervisor SBOM)

| Claim in slide | Verified value | Source file | Commit (last change to that path) |
|---|---|---|---|
| x86_64: unknown commands = 0, exit 0 | `grep -c "no matching parser was found" analysis/xen-full/xen-full.run.log` → `0` | `analysis/xen-full/xen-full.run.log` | `45832c9` |
| x86_64: sbom-build.spdx.json, 3,554 elements (1,518 software_File), ~3.2 MB | 3554 `@graph` elements, 1518 of type `software_File`; file size 3,234,295 bytes | `analysis/xen-full/sbom-build.spdx.json` | `45832c9` |
| x86_64: sbom-output.spdx.json, 12 elements, 24 KB | 12 `@graph` elements; file size 24,170 bytes | `analysis/xen-full/sbom-output.spdx.json` | `45832c9` |
| x86_64: 21 unit tests | `grep -c '^    def test_' scripts/xen-sbom-poc/tests/test_xen_parsers.py` → `21` (static count of test methods; **not re-executed in this session** — see caveat below) | `scripts/xen-sbom-poc/tests/test_xen_parsers.py` | `673d606` (suite created), `bf20f45`/`1ef7eae`/`2ffa9e4` (later additions, arm64 work) |
| arm64: unknown commands = 0, exit 0 | `grep -c "no matching parser was found" analysis/arm64/arm64.run.log` → `0` | `analysis/arm64/arm64.run.log` | `dad2cea` |
| arm64: sbom-build.spdx.json, 1,961 elements (897 software_File), ~1.5 MB | 1961 `@graph` elements, 897 of type `software_File`; file size 1,507,521 bytes | `analysis/arm64/sbom-build.spdx.json` | `dad2cea` |
| arm64: sbom-output.spdx.json, 12 elements, 24 KB | 12 `@graph` elements; file size 24,304 bytes | `analysis/arm64/sbom-output.spdx.json` | `dad2cea` |
| arm64 config gap: CONFIG_XSM_FLASK causes the one missing parser | `_parse_flask_codegen` docstring and registry comment in `xen_parsers.py` state this explicitly; see also `docs/{en,ja}/07-arm64-parser-gap-analysis.md` §3 | `scripts/xen-sbom-poc/xen_parsers.py` (lines ~134-156, ~187-189) | `bf20f45` |

**Caveat (disclosed, not silently glossed over):** this session's Python is
3.8.10 only; the project requires 3.10+ (`CLAUDE.md`), and `xen_parsers.py`
uses PEP 585 generics (`list[PathStr]`) that raise `TypeError` under 3.8. The
"21 unit tests pass" figure could therefore only be confirmed *statically*
(the file has exactly 21 `def test_` methods) in this session, not by
actually running the suite. The pass/fail claim itself carries forward from
README.md / worklog's own prior record of running it under Python 3.10+.
`scripts/xen-sbom-poc/tests/test_query_traceability.py` (11 tests, B-8) *was*
actually executed in this session (no incompatible syntax) and confirmed to
pass.

## Slide "実績① 実際のログ・検証結果 (エビデンス)"

| Excerpt shown | Source | Commit |
|---|---|---|
| Before: `[WARNING] Skipped parsing command ... because no matching parser was found` (baseline PoC, e.g. the XSM/FLASK and `mv -f` examples) | `analysis/xen-poc/xen-poc.run.log` | `cb6bac1` (file added), `45832c9` (last touched) |
| After: `grep -c 'no matching parser was found' analysis/xen-full/xen-full.run.log` → `0` | `analysis/xen-full/xen-full.run.log` | `45832c9` |
| `Conforms: True` (pyshacl) | `analysis/validate-spdx-20260806.log`, line 10 | `dad2cea` |

## Slide "SBOM 生成の処理フロー" (code excerpt)

| Excerpt shown | Source | Commit |
|---|---|---|
| `XEN_COMMAND_PARSERS` registry entry for XSM/FLASK codegen (`_parse_flask_codegen`) | `scripts/xen-sbom-poc/xen_parsers.py`, function defined ~line 134, registered ~line 187 | `bf20f45` |

## Slide "Appendix A: tree-sitter-bash" (measurement table)

| Claim | Source |
|---|---|
| 303 savedcmd measured, 0 rescued / 7 stolen for tree-sitter, 23 stolen for the `ld` parser, 48%→99.6% never measured | `docs/{en,ja}/07-arm64-parser-gap-analysis.md` §4.1-4.4; `worklog/decisions.md` ADR-0010 | — (doc-only, not re-derived from raw logs in this session) |

## How to reproduce these checks yourself

```bash
# element/type counts
python3 -c "
import json
from collections import Counter
for f in ['analysis/xen-full/sbom-build.spdx.json', 'analysis/xen-full/sbom-output.spdx.json',
          'analysis/arm64/sbom-build.spdx.json', 'analysis/arm64/sbom-output.spdx.json']:
    d = json.load(open(f))
    g = d.get('@graph', [])
    print(f, len(g), dict(Counter(e.get('type') for e in g)))
"

# unknown-command warning counts
grep -c "no matching parser was found" analysis/xen-full/xen-full.run.log
grep -c "no matching parser was found" analysis/arm64/arm64.run.log

# which commit last touched a given path
git log --oneline -- <path>
```
