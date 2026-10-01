#!/usr/bin/env bash
# Install folio-orders-loader on a host (e.g. EC2) without cloning the repo.
#
# Downloads one tagged release tarball from GitHub, pip-installs it into a
# dedicated venv, and links the CLI onto the PATH. Nothing but the venv is kept.
#
# Usage:
#   GITHUB_TOKEN=ghp_xxx ./install.sh [-v v0.3.2] [-d /opt/folio-orders-loader] [-b /usr/local/bin]
#   curl -fsSL -H "Authorization: Bearer $GITHUB_TOKEN" \
#     https://raw.githubusercontent.com/marnold-ebsco/folio_orders_loader/v0.3.2/install.sh | \
#     GITHUB_TOKEN=$GITHUB_TOKEN bash -s -- -v v0.3.2
#
# The repo is private, so a read-only token (fine-grained, Contents: read on this
# repo only) is required in GITHUB_TOKEN. Use -v latest to resolve the newest release tag.
set -euo pipefail

REPO="marnold-ebsco/folio_orders_loader"
VERSION="latest"
PREFIX="${HOME}/folio-orders-loader"
BINDIR=""
PYTHON="${PYTHON:-python3}"

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while getopts "v:d:b:h" opt; do
  case "$opt" in
    v) VERSION="$OPTARG" ;;
    d) PREFIX="$OPTARG" ;;
    b) BINDIR="$OPTARG" ;;
    h) usage 0 ;;
    *) usage 1 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

[ -n "${GITHUB_TOKEN:-}" ] || die "GITHUB_TOKEN is not set (read-only token for ${REPO})"
command -v curl >/dev/null || die "curl is required"
command -v "$PYTHON" >/dev/null || die "$PYTHON not found (need Python 3.12+)"
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
  || die "Python 3.12+ required (found $("$PYTHON" --version 2>&1))"

api() {
  curl -fsSL -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" "$@"
}

if [ "$VERSION" = "latest" ]; then
  VERSION="$(api "https://api.github.com/repos/${REPO}/tags?per_page=100" \
    | "$PYTHON" -c 'import json,sys
tags=[t["name"] for t in json.load(sys.stdin) if t["name"].startswith("v")]
key=lambda s: tuple(int(p) for p in s[1:].split("."))
print(max(tags,key=key))')" || die "could not resolve latest tag"
fi
echo "Installing ${REPO} ${VERSION} into ${PREFIX}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
TARBALL="${TMP}/folio_orders_loader-${VERSION}.tar.gz"

api -o "$TARBALL" "https://api.github.com/repos/${REPO}/tarball/${VERSION}" \
  || die "download failed (bad tag or token lacks access)"

"$PYTHON" -m venv "$PREFIX/venv" \
  || die "venv creation failed (on Debian/Ubuntu: apt install python3-venv)"
"$PREFIX/venv/bin/pip" install --quiet --upgrade pip
"$PREFIX/venv/bin/pip" install --quiet "$TARBALL"

CLI="$PREFIX/venv/bin/folio-orders-loader"
[ -x "$CLI" ] || die "install finished but $CLI is missing"

if [ -z "$BINDIR" ]; then
  if [ -w /usr/local/bin ]; then BINDIR=/usr/local/bin; else BINDIR="${HOME}/.local/bin"; fi
fi
mkdir -p "$BINDIR"
ln -sf "$CLI" "$BINDIR/folio-orders-loader"

echo "Installed: $("$CLI" --help >/dev/null 2>&1 && echo ok)"
echo "CLI linked at ${BINDIR}/folio-orders-loader"
case ":$PATH:" in *":$BINDIR:"*) ;; *) echo "note: add ${BINDIR} to PATH" ;; esac
echo "Uninstall: rm -rf ${PREFIX} ${BINDIR}/folio-orders-loader"
