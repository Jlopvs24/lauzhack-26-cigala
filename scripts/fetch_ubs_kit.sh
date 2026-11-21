#!/usr/bin/env bash
# Downloads the UBS AI Financial Twin kit (private, "all rights reserved") into vendor/ubs-kit.
# vendor/ is gitignored: the kit must NOT be committed to this (public) repo.
# Needs: gh/git logged in with an account UBS granted access to.
# Skips the "resources /..." folders: their names end in a space and cannot exist on Windows.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
DEST="$ROOT/vendor/ubs-kit"
BARE="$ROOT/vendor/.ubs-kit.git"
REPO="SSChallenge/ai-financial-twin-lauzhack-2026"
mkdir -p "$ROOT/vendor"
if [ -d "$BARE" ]; then git -C "$BARE" fetch -q --depth 1 origin "+refs/heads/*:refs/heads/*"; else git clone -q --bare --depth 1 "https://github.com/$REPO.git" "$BARE"; fi
rm -rf "$DEST"; mkdir -p "$DEST"
git -c core.protectNTFS=false -C "$BARE" archive HEAD README.md Data docs evaluation examples faq resources starter-kit | tar -x -C "$DEST"
echo "UBS kit ready in vendor/ubs-kit ($(find "$DEST" -type f | wc -l) files)"
