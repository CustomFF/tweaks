# Testing these tweaks

No automated tests — static checks plus a manual checklist, run after
applying the tweaks (by hand per `README.md`, or via
[myfox](https://github.com/CustomFF/myfox)) and restarting Firefox.
Test on beta first, stable only once beta looks right (Firefox's Nova
redesign is beta-only and several selectors depend on it).

## Static checks

```bash
for f in autoconfig/myfox.cfg autoconfig/myfox/*.js; do cp "$f" /tmp/fc.js && node --check /tmp/fc.js; done
grep -rn 'url(' chrome/user chrome/agent | grep -v 'chrome://\|data:'   # relative url()s must use ../, nothing else
```

## Fresh profile, first start

- [ ] bookmarks toolbar has exactly two bookmarks ("Advanced settings" → about:config,
      "Add bookmarklets" → ddblm, `?lang=ru` for a Russian-language Firefox) with icons,
      and they survive a second restart
- [ ] no "Import bookmarks"/profile-avatar buttons; about:welcome doesn't show
- [ ] bookmarks toolbar always visible (`browser.toolbars.bookmarks.visibility=always`)
- [ ] compact density; AI/Pocket/sponsored content/telemetry off
- [ ] the chosen theme is active; "website appearance" follows it

## Styling

- [ ] floating "card" tabs with ears; page and sidebar are also cards; one
      consistent corner radius everywhere; no purple anywhere (new tab,
      about:preferences, buttons)
- [ ] sidebar: bookmarks/history/synced-tabs rows sit below the header, no
      pill shapes, tight; downloads panel has its own header/search/"Clear";
      passwords panel background matches the others
- [ ] round close (✕) buttons on tabs on hover, even with many tabs open;
      sidebar has its own close button
- [ ] about:preferences / about:logins / about:addons / about:processes use
      12px text, no pill-shaped rows
- [ ] light theme: the selected tab is set off with a shadow — check this on
      both stable and beta
- [ ] `userChrome.css`'s `@import user/*.css` picks up all files, and every
      `chrome/agent/*.css` sheet registers — check **after a restart**:
      content-process pages (about:newtab, about:preferences) don't pick up
      a live agent-sheet re-registration, only a fresh start

## A foreign profile stays untouched

Create a second profile in the same Firefox install, without applying any
tweaks to it, and launch `firefox -P <name>`:

- [ ] no files under `<profile>/chrome/`, no `.myfox` marker, no `myfox.*`
      prefs set, no bookmarks added — plain stock Firefox

## Bookmarklets (ddblm)

```bash
MYFOX_DDBLM_LOCAL=/path/to/ddblm-checkout <however you apply tweaks>   # to test local ddblm edits
```

- [ ] `<profile>/chrome/` has `blm_panel.css` and every `panel-icons/*.svg`
      (including `import-bookmarklets.svg`)
- [ ] icons and hidden labels apply; drag-and-drop from the gallery works
- [ ] an unreachable source (404) is a warning + skip, never a hard failure

## Applying by hand (README.md's own instructions)

- [ ] on a throwaway profile, follow `README.md`'s steps 1-4 exactly — the
      tweaks work
- [ ] skip step 3 (the `.myfox` marker) — the tweaks do **not** apply; no
      error, just silently inert (by design — see `autoconfig/myfox.cfg`'s
      guard)

## After editing styles/scripts

- [ ] `myfox.cfg`: `node --check` passes; a real Firefox start (not
      `--headless --screenshot` — it exits before the async setup runs)
      applies the same `myfox.*` prefs and bookmarks as before, no errors in
      the Browser Console
- [ ] after splitting/moving CSS, diff computed styles before/after on a
      live Firefox (main window + sidebars) — should be identical
- [ ] `scripts/reload_userchrome.py` (talks to `scripts/firefox_rdp_proxy.py`
      for hot-reload) still works: `userChrome.css` + `agent/*.css` reload
      without a restart

## Where to look

- profile: `about:support` → "Profile Folder"
- Browser Console: `about:devtools-toolbox` or Ctrl+Shift+J, for `myfox.cfg`/JS errors
- a local ddblm checkout for `MYFOX_DDBLM_LOCAL`: wherever you cloned
  [ddblm](https://github.com/CustomFF/ddblm)
