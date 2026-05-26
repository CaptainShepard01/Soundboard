#!/usr/bin/env bash
#
# release.sh — Commit, tag, and push a Soundboard release.
#
# Uses pyproject.toml as the single source of truth for the version. Verifies
# that pyproject.toml and soundboard/__init__.py agree, refuses to reuse an
# existing tag, then commits all changes, creates the matching v<version> tag,
# and pushes both the branch and the tag (which triggers the release workflow).
#
# Usage (run from the repo root):
#   ./release.sh -m "commit message"              # release at current version
#   ./release.sh -v patch -m "commit message"     # bump patch (lowest) part
#   ./release.sh -v 1.2.0 -m "commit message"     # bump to an explicit version
#
# Options:
#   -m, --message   Commit message (required).
#   -v, --version   New version: an explicit MAJOR.MINOR.PATCH, or one of the
#                   keywords 'major'/'minor'/'patch' to increment that part of
#                   the current version. Updates pyproject.toml,
#                   soundboard/__init__.py, and uv.lock first.
#   -h, --help      Show this help.
#
# Environment:
#   GITHUB_SSH_KEY  Path to the SSH key used for the push.
#                   Defaults to ~/.ssh/ed25519_github.

set -euo pipefail

MESSAGE=""
VERSION=""

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--message) MESSAGE="${2:-}"; shift 2 ;;
        -v|--version) VERSION="${2:-}"; shift 2 ;;
        -h|--help)    usage 0 ;;
        *) echo "Unknown argument: $1" >&2; usage 1 ;;
    esac
done

[[ -n "$MESSAGE" ]] || { echo "error: -m/--message is required" >&2; usage 1; }

# Run from the repo root regardless of where the script is invoked.
cd "$(git rev-parse --show-toplevel)"

PYPROJECT="pyproject.toml"
INIT_PY="soundboard/__init__.py"

read_version() {  # $1=file  $2=sed-extract-pattern
    sed -n -E "s/$2/\1/p" "$1" | head -n1
}

# ── Optional version bump ────────────────────────────────────────────────────
if [[ -n "$VERSION" ]]; then
    # Accept an explicit MAJOR.MINOR.PATCH, or a keyword that increments the
    # matching component of the current version (patch resets nothing, minor
    # resets patch, major resets minor and patch).
    if [[ "$VERSION" =~ ^(major|minor|patch)$ ]]; then
        CUR=$(read_version "$PYPROJECT" '^version = "(.*)"')
        if ! [[ "$CUR" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
            echo "error: cannot bump '$VERSION': current version '$CUR' is not MAJOR.MINOR.PATCH" >&2
            exit 1
        fi
        MA=${BASH_REMATCH[1]}; MI=${BASH_REMATCH[2]}; PA=${BASH_REMATCH[3]}
        case "$VERSION" in
            major) MA=$((MA + 1)); MI=0; PA=0 ;;
            minor) MI=$((MI + 1)); PA=0 ;;
            patch) PA=$((PA + 1)) ;;
        esac
        VERSION="$MA.$MI.$PA"
    elif ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "error: version '$VERSION' must be MAJOR.MINOR.PATCH (e.g. 1.2.0) or one of: major minor patch" >&2
        exit 1
    fi
    echo "Bumping version to $VERSION"
    sed -i -E "s/^version = \".*\"/version = \"$VERSION\"/" "$PYPROJECT"
    sed -i -E "s/^__version__ = \".*\"/__version__ = \"$VERSION\"/" "$INIT_PY"
    if command -v uv >/dev/null 2>&1; then
        uv lock >/dev/null
    else
        echo "warning: uv not found — uv.lock not updated. Update it manually if needed." >&2
    fi
fi

# ── Verify the version is consistent ─────────────────────────────────────────
PY_VER=$(read_version "$PYPROJECT" '^version = "(.*)"')
INIT_VER=$(read_version "$INIT_PY" '^__version__ = "(.*)"')

[[ -n "$PY_VER" ]] || { echo "error: could not read version from $PYPROJECT" >&2; exit 1; }

if [[ "$PY_VER" != "$INIT_VER" ]]; then
    echo "error: version mismatch: $PYPROJECT=$PY_VER but $INIT_PY=$INIT_VER" >&2
    exit 1
fi

TAG="v$PY_VER"

# ── Guard against reusing a tag ──────────────────────────────────────────────
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "error: tag $TAG already exists. Bump the version (-v x.y.z) before releasing." >&2
    exit 1
fi

# ── Show what will happen, then do it ────────────────────────────────────────
echo
echo "Releasing $TAG"
echo "  commit message: $MESSAGE"
git status --short

git add -A
git commit -m "$MESSAGE"
git tag -a "$TAG" -m "$MESSAGE"

# BatchMode=yes makes SSH fail fast with a real error instead of hanging on an
# interactive prompt (host-key confirmation or key passphrase). accept-new
# auto-trusts a new host's key on first connect rather than prompting.
SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=accept-new"
# Force the GitHub key explicitly so the push works regardless of which terminal
# launched this script — some shells don't resolve ~/.ssh/config the same way.
# Override the path with GITHUB_SSH_KEY; skipped if the file isn't present.
GITHUB_SSH_KEY="${GITHUB_SSH_KEY:-$HOME/.ssh/ed25519_github}"
if [[ -f "$GITHUB_SSH_KEY" ]]; then
    SSH_OPTS="$SSH_OPTS -i $GITHUB_SSH_KEY -o IdentitiesOnly=yes"
fi
export GIT_SSH_COMMAND="ssh $SSH_OPTS"
git push origin HEAD
git push origin "$TAG"

echo
echo "Pushed commit and tag $TAG. The release workflow will build Soundboard.exe."
