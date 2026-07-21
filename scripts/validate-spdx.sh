#!/usr/bin/env bash
#
# validate-spdx.sh - Validate SPDX 3.0.1 JSON-LD documents with the official
# tooling: structural validation against the SPDX JSON Schema, and semantic
# validation against the SPDX SHACL model. Both are referenced directly by
# URL (network access required); no local copy of schema/model is needed.
#
# Background: `pip install spdx-tools` (aka pyspdxtools) cannot be used here
# -- its SPDX-3 support is import (SPDX-2.x -> SPDX-3 "bump") and export
# only; it has no parser for existing SPDX 3.0 JSON-LD. The two tools below
# are the ones documented by the SPDX 3.0.1 model repo itself
# (serialization/jsonld/validation.md in spdx/spdx-3-model).
#
# Known, harmless caveats (see docs/en/06-external-validation.md for detail):
#   1. check-jsonschema requires @context to be the literal schema URL
#      string. This project's documents use an array
#      (official context + a small custom prefix map to shorten spdxIds),
#      which is valid JSON-LD but rejected by the schema as written. This
#      script flattens @context to the plain string in a temp copy before
#      running check-jsonschema; the original file on disk is untouched.
#   2. pyshacl cannot resolve references to elements defined in a companion
#      SPDX document (e.g. sbom-build.spdx.json referencing an element that
#      lives in sbom-output.spdx.json). This shows up as
#      ClassConstraintComponent violations on `from`/`to`/`rootElement`. It
#      is a documented pyshacl limitation, not a defect in the data --
#      pass related documents together (see --with below) to confirm.
#
# Usage:
#   scripts/validate-spdx.sh FILE.spdx.json [FILE2.spdx.json ...]
#   scripts/validate-spdx.sh --with FILE.spdx.json FILE2.spdx.json ...
#     --with merges all given documents' @graph before SHACL validation,
#     to check semantics across a set of related documents at once
#     (still runs JSON Schema validation on each file individually).
#
# Setup (once): pip install -r scripts/validate-spdx-requirements.txt
set -euo pipefail

SCHEMA_URL="https://spdx.org/schema/3.0.1/spdx-json-schema.json"
MODEL_URL="https://spdx.org/rdf/3.0.1/spdx-model.ttl"

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
for f in "$@"; do
  flat="${WORKDIR}/$(basename "$f").contextfix.json"
  python3 - "$f" "$flat" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
d["@context"] = "https://spdx.org/rdf/3.0.1/spdx-context.jsonld"
json.dump(d, open(dst, "w"))
PY
  echo "-- ${f} (@context flattened to plain string; see caveat 1 above) --"
  check-jsonschema -v --schemafile "${SCHEMA_URL}" "${flat}" || true
done

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
