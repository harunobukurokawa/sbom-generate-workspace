#!/usr/bin/env bash
#
# validate-spdx.sh - Validate SPDX 3.0.1 JSON-LD documents with three
# independent, official validators: structural (SPDX JSON Schema), semantic
# (SPDX SHACL model), and the SPDX Java Tools' own Verify command -- the
# engine behind https://tools.spdx.org's Validate page, giving a result
# comparable to what the wider SPDX community sees from that site. Schema
# and SHACL model are referenced directly by URL (network access required);
# Verify runs against a jar fetched once by fetch-spdx-tools-java.sh.
#
# Background: `pip install spdx-tools` (aka pyspdxtools) cannot be used here
# -- its SPDX-3 support is import (SPDX-2.x -> SPDX-3 "bump") and export
# only; it has no parser for existing SPDX 3.0 JSON-LD. check-jsonschema and
# pyshacl are the ones documented by the SPDX 3.0.1 model repo itself
# (serialization/jsonld/validation.md in spdx/spdx-3-model). Verify is a
# separate, Java-based reference implementation with no such limitation.
#
# Known, harmless caveats (see docs/en/06-external-validation.md for detail):
#   1. check-jsonschema requires @context to be the literal schema URL
#      string. This project's documents use an array
#      (official context + a small custom prefix map to shorten spdxIds),
#      which is valid JSON-LD but rejected by the schema as written. This
#      script flattens @context to the plain string in a temp copy before
#      running check-jsonschema and Verify; the original file on disk is
#      untouched.
#   2. pyshacl cannot resolve references to elements defined in a companion
#      SPDX document (e.g. sbom-build.spdx.json referencing an element that
#      lives in sbom-output.spdx.json). This shows up as
#      ClassConstraintComponent violations on `from`/`to`/`rootElement`. It
#      is a documented pyshacl limitation, not a defect in the data --
#      pass related documents together (see --with below) to confirm. Note
#      Verify does NOT flag this: it takes one file at a time (no merge
#      option) and does not appear to check cross-document referential
#      integrity, so a Verify "valid" is not itself evidence the reference
#      resolves -- pyshacl --with remains the check for that.
#   3. Verify can raise a false "duplicate ID" (Object URI already exists)
#      for two genuinely distinct files whose paths differ only by case
#      (e.g. xt_hl.ko vs xt_HL.ko on a case-sensitive filesystem). Root
#      cause: the underlying Spdx-Java-Library treats all element IDs as
#      case-insensitive, a behaviour meant only for SPDX 2.x license
#      reference IDs (spdx/tools-java#283, open as of v2.0.7). Checked: no
#      case-only-differing paths exist in this project's Xen tree, so this
#      has not been observed here, but treat a duplicate-ID error from
#      Verify as a hint to check for a case collision before assuming a
#      real defect in the data.
#
# Usage:
#   scripts/validate-spdx.sh FILE.spdx.json [FILE2.spdx.json ...]
#   scripts/validate-spdx.sh --with FILE.spdx.json FILE2.spdx.json ...
#     --with merges all given documents' @graph before SHACL validation,
#     to check semantics across a set of related documents at once
#     (still runs JSON Schema validation and Verify on each file individually).
#
# Setup (once):
#   pip install -r scripts/validate-spdx-requirements.txt
#   scripts/fetch-spdx-tools-java.sh   # needs Java 17+ to *run* (not fetch)
set -euo pipefail

SCHEMA_URL="https://spdx.org/schema/3.0.1/spdx-json-schema.json"
MODEL_URL="https://spdx.org/rdf/3.0.1/spdx-model.ttl"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPDX_TOOLS_JAVA_JAR="${SPDX_TOOLS_JAVA_JAR:-${REPO_ROOT}/external/spdx-tools-java/tools-java-2.0.7-jar-with-dependencies.jar}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

MERGE=0
if [ "${1:-}" = "--with" ]; then
  MERGE=1
  shift
fi

if [ "$#" -eq 0 ]; then
  echo "usage: $0 [--with] FILE.spdx.json [FILE2.spdx.json ...]" >&2
  exit 2
fi

echo "== Structural validation (JSON Schema, per-file) =="
ORIG_FILES=()
FLAT_FILES=()
for f in "$@"; do
  flat="${WORKDIR}/$(basename "$f").contextfix.json"
  python3 - "$f" "$flat" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
d["@context"] = "https://spdx.org/rdf/3.0.1/spdx-context.jsonld"
json.dump(d, open(dst, "w"))
PY
  ORIG_FILES+=("${f}")
  FLAT_FILES+=("${flat}")
  echo "-- ${f} (@context flattened to plain string; see caveat 1 above) --"
  check-jsonschema -v --schemafile "${SCHEMA_URL}" "${flat}" || true
done

echo
echo "== Reference validation (SPDX Java Tools Verify, per-file) =="
if [ -f "${SPDX_TOOLS_JAVA_JAR}" ]; then
  for i in "${!FLAT_FILES[@]}"; do
    echo "-- ${ORIG_FILES[$i]} (@context flattened; see caveats 1-3 above) --"
    java -jar "${SPDX_TOOLS_JAVA_JAR}" Verify "${FLAT_FILES[$i]}" JSONLD || true
  done
else
  echo ">> skipped: ${SPDX_TOOLS_JAVA_JAR} not found -- run scripts/fetch-spdx-tools-java.sh"
fi

echo
echo "== Semantic validation (SHACL) =="
if [ "${MERGE}" -eq 1 ]; then
  merged="${WORKDIR}/merged.spdx.json"
  python3 - "${merged}" "$@" <<'PY'
import json, sys
dst = sys.argv[1]
files = sys.argv[2:]
docs = [json.load(open(f)) for f in files]
merged = dict(docs[0])
merged["@graph"] = [e for d in docs for e in d["@graph"]]
json.dump(merged, open(dst, "w"))
PY
  echo "-- merged graph of: $* --"
  pyshacl --shacl "${MODEL_URL}" --ont-graph "${MODEL_URL}" -f human "${merged}"
else
  for f in "$@"; do
    echo "-- ${f} --"
    pyshacl --shacl "${MODEL_URL}" --ont-graph "${MODEL_URL}" -f human "${f}" || true
  done
fi
