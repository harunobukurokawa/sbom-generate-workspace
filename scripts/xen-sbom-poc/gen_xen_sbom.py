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
#                   [--srcarch ARCH] [--package-version VERSION]
#
# --srcarch / --package-version default to "x86" / "4.23-unstable" (the values
# this driver historically hard-coded). The in-tree `make sbom` target passes
# the real ones ($(SRCARCH), $(XEN_FULLVERSION)).
#
# Unlike the baseline PoC, this does NOT pass --do-not-fail-on-unknown-build-command:
# any remaining unknown command is a hard failure, guaranteeing the "zero unknown
# commands" result and catching regressions.

import argparse
import os
import runpy
import sys


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sbom_dir")
    ap.add_argument("xen_hv")
    ap.add_argument("out_dir")
    ap.add_argument("root", nargs="?", default="prelink.o")
    ap.add_argument("--srcarch", default="x86")
    ap.add_argument("--package-version", default="4.23-unstable")
    args = ap.parse_args()
    sbom_dir = os.path.abspath(args.sbom_dir)
    xen_hv = os.path.abspath(args.xen_hv)
    out_dir = os.path.abspath(args.out_dir)
    root = args.root

    # Make the upstream sbom package and this directory importable.
    sys.path.insert(0, sbom_dir)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Install Xen extensions before the graph is built.
    import xen_parsers

    xen_parsers.OBJ_TREE = xen_hv  # filter parsed inputs to files that exist
    xen_parsers.install_xen_extensions()

    os.environ.setdefault("SRCARCH", args.srcarch)
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
        "--package-version", args.package_version,
    ]

    # cwd must be the obj-tree for root-artifact resolution, matching run-xen-poc.sh.
    os.chdir(xen_hv)
    try:
        runpy.run_path(os.path.join(sbom_dir, "sbom.py"), run_name="__main__")
    finally:
        # Written even on failure: with fail-on-unknown, an aborted run is
        # exactly the case this report exists to explain. See
        # diff_unknown_commands.py for how two of these get compared.
        xen_parsers.write_unknown_commands_report(
            os.path.join(out_dir, "unknown-commands.json"),
            xen_hv=xen_hv,
            root_artifact=root,
            arch=os.environ.get("XEN_TARGET_ARCH"),
        )


if __name__ == "__main__":
    main()
