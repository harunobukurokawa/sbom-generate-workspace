#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only OR MIT
#
# gen_xen_sbom.py - Runtime-injection driver.
#
# Runs the UNMODIFIED upstream Linux KernelSbom (external/linux/scripts/sbom)
# against a built Xen hypervisor, after installing the Xen-specific parser and
# hardcoded-dependency extensions from xen_parsers.py. The upstream sbom package
# modules are shared via sys.modules, so the injection persists when sbom.py runs.
#
# Usage:
#   gen_xen_sbom.py <sbom_dir> <xen_hv_dir> <out_dir> [root_artifact]
#
# Unlike the baseline PoC, this does NOT pass --do-not-fail-on-unknown-build-command:
# any remaining unknown command is a hard failure, guaranteeing the "zero unknown
# commands" result and catching regressions.

import os
import runpy
import sys


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    sbom_dir = os.path.abspath(sys.argv[1])
    xen_hv = os.path.abspath(sys.argv[2])
    out_dir = os.path.abspath(sys.argv[3])
    root = sys.argv[4] if len(sys.argv) > 4 else "prelink.o"

    # Make the upstream sbom package and this directory importable.
    sys.path.insert(0, sbom_dir)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Install Xen extensions before the graph is built.
    import xen_parsers

    xen_parsers.OBJ_TREE = xen_hv  # filter parsed inputs to files that exist
    xen_parsers.install_xen_extensions()

    os.environ.setdefault("SRCARCH", "x86")
    os.makedirs(out_dir, exist_ok=True)

    # Build argv for the upstream sbom.py entry point. In-tree build => src == obj.
    # No --do-not-fail-on-unknown-build-command: unknown commands must be zero.
    sys.argv = [
        os.path.join(sbom_dir, "sbom.py"),
        "--src-tree", xen_hv,
        "--obj-tree", xen_hv,
        "--roots", root,
        "--generate-spdx",
        "--generate-used-files",
        "--prettify-json",
        "--output-directory", out_dir,
        "--spdxId-prefix", "urn:xenproject.org:",
        "--build-type", "urn:xenproject.org:Kbuild",
        "--package-license", "GPL-2.0-only",
        "--package-version", "4.23-unstable",
    ]

    # cwd must be the obj-tree for root-artifact resolution, matching run-xen-poc.sh.
    os.chdir(xen_hv)
    runpy.run_path(os.path.join(sbom_dir, "sbom.py"), run_name="__main__")


if __name__ == "__main__":
    main()
