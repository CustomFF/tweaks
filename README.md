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
