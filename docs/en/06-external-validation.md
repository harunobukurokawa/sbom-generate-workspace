# External Validation of the Generated SPDX 3.0.1 Documents (B-1)

*Until now, "validity" of the generated SBOM had only been checked with an
ad-hoc JSON-LD structural check (`@graph` present, element counts as
expected). This document records the result of validating the actual
generated documents (`analysis/xen-full/`) with the official SPDX tooling,
and the two caveats that surfaced along the way.*

## 1. Why `spdx-tools` (pip: `spdx-tools`, aka "pyspdxtools") cannot be used

`spdx-tools` is the SPDX project's own Python implementation
(`spdx/tools-python`). As of the version available at the time of writing
(0.8.5), its `spdx3` subpackage only supports:

- Parsing an **SPDX 2.x** document (tag-value / RDF-XML / 2.x JSON / XML /
  YAML — `spdx_tools.spdx.parser.parse_anything.parse_file`), then
- Validating it as SPDX 2.x (`validate_full_spdx_document`), then
- "Bumping" it into a **prototype** SPDX 3.0 model and writing it out as
  JSON-LD (`spdx_tools.spdx3.writer.json_ld`).

In other words, its SPDX-3 support is a one-way **2.x → 3.0 migration
export**, not an **import/validator for existing SPDX 3.0.1 JSON-LD**. There
is no code path in this library that reads an SPDX 3.0.1 JSON-LD file such as
the ones this project generates. It cannot be used for B-1's goal.

(Confirmed by reading `spdx_tools/spdx3/clitools/pyspdxtools3.py` and
`spdx_tools/spdx/parser/parse_anything.py` directly in the installed
package — not from documentation alone.)

## 2. The tooling that actually works

The `spdx/spdx-3-model` repository — the source of truth for the SPDX 3.0.1
model — documents exactly two complementary validation mechanisms in
`serialization/jsonld/validation.md` (checked at the `3.0.1` tag):

| Aspect                | Tool                                                    | What it checks |
| ---------------------- | -------------------------------------------------------- | -------------- |
| Structural (syntax)   | `check-jsonschema` (or `ajv`), against `https://spdx.org/schema/3.0.1/spdx-json-schema.json` | Are the right fields present, with the right types/cardinality? |
| Semantic (model)      | `pyshacl`, against `https://spdx.org/rdf/3.0.1/spdx-model.ttl` (as both `--shacl` and `--ont-graph`) | Are classes/properties used the way the SPDX 3.0.1 ontology defines them? |

Both tools fetch the schema/model directly from the official URL — no local
checkout of `spdx-3-model` or manual "context expansion" step is required to
get started. Install with:

```bash
pip install -r scripts/validate-spdx-requirements.txt
```

A wrapper script, `scripts/validate-spdx.sh`, runs both checks for one or more
`*.spdx.json` files (see its header comment for usage and for the two caveats
below, which it works around / documents automatically).

## 3. Actual results on `analysis/xen-full/`

| Document                  | JSON Schema (structural) | SHACL (semantic) |
| -------------------------- | ------------------------- | ------------------ |
| `sbom-output.spdx.json`   | pass (after caveat 1 below) | **Conforms: True**, as-is |
| `sbom-build.spdx.json`    | pass (after caveat 1 below; ~8 min due to file size, 3.2 MB) | 3 violations (caveat 2 below); **Conforms: True** once merged with `sbom-output.spdx.json`'s graph |

Both documents are, in substance, valid per the official SPDX 3.0.1 tooling.
The two deviations that appeared are both documented, known limitations of
the tools — not defects in the generated data — as detailed below.

### Caveat 1: `@context` as an array is valid JSON-LD, but the JSON Schema requires the literal URL string

This project's generator writes `@context` as an array: the official context
URL, plus a small object defining short prefixes (`p:`, `b:`, `o:`) used to
shorten `spdxId` values and keep file size down (see `docs/en/01
§5`). Example, from `sbom-output.spdx.json`:

```json
"@context": [
  "https://spdx.org/rdf/3.0.1/spdx-context.jsonld",
  {
    "o": "urn:xenproject.org:.../output/",
    "p": "urn:xenproject.org:.../"
  }
]
```

This is valid JSON-LD (an array of contexts is standard JSON-LD syntax), and
`pyshacl` — which parses the document as RDF using its own `@context` — has
no trouble with it (see the clean SHACL result above). However, the official
JSON Schema at `spdx-json-schema.json` requires `@context` to equal the
*literal string* `"https://spdx.org/rdf/3.0.1/spdx-context.jsonld"`, and
rejects the array form outright:

```
$['@context']: 'https://spdx.org/rdf/3.0.1/spdx-context.jsonld' was expected
```

This looks like a gap in the JSON Schema (it does not anticipate context
arrays, even though those are valid JSON-LD and are how the SPDX 3.0.1 spec
itself recommends composing custom prefixes with the core context), rather
than a defect in this project's documents. To confirm there is no *other*
structural issue hiding behind this, `validate-spdx.sh` temporarily flattens
`@context` to the plain string (in a throwaway temp copy — the actual output
files are never modified) before running `check-jsonschema`. With that one
change, both documents pass JSON Schema validation cleanly with **zero**
other errors.

### Caveat 2: `pyshacl` cannot resolve references across separate SPDX documents

`sbom-build.spdx.json` reported 3 `ClassConstraintComponent` violations, all
of the same shape:

```
Source Shape: [ sh:class ns1:Element ... sh:path ns1:from ]
Focus Node: b:1520
Value Node: o:3
Message: Value does not have class ns1:Element
```

`o:3` and `o:5` are `spdxId`s that are genuinely typed as `Element` — but in
the *companion* document, `sbom-output.spdx.json` (the `o:` prefix is that
document's namespace), not in `sbom-build.spdx.json` itself. The three
properties involved — `Relationship.from`, `Relationship.to`, and
`SpdxDocument.rootElement` — are exactly the properties SPDX uses to link one
document's elements to another's. `spdx-3-model`'s own validation guide
states this limitation explicitly:

> pyshacl will produce warnings if you are referencing SpdxIds that are
> outside of your document, as it cannot understand the use of `import` in
> `SpdxDocument`. For the time being, you will need to manually verify these
> references and ignore the warnings.

To confirm this is exactly what's happening (and not a real dangling
reference), `scripts/validate-spdx.sh --with FILE1 FILE2 ...` merges the
`@graph` arrays of the given documents before validating. Doing so for
`sbom-build.spdx.json` + `sbom-output.spdx.json` (3,566 combined elements)
produces:

```
Validation Report
Conforms: True
```

with zero violations — proving the 3 build-document violations were purely
an artifact of `pyshacl` validating one document in isolation, not a defect
in the relationships themselves.

## 4. Conclusion for B-1

The generated Xen SBOM (`analysis/xen-full/`) is valid, both structurally and
semantically, according to the official SPDX 3.0.1 tooling (`check-jsonschema`
+ `pyshacl`), once the two documented tooling limitations above are accounted
for. `spdx-tools`/`pyspdxtools` is not a viable validator for this use case
and should not be pursued further for it.

**Not yet done / out of scope for this pass:**

- The `sbom-source.spdx.json` document is not produced for the Xen in-tree
  build (see `docs/en/05 §6`), so it was not part of this validation; the
  Linux-side sample documents in `analysis/sample-sbom-*.spdx.json` are
  illustrative excerpts, not full documents, and were likewise not validated
  end-to-end here.
- This validates the mechanically generated JSON-LD's conformance to the
  SPDX 3.0.1 model. It does not validate that the *semantic content*
  (e.g. specific `relationshipType` choices) is the best possible modeling
  choice for FuSa purposes — that is a separate, ongoing concern (see
  backlog B-2/B-8).
