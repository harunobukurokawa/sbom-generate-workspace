# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# Unit tests for query_traceability.py (B-8), using small hand-built JSON-LD
# fixtures that reproduce the ADR-0008/ADR-0009 findings from the real
# analysis/xen-full/ SBOM (relationshipType inventory, dependsOn-only
# reachability, ancestorOf fan-out, hasDeclaredLicense noise, basename
# collisions, cross-document package resolution).
#
# Run:
#   PYTHONPATH=external/linux/scripts/sbom:scripts/xen-sbom-poc \
#       python3 -m pytest scripts/xen-sbom-poc/tests/test_query_traceability.py -q

import json
import os
import tempfile
import unittest

import query_traceability as qt


def _doc(elements):
    return {"@context": "https://spdx.org/rdf/3.0.1/spdx-context.jsonld", "@graph": elements}


def _file(spdx_id, name):
    return {"type": "software_File", "spdxId": spdx_id, "name": name}


def _build(spdx_id, comment):
    return {"type": "build_Build", "spdxId": spdx_id, "comment": comment}


def _rel(spdx_id, rel_type, from_id, to_ids):
    return {"type": "Relationship", "spdxId": spdx_id, "relationshipType": rel_type, "from": from_id, "to": to_ids}


class TraceabilityFixture(unittest.TestCase):
    """A 3-level chain (prelink.o <- built_in.o <- bitmap.o <- bitmap.c) plus
    the three ADR-0009 edge cases, split across a build doc ("b:" ids) and an
    output doc ("o:" ids) the way the real generator produces them.
    """

    def setUp(self):
        build_elements = [
            _file("b:1", "common/bitmap.c"),
            _file("b:2", "common/bitmap.o"),
            _file("b:3", "common/built_in.o"),
            _file("b:4", "include/xen/bitops.h"),
            # basename collision fixture (ADR-0009 point 3): two built_in.o
            _file("b:5", "drivers/built_in.o"),
            # dependsOn-only fixture (ADR-0009 point 1): reachable ONLY via
            # dependsOn, never via hasInput - mirrors tools/process-banner.sed.
            _file("b:6", ".banner"),
            _file("b:7", "include/xen/compile.h"),
            _build("b:10", "gcc -c common/bitmap.c -o common/bitmap.o"),
            _build("b:11", "ld -r -o common/built_in.o common/bitmap.o"),
            _build("b:12", "ld -r -o prelink.o common/built_in.o"),
            _rel("b:20", "hasInput", "b:10", ["b:1", "b:4"]),
            _rel("b:21", "hasOutput", "b:10", ["b:2"]),
            _rel("b:22", "hasInput", "b:11", ["b:2"]),
            _rel("b:23", "hasOutput", "b:11", ["b:3"]),
            _rel("b:25", "hasInput", "b:12", ["b:3"]),
            _rel("b:26", "hasOutput", "b:12", ["o:5"]),  # crosses into output doc
            _rel("b:24", "dependsOn", "b:7", ["b:6"]),  # compile.h depends on .banner
            # noise that must NOT be traversed:
            _rel("b:30", "hasDeclaredLicense", "b:1", ["b:31"]),
            {"type": "simplelicensing_LicenseExpression", "spdxId": "b:31"},
            _rel("b:40", "ancestorOf", "o:3", ["b:10", "b:11"]),
        ]
        output_elements = [
            _build("o:3", "make (top level)"),
            _file("o:5", "prelink.o"),
            {"type": "software_Package", "spdxId": "o:6", "name": "prelink.o"},
            _rel("o:7", "hasDistributionArtifact", "o:6", ["o:5"]),
        ]

        self.tmpdir = tempfile.mkdtemp()
        self.build_path = os.path.join(self.tmpdir, "sbom-build.spdx.json")
        self.output_path = os.path.join(self.tmpdir, "sbom-output.spdx.json")
        with open(self.build_path, "w") as f:
            json.dump(_doc(build_elements), f)
        with open(self.output_path, "w") as f:
            json.dump(_doc(output_elements), f)

        self.graph = qt.load_graph(self.build_path, self.output_path)


class TestDownstreamTraversal(TraceabilityFixture):
    def test_source_file_reaches_root_artifact_and_package(self):
        result = qt.query(self.graph, "common/bitmap.c", "downstream")
        file_names = {f.get("name") for f in result["files"]}
        self.assertIn("common/bitmap.o", file_names)
        self.assertIn("common/built_in.o", file_names)
        self.assertIn("prelink.o", file_names)
        self.assertIn("o:6", {p["spdxId"] for p in result["packages"]})

    def test_intermediate_builds_are_reported(self):
        result = qt.query(self.graph, "common/bitmap.c", "downstream")
        comments = {b.get("comment") for b in result["builds"]}
        self.assertTrue(any("bitmap.c -o common/bitmap.o" in c for c in comments))
        self.assertTrue(any("built_in.o common/bitmap.o" in c for c in comments))

    def test_no_downstream_dependents_is_a_real_empty_result(self):
        # prelink.o (o:5) has nothing consuming it further in this fixture.
        result = qt.query(self.graph, "prelink.o", "downstream")
        self.assertEqual(result["files"], [])
        self.assertEqual(result["builds"], [])


class TestDependsOnIsMandatory(TraceabilityFixture):
    def test_banner_only_reachable_via_dependson(self):
        # .banner has NO hasInput edge anywhere; if the traversal only looked
        # at hasInput/hasOutput it would report zero impact (a false
        # negative). dependsOn must surface compile.h as a dependent.
        result = qt.query(self.graph, ".banner", "downstream")
        file_names = {f.get("name") for f in result["files"]}
        self.assertIn("include/xen/compile.h", file_names)


class TestNoiseIsExcluded(TraceabilityFixture):
    def test_ancestorof_does_not_leak_into_traversal(self):
        # o:3 --ancestorOf--> {b:10, b:11} must never be walked: querying the
        # top-level make build must not "discover" every build in the tree
        # through this edge (it isn't indexed for traversal at all).
        self.assertNotIn("ancestorOf", qt.TRAVERSAL_RELATIONSHIP_TYPES)

    def test_hasdeclaredlicense_does_not_appear_in_results(self):
        result = qt.query(self.graph, "common/bitmap.c", "downstream")
        types = {f.get("type") for f in result["files"]}
        self.assertNotIn("simplelicensing_LicenseExpression", types)
        names = {f.get("spdxId") for f in result["files"]}
        self.assertNotIn("b:31", names)


class TestPathResolution(TraceabilityFixture):
    def test_exact_path_match_required(self):
        # "built_in.o" alone (basename) must not silently resolve to either
        # common/built_in.o or drivers/built_in.o.
        with self.assertRaises(qt.CoverageError):
            qt.resolve_path(self.graph, "built_in.o")

    def test_full_path_is_unambiguous(self):
        self.assertEqual(qt.resolve_path(self.graph, "common/built_in.o"), "b:3")
        self.assertEqual(qt.resolve_path(self.graph, "drivers/built_in.o"), "b:5")


class TestCoverageVsNoImpact(TraceabilityFixture):
    def test_unknown_path_raises_coverage_error_not_empty_result(self):
        # A path outside the loaded SBOM (e.g. the autotools xen.git/tools/
        # tree from backlog item B-3) must be reported as out-of-coverage,
        # never as an empty "no impact" result.
        with self.assertRaises(qt.CoverageError):
            qt.query(self.graph, "tools/xl/xl.c", "downstream")

    def test_cli_returns_nonzero_and_distinct_message_for_unknown_path(self):
        exit_code = qt.main(["--build", self.build_path, "--output", self.output_path, "tools/xl/xl.c"])
        self.assertEqual(exit_code, 2)


class TestUpstreamTraversal(TraceabilityFixture):
    def test_root_artifact_resolves_back_to_source(self):
        result = qt.query(self.graph, "prelink.o", "upstream")
        file_names = {f.get("name") for f in result["files"]}
        self.assertIn("common/built_in.o", file_names)
        self.assertIn("common/bitmap.o", file_names)
        self.assertIn("common/bitmap.c", file_names)
        self.assertIn("include/xen/bitops.h", file_names)


if __name__ == "__main__":
    unittest.main()
