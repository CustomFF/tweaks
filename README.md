# MyFox tweaks

Firefox UI tweaks — floating "card" tabs, rounded corners, a reworked sidebar,
dark/light themes — as plain files, no installer required. [MyFox](https://github.com/CustomFF/myfox)
applies these automatically, but every file here also works by hand, including
on a Firefox you already have installed.

## Apply by hand

Two destinations: the Firefox **install** (the directory with the `firefox`
binary) and the **profile** (`about:support` → "Profile Folder").

1. Copy into the install directory:
   - `autoconfig/autoconfig.js` → `<install>/defaults/pref/autoconfig.js`
   - `autoconfig/myfox.cfg` → `<install>/myfox.cfg`
   - `autoconfig/myfox/` → `<install>/myfox/`
2. Copy into the profile directory:
   - `chrome/` → `<profile>/chrome/`
3. Create an empty file `<profile>/.myfox`. **Required** — `myfox.cfg` checks
   for this marker first and does nothing at all without it (so tweaks never
   leak into a profile you didn't mean to touch).
4. Restart Firefox.

To also install a theme, copy its signed `.xpi` (from this repo's
[Releases](https://github.com/CustomFF/tweaks/releases) — `build/signed/`
if building locally, see "Developing" below) into `<profile>/extensions/<id>.xpi`:
`myfox-dark-theme@daydve.github.io.xpi` or `myfox-light-theme@daydve.github.io.xpi`.

To remove everything: delete `<profile>/.myfox` and `<profile>/chrome/`,
restart.

## Layout

| Path | What |
|---|---|
| `autoconfig/` | Privileged JS (`myfox.cfg` + `myfox/*.js`) — prefs, sidebar panels, theme activation. Firefox's Autoconfig mechanism. |
| `chrome/` | CSS (`userChrome.css` + `agent/`/`user/`) — the actual visual tweaks. |
| `themes/` | Source for the two bundled theme add-ons (see `themes/README.md`). |
| `assets/` | Misc assets the installer bundles (not theme `.xpi`s — those come from Releases, see above). |
| `scripts/` | `build-themes.sh`/`sign-themes.sh` (AMO signing — see below), `firefox_rdp_proxy.py` (dev tool, see below). |

## Developing

Building/signing themes needs Node (`npx web-ext`) and an AMO API key:

```bash
scripts/build-themes.sh          # unsigned .xpi -> build/themes/ (dev only)
scripts/sign-themes.sh           # signed .xpi -> build/signed/ (needs AMO_JWT_ISSUER/AMO_JWT_SECRET)
```

The `.github/workflows/themes.yml` workflow does the same in CI (manual
trigger, or automatically when `themes/**` changes) and publishes the
signed `.xpi`s as a GitHub Release.

`scripts/firefox_rdp_proxy.py` lets you hot-reload CSS/JS changes against a
running Firefox without restarting it — see its own `--help`.

## Releases

The tweaks are released separately from the themes, with tags
`<Firefox beta major>.<patch>` (e.g. `158.0`). Each release has two files:

- `myfox-tweaks.tar.gz`: `autoconfig/` and `chrome/` at the archive root
- `changelog.json`: every released version from `CHANGELOG.md`, newest first

MyFox relies on this layout. Change it only together with MyFox.

To release a version:

1. Run `scripts/changelog_to_json.py --next` to get the next version number.
2. Add a `## <version> — <YYYY-MM-DD>` section to the top of `CHANGELOG.md`,
   with user-facing lines in English, and commit it.
3. `git tag <version> && git push origin <version>`.

The `.github/workflows/tweaks.yml` workflow fails if `CHANGELOG.md` has no
section for the tag. It warns if the tag's major isn't the current Firefox
beta. Then it builds the files (`scripts/build-tweaks-dist.sh`) and creates
the release. To test it without releasing, run it manually with `dry_run`;
the files are attached to the run instead.
