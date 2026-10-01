#!/usr/bin/env bash
# install.sh -- fetch and set up folio_orders_loader without cloning the full repo.
#
# Downloads only the files the loader needs to run (plus README), pinned to one
# commit SHA, and creates a ready-to-use venv with the package installed in it.
# Safe to re-run: with no flags it checks for a newer commit and updates in
# place (leaving the venv alone unless --recreate-venv is passed).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/marnold-ebsco/folio_orders_loader/main/install.sh | bash -s -- [options]
#   ./install.sh [options]
#
# Options:
#   --dir PATH           Install location (default: ./folio_orders_loader)
#   --ref REF            Branch or tag to install from (default: main), e.g. v0.3.5
#   --recreate-venv      Delete and rebuild the venv even if one exists
#   --check              Only report whether an update is available; change nothing
#   -h, --help           Show this help

set -euo pipefail

REPO="marnold-ebsco/folio_orders_loader"
INSTALL_DIR="./folio_orders_loader"
REF="main"
RECREATE_VENV=0
CHECK_ONLY=0

# Files needed to run the loader, relative to repo root. Deliberately excludes
# tests/, spike/, out/ and the handoff/findings notes.
FILES=(
  "pyproject.toml"
  "README.md"
  "folio_orders_loader/__init__.py"
  "folio_orders_loader/__main__.py"
  "folio_orders_loader/budgets.py"
  "folio_orders_loader/builder.py"
  "folio_orders_loader/cli.py"
  "folio_orders_loader/client.py"
  "folio_orders_loader/loader.py"
  "folio_orders_loader/lookups.py"
  "folio_orders_loader/mapping.py"
  "folio_orders_loader/records.py"
  "folio_orders_loader/tools.py"
)

VERSION_MARKER=".folio_orders_loader_install_version"

usage() {
  sed -n '/^# Usage:/,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --recreate-venv) RECREATE_VENV=1; shift ;;
    --check) CHECK_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Error: '$1' is required but not found on PATH." >&2; exit 1; }
}
need curl
need python3

# pyproject.toml requires Python >= 3.12.
python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' || {
  echo "Error: Python 3.12+ is required (found $(python3 --version 2>&1))." >&2
  exit 1
}

resolve_sha() {
  curl -fsSL "https://api.github.com/repos/${REPO}/commits/${REF}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'])"
}

echo "Resolving latest commit for ${REPO}@${REF}..."
REMOTE_SHA="$(resolve_sha)"
echo "Latest commit: ${REMOTE_SHA}"

LOCAL_SHA=""
if [[ -f "${INSTALL_DIR}/${VERSION_MARKER}" ]]; then
  LOCAL_SHA="$(cat "${INSTALL_DIR}/${VERSION_MARKER}")"
fi

if [[ -n "$LOCAL_SHA" && "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "Already up to date (${LOCAL_SHA})."
  if [[ "$CHECK_ONLY" -eq 1 ]]; then exit 0; fi
elif [[ -n "$LOCAL_SHA" ]]; then
  echo "Update available: ${LOCAL_SHA} -> ${REMOTE_SHA}"
  if [[ "$CHECK_ONLY" -eq 1 ]]; then exit 0; fi
else
  echo "No existing install found at ${INSTALL_DIR}; installing fresh."
  if [[ "$CHECK_ONLY" -eq 1 ]]; then exit 0; fi
fi

mkdir -p "${INSTALL_DIR}/folio_orders_loader"

echo "Fetching files pinned to ${REMOTE_SHA}..."
for f in "${FILES[@]}"; do
  url="https://raw.githubusercontent.com/${REPO}/${REMOTE_SHA}/${f}"
  dest="${INSTALL_DIR}/${f}"
  mkdir -p "$(dirname "$dest")"
  curl -fsSL "$url" -o "$dest"
  echo "  ${f}"
done

VENV_DIR="${INSTALL_DIR}/venv"

if [[ "$RECREATE_VENV" -eq 1 && -d "$VENV_DIR" ]]; then
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating venv at ${VENV_DIR}..."
  python3 -m venv "$VENV_DIR" || {
    echo "Error: venv creation failed (on Debian/Ubuntu: apt install python3-venv)." >&2
    exit 1
  }
else
  echo "Reusing existing venv at ${VENV_DIR}."
fi

# Editable install: the fetched files stay the source of truth, so a later
# update only has to replace them. folioclient is pulled in as a dependency.
echo "Installing folio_orders_loader and dependencies..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet --editable "${INSTALL_DIR}"

# Written last so an interrupted install is retried on the next run.
echo "${REMOTE_SHA}" > "${INSTALL_DIR}/${VERSION_MARKER}"

# $0 is "bash" when run via `curl | bash -s --`, so it's not a usable
# path to re-invoke -- fall back to re-fetching via curl in that case.
case "$0" in
  *install.sh) RERUN_CMD="$0" ;;
  *) RERUN_CMD="curl -fsSL https://raw.githubusercontent.com/${REPO}/main/install.sh | bash -s --" ;;
esac

cat <<EOF

Done. folio_orders_loader (commit ${REMOTE_SHA:0:12}) is ready at:
  ${INSTALL_DIR}

Activate and run:
  source "${VENV_DIR}/bin/activate"
  folio-orders-loader --help

Check for updates later without changing anything:
  ${RERUN_CMD} --dir "${INSTALL_DIR}" --check

Apply an update in place:
  ${RERUN_CMD} --dir "${INSTALL_DIR}"
EOF
