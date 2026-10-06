#!/bin/bash
# build-tweaks-dist.sh [out-dir] — builds the tweaks release assets
# (default out-dir: build/dist):
#   myfox-tweaks.tar.gz  autoconfig/ and chrome/ at the archive root
#   changelog.json       CHANGELOG.md, all released versions (validated)
# The layout is a contract with MyFox — see docs/plan-releases-changelog.md.
set -eo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
out_dir="${1:-build/dist}"
mkdir -p "$out_dir"

python3 scripts/changelog_to_json.py -o "$out_dir/changelog.json"

tar --exclude='__pycache__' --exclude='*.pyc' --exclude='*.swp' --exclude='*~' \
    --exclude='.DS_Store' --owner=0 --group=0 --numeric-owner \
    -czf "$out_dir/myfox-tweaks.tar.gz" autoconfig chrome

echo "build-tweaks-dist: $out_dir/myfox-tweaks.tar.gz"
echo "build-tweaks-dist: $out_dir/changelog.json"
