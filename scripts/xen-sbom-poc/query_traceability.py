#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# query_traceability.py - Reverse-lookup traceability queries over an already
# generated Xen SPDX SBOM (B-8, see worklog/backlog.md and ADR-0008/ADR-0009
# in worklog/decisions.md for the design rationale).
#
# Given a source file path (obj-tree relative, e.g. "common/bitmap.c"),
# reports which build_Build commands consume it and which artifacts /
# packages are ultimately produced downstream of it - "if I change this
# file, what in the SBOM is affected?" Also supports the reverse
# (upstream) direction: given an artifact, what did it come from?
#
# This tool does NOT regenerate or modify the SBOM; it only reads the
# existing sbom-build.spdx.json / sbom-output.spdx.json JSON-LD documents.
#
# Usage:
#   scripts/xen-sbom-poc/query_traceability.py \
#       --build analysis/xen-full/sbom-build.spdx.json \
#       --output analysis/xen-full/sbom-output.spdx.json \
#       common/bitmap.c
#
#   scripts/xen-sbom-poc/query_traceability.py --direction upstream ... prelink.o

import argparse
import json
import sys
from dataclasses import dataclass, field

# ADR-0009 point 1: whitelist only. hasDeclaredLicense (File->LicenseExpression)
# and ancestorOf (a document-grouping edge fanning out to every build_Build)
# must NOT be traversed, or results are polluted / diverge to everything.
TRAVERSAL_RELATIONSHIP_TYPES = frozenset({"hasInput", "hasOutput", "dependsOn"})

# hasDistributionArtifact links a software_Package to the software_File it
# distributes (observed once, for the root artifact/package pair in
# sbom-output.spdx.json). Only used for the final package-attribution step,
# never for graph traversal.
PACKAGE_RELATIONSHIP_TYPE = "hasDistributionArtifact"


class CoverageError(Exception):
    """Raised when the queried path is not a software_File in the loaded SBOM."""


@dataclass
class Graph:
    by_id: dict = field(default_factory=dict)
    # spdxId -> [Relationship dict, ...], indexed on the traversal-relevant side.
    from_index: dict = field(default_factory=dict)
    to_index: dict = field(default_factory=dict)
    # exact "obj-tree relative path" -> [spdxId, ...] (ADR-0009 point 3: full
    # paths were verified unique in a real build, but we still return a list
    # and let the caller detect ambiguity rather than assume uniqueness).
    name_index: dict = field(default_factory=dict)
    # software_File spdxId -> [software_Package spdxId, ...]
    package_of_file: dict = field(default_factory=dict)

    def elements_of_type(self, type_name):
        return [e for e in self.by_id.values() if e.get("type") == type_name]


def _load_graph_document(path):
    with open(path, "rt", encoding="utf-8") as f:
        doc = json.load(f)
    return doc.get("@graph", [])


def load_graph(build_path, output_path=None):
    """Load one or two SPDX JSON-LD documents into a single merged Graph.

    The build document uses "b:"-prefixed spdxIds and the output document
    uses "o:"-prefixed ids; hasOutput edges in the build document cross over
    into the output document for the root artifact (ADR-0008), so both must
    be loaded together to fully resolve a chain up to the package.
    """
    graph = Graph()
    elements = list(_load_graph_document(build_path))
    if output_path:
        elements += list(_load_graph_document(output_path))

    for element in elements:
        spdx_id = element.get("spdxId")
        if spdx_id:
            graph.by_id[spdx_id] = element

    for element in elements:
        if element.get("type") != "Relationship":
            continue
        rel_type = element.get("relationshipType")
        from_id = element.get("from")
        to_ids = element.get("to") or []

        if rel_type == PACKAGE_RELATIONSHIP_TYPE:
            for file_id in to_ids:
                graph.package_of_file.setdefault(file_id, []).append(from_id)
            continue

        if rel_type not in TRAVERSAL_RELATIONSHIP_TYPES:
            continue

        graph.from_index.setdefault(from_id, []).append(element)
        for to_id in to_ids:
            graph.to_index.setdefault(to_id, []).append(element)

    for element in elements:
        if element.get("type") == "software_File" and element.get("name"):
            graph.name_index.setdefault(element["name"], []).append(element["spdxId"])

    return graph


def resolve_path(graph, path):
    """Resolve an obj-tree-relative path to a software_File spdxId.

    Raises CoverageError if the path is not present as a software_File in the
    loaded documents (ADR-0009 point 4: this must be reported distinctly from
    "found, but nothing downstream/upstream" - ambiguous coverage vs. no
    impact is a real safety-relevant distinction for FuSa change management).
    """
    matches = graph.name_index.get(path)
    if not matches:
        raise CoverageError(path)
    if len(matches) > 1:
        raise CoverageError(f"{path} (ambiguous: {len(matches)} matches, use exact indexing)")
    return matches[0]


def _describe(graph, spdx_id):
    element = graph.by_id.get(spdx_id)
    if element is None:
        return {"spdxId": spdx_id, "type": "unknown"}
    desc = {"spdxId": spdx_id, "type": element.get("type")}
    if element.get("name"):
        desc["name"] = element["name"]
    if element.get("comment"):
        desc["comment"] = element["comment"]
    return desc


def _downstream_hops(graph, file_id):
    """One BFS step downstream from a software_File: what consumes it, and
    what is produced as a result. Returns (builds, dependents, produced_files).
    """
    builds = []
    dependents = []
    produced_files = set()

    for rel in graph.to_index.get(file_id, []):
        rel_type = rel.get("relationshipType")
        if rel_type == "hasInput":
            build_id = rel["from"]
            builds.append(build_id)
            for out_rel in graph.from_index.get(build_id, []):
                if out_rel.get("relationshipType") == "hasOutput":
                    produced_files.update(out_rel.get("to") or [])
        elif rel_type == "dependsOn":
            # from dependsOn to==file_id: `from` is the dependent artifact.
            dependents.append(rel["from"])
            produced_files.add(rel["from"])

    return builds, dependents, produced_files


def _upstream_hops(graph, file_id):
    """One BFS step upstream from a software_File: what produced it, and what
    that in turn consumed. Returns (builds, dependencies, consumed_files).
    """
    builds = []
    dependencies = []
    consumed_files = set()

    for rel in graph.from_index.get(file_id, []):
        if rel.get("relationshipType") == "dependsOn":
            dependencies.extend(rel.get("to") or [])
            consumed_files.update(rel.get("to") or [])

    for rel in graph.to_index.get(file_id, []):
        if rel.get("relationshipType") != "hasOutput":
            continue
        build_id = rel["from"]
        builds.append(build_id)
        for in_rel in graph.from_index.get(build_id, []):
            if in_rel.get("relationshipType") == "hasInput":
                consumed_files.update(in_rel.get("to") or [])

    return builds, dependencies, consumed_files


def traverse(graph, start_id, direction):
    """BFS over the whitelisted relationship types from start_id.

    direction="downstream": "what is affected if start_id changes?"
    direction="upstream":   "what did start_id come from?"
    """
    step = _downstream_hops if direction == "downstream" else _upstream_hops

    visited_files = {start_id}
    visited_builds = set()
    queue = [start_id]

    while queue:
        current = queue.pop(0)
        builds, _related_files, next_files = step(graph, current)
        for build_id in builds:
            visited_builds.add(build_id)
        for next_id in next_files:
            if next_id not in visited_files:
                visited_files.add(next_id)
                queue.append(next_id)

    visited_files.discard(start_id)
    packages = set()
    for file_id in visited_files | {start_id}:
        for package_id in graph.package_of_file.get(file_id, []):
            packages.add(package_id)

    return visited_builds, visited_files, packages


def query(graph, path, direction="downstream"):
    start_id = resolve_path(graph, path)
    builds, files, packages = traverse(graph, start_id, direction)
    return {
        "query": path,
        "direction": direction,
        "start": _describe(graph, start_id),
        "builds": [_describe(graph, b) for b in sorted(builds)],
        "files": [_describe(graph, f) for f in sorted(files)],
        "packages": [_describe(graph, p) for p in sorted(packages)],
    }


def coverage_summary(graph):
    top_level_dirs = sorted(
        {name.split("/", 1)[0] for name in graph.name_index if "/" in name}
        - {""}
    )
    return (
        "SBOM covers obj-tree-relative paths under: " + ", ".join(top_level_dirs) + ". "
        "Note: a 'tools/' prefix in this SBOM is xen/tools/ (hypervisor build "
        "helpers), NOT the autotools xen.git/tools/ tree (xl, libxl, ...) "
        "targeted by backlog item B-3, which is not yet covered."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="obj-tree-relative source/artifact path to query")
    parser.add_argument("--build", required=True, help="path to sbom-build.spdx.json")
    parser.add_argument("--output", help="path to sbom-output.spdx.json (for root-artifact/package resolution)")
    parser.add_argument(
        "--direction",
        choices=("downstream", "upstream"),
        default="downstream",
        help="downstream = what is affected if this file changes (default); "
        "upstream = what this artifact was built from",
    )
    args = parser.parse_args(argv)

    graph = load_graph(args.build, args.output)

    try:
        result = query(graph, args.path, args.direction)
    except CoverageError as exc:
        print(f"UNKNOWN / OUT-OF-COVERAGE: {exc}", file=sys.stderr)
        print(coverage_summary(graph), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    if not result["builds"] and not result["files"] and not result["packages"]:
        print(
            f"# note: '{args.path}' is a known SBOM file with no {args.direction} "
            "dependents recorded (this is a real 'no impact', not a coverage gap).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
