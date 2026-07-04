#!/usr/bin/env bash
#
# fetch-sources.sh - Clone the upstream Linux and Xen source trees used by this
# project into external/ (which is git-ignored).
#
# - Linux: Linus Torvalds' mainline
# - Xen:   xenbits mainline (latest)
#
# Usage:
#   scripts/fetch-sources.sh            # shallow clone both
#   scripts/fetch-sources.sh linux      # only Linux
#   scripts/fetch-sources.sh xen        # only Xen
#
# Environment:
#   FULL=1   perform a full clone instead of --depth=1 (needed to check out tags)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT="${REPO_ROOT}/external"
mkdir -p "${EXT}"

LINUX_URL="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git"
XEN_URL="https://xenbits.xen.org/git-http/xen.git"

depth_args=(--depth=1)
[ "${FULL:-0}" = "1" ] && depth_args=()

clone_one() {
  local name="$1" url="$2" dest="${EXT}/$3"
  if [ -d "${dest}/.git" ]; then
    echo ">> ${name}: already present at ${dest} (skipping clone)"
    return 0
  fi
  echo ">> ${name}: cloning ${url} -> ${dest}"
  git clone "${depth_args[@]}" "${url}" "${dest}"
  echo ">> ${name}: HEAD = $(git -C "${dest}" rev-parse HEAD)"
  git -C "${dest}" log -1 --pretty='   %h %s (%ci)' || true
}

target="${1:-all}"
case "${target}" in
  linux) clone_one Linux "${LINUX_URL}" linux ;;
  xen)   clone_one Xen   "${XEN_URL}"   xen ;;
  all)
    clone_one Linux "${LINUX_URL}" linux
    clone_one Xen   "${XEN_URL}"   xen
    ;;
  *) echo "unknown target: ${target}" >&2; exit 2 ;;
esac

echo ">> done."
