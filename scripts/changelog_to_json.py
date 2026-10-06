#!/usr/bin/env python3
"""CHANGELOG.md -> changelog.json (the release asset MyFox reads).

Usage:
    changelog_to_json.py [-o FILE]   validate CHANGELOG.md, write changelog.json
                                     (stdout by default)
    changelog_to_json.py --check TAG     fail unless CHANGELOG.md has a
                                         non-empty section for TAG
    changelog_to_json.py --notes TAG     print TAG's section (release notes)
    changelog_to_json.py --next          print the next version number:
                                         <beta major>.<next patch>
    changelog_to_json.py --beta-major    print the current Firefox beta major

Every mode validates the whole file first. --changelog PATH reads another
file (for testing). The CHANGELOG.md format and the changelog.json contract
are described in docs/plan-releases-changelog.md.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"

VERSION_RE = re.compile(r"^\d+\.\d+$")
HEADER_RE = re.compile(r"^## (\S+) — (\S+)$")


class ChangelogError(Exception):
    pass


def version_key(version):
    major, patch = version.split(".")
    return (int(major), int(patch))


def parse(path):
    """Returns the released versions, newest first:
    [{"version", "date", "changes": [...]}]. ## Unreleased is skipped."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        raise ChangelogError(f"cannot read {path}: {e}")

    errors = []
    versions = []
    # The section being read: None before the first one; a throwaway dict for
    # ## Unreleased and for a broken header (their items go nowhere).
    current = None
    seen_title = False
    seen_unreleased = False
    for n, line in enumerate(lines, 1):
        where = f"{os.path.basename(path)}:{n}"
        if not line.strip():
            continue
        if line.startswith("## "):
            if line == "## Unreleased":
                if versions or seen_unreleased:
                    errors.append(f"{where}: '## Unreleased' must be the first section")
                seen_unreleased = True
                current = {"changes": []}
                continue
            m = HEADER_RE.match(line)
            if not m:
                errors.append(f"{where}: bad header {line!r}, expected '## <major>.<patch> — <YYYY-MM-DD>'")
                current = {"changes": []}
                continue
            version, date = m.groups()
            if not VERSION_RE.match(version):
                errors.append(f"{where}: bad version {version!r}, expected <major>.<patch>")
            try:
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                    raise ValueError
                datetime.date.fromisoformat(date)
            except ValueError:
                errors.append(f"{where}: bad date {date!r}, expected YYYY-MM-DD")
            current = {"version": version, "date": date, "changes": [], "line": where}
            versions.append(current)
        elif line.startswith("- "):
            if current is None:
                errors.append(f"{where}: list item before any '## ' section")
            elif line[2:].strip():
                current["changes"].append(line[2:].strip())
            else:
                errors.append(f"{where}: empty list item")
        elif line.startswith("# ") and not seen_title and current is None:
            seen_title = True
        else:
            errors.append(f"{where}: unexpected line {line!r} (sections hold only '- ' items)")

    for v in versions:
        if not v["changes"]:
            errors.append(f"{v['line']}: section {v['version']} has no items")
    valid = [v for v in versions if VERSION_RE.match(v["version"])]
    for newer, older in zip(valid, valid[1:]):
        if version_key(newer["version"]) <= version_key(older["version"]):
            errors.append(f"{older['line']}: {older['version']} must be older than "
                          f"{newer['version']} above it (newest first, no duplicates)")
    if errors:
        raise ChangelogError("\n".join(errors))
    return [{"version": v["version"], "date": v["date"], "changes": v["changes"]} for v in versions]


def find(versions, tag):
    for v in versions:
        if v["version"] == tag:
            return v
    raise ChangelogError(f"CHANGELOG.md has no section for {tag}")


def beta_major():
    try:
        with urllib.request.urlopen(VERSIONS_URL, timeout=30) as resp:
            data = json.load(resp)
        return int(data["LATEST_FIREFOX_DEVEL_VERSION"].split(".")[0])
    except Exception as e:
        raise ChangelogError(f"cannot get the Firefox beta version from {VERSIONS_URL}: {e}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--changelog", default=os.path.join(ROOT, "CHANGELOG.md"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", metavar="TAG")
    mode.add_argument("--notes", metavar="TAG")
    mode.add_argument("--next", action="store_true")
    mode.add_argument("--beta-major", action="store_true")
    p.add_argument("-o", "--output", metavar="FILE")
    args = p.parse_args()

    try:
        if args.beta_major:
            print(beta_major())
            return
        versions = parse(args.changelog)
        if args.check:
            find(versions, args.check)
        elif args.notes:
            for change in find(versions, args.notes)["changes"]:
                print(f"- {change}")
        elif args.next:
            major = beta_major()
            patches = [version_key(v["version"])[1] for v in versions
                       if version_key(v["version"])[0] == major]
            print(f"{major}.{max(patches) + 1 if patches else 0}")
        else:
            text = json.dumps({"versions": versions}, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(text)
            else:
                sys.stdout.write(text)
    except ChangelogError as e:
        print(f"changelog_to_json: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
