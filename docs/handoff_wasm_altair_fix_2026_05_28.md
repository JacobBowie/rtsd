# Handoff → rtSD Explorer session: WASM bundle broken on Pyodide (Altair version skew)

> **STATUS: RESOLVED in the rtSD repo (2026-05-28), pending re-release.** Applied the §4 cross-version theme fix in `_imports` (conditional `alt.theme.register` vs `alt.themes.register`, plain dict, no `ThemeConfig`) — host headless clean, no deprecation warning. Added defensive degradation around `.interactive(name=)` (§5 secondary-delta insurance: falls back to a static panel rather than break the tab). Made `build_wasm.py --export` strip the stray `CLAUDE.md` (§6; source is marimo's own `_static/CLAUDE.md` template asset). Could NOT reproduce locally via an old-Altair venv (Altair 5.4.1 won't import on host Python 3.13), so the **browser re-test on your side is the final gate**. Fixes committed; ready to cut a re-release of `rtsd-wasm.tar.gz` when you trigger it.

**From:** the Netlify deploy session (jacobbowie.com), 2026-05-28
**To:** the rtSD Explorer build session (this repo)
**Re:** your `docs/handoff_netlify_deploy_2026_05_28.md` — I deployed the bundle; it loads but the marimo app is fully broken in the browser. Root cause found, fix below.

---

## TL;DR

The `v0.2.0` WASM bundle deploys fine but **renders a wall of cell errors in the browser**. Root cause: the `_imports` cell uses the **Altair ≥5.5 / 6** theme API (`alt.theme.register` + `alt.theme.ThemeConfig`), but **Pyodide ships Altair < 5.5**, which only has the older `alt.themes` registry. `_imports` is the root cell, so its failure cascades to all 18 downstream cells. One contained fix (below) clears it. The module-inlining (#5488) you built **works perfectly** — that is not the problem.

## 1. Symptom (from the live Netlify deploy preview)

Browser console on `…/rtsd/notebook/`:

```
AttributeError: module 'altair.vegalite.v5.theme' has no attribute 'register'
  Cell marimo://notebook.py#cell=_imports, line 15
    @alt.theme.register("rtsd", enable=True)
```

Every other cell then reports: *"An ancestor raised an exception (AttributeError): _imports."* Nothing renders.

## 2. Root cause — Altair API version skew

Failing lines in `python/rtsd/rtsd.py`, `_imports` cell:

```python
@alt.theme.register("rtsd", enable=True)     # ← Altair >=5.5 / 6 only
def _rtsd_theme():
    return alt.theme.ThemeConfig({...})       # ← Altair >=5.5 / 6 only
```

`alt.theme.register` / `alt.theme.ThemeConfig` were introduced in **Altair 5.5.0**. Verified both ends:

| Environment | Altair | `alt.theme.register`? |
|---|---|---|
| Local host (`marimo run`) | **6.1.0** | yes → renders fine |
| Pyodide in the WASM bundle | **5.x** (`altair.vegalite.v5`, pre-5.5) | **no → AttributeError** |

`_imports` exports `alt, mo, np, pd, plt` to the whole reactive graph, so one AttributeError there blanks the entire notebook.

## 3. Why it passed locally — and the lesson

`marimo run rtsd.py` runs on **your host Python (Altair 6.1.0)**. The exported WASM bundle runs **Pyodide with its own Altair 5.x**, regardless of host. So "rendered locally" only proves the host path. The faithful local test is the *exported dist*, not `marimo run`:

```bash
python python/rtsd/build_wasm.py --export
cd python/rtsd/build/wasm && python -m http.server 8000   # open in a browser
```

That would have reproduced this error locally. Going forward, **smoke-test the dist in a browser** (or pin local Altair to match Pyodide), never just `marimo run`.

## 4. The fix (cross-version — works on Pyodide 5.x AND local 6.x)

Replace the theme block in the `_imports` cell with:

```python
    _ = alt.data_transformers.disable_max_rows()

    _RTSD_THEME = {
        "config": {
            "view": {"stroke": "transparent"},
            "axis": {"labelFontSize": 11, "titleFontSize": 12, "titleFontWeight": "normal",
                     "labelColor": "#555555", "titleColor": "#333333", "gridColor": "#ededed",
                     "domainColor": "#d0d0d0", "tickColor": "#d0d0d0"},
            "axisX": {"grid": False},
            "title": {"fontSize": 14, "fontWeight": "bold", "color": "#222222",
                      "anchor": "start", "offset": 10},
            "legend": {"labelFontSize": 11, "titleFontSize": 12, "titleColor": "#333333"},
            "background": "white",
            "font": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        }
    }
    # alt.theme.register is Altair >=5.5; Pyodide ships older 5.x (alt.themes registry).
    if hasattr(getattr(alt, "theme", None), "register"):
        alt.theme.register("rtsd", enable=True)(lambda: _RTSD_THEME)   # Altair >=5.5 / 6
    else:
        alt.themes.register("rtsd", lambda: _RTSD_THEME)               # Altair <5.5
        alt.themes.enable("rtsd")
```

Drop the `alt.theme.ThemeConfig(...)` wrapper — both APIs accept a plain dict.

> marimo auto-formatter caveat: stop any running `marimo edit` server before editing the file externally, or it will churn cell signatures / strip the `_imports` body.

## 5. Rebuild + RE-TEST (do not skip the browser step)

1. Apply the fix, then `python python/rtsd/build_wasm.py --export`.
2. **Browser-test the dist** (`cd build/wasm && python -m http.server 8000`), walk the §4 checklist from your original handoff: Pyodide boots, sliders drive the 4 panels, Save run + delete, Stock-and-flow tab renders, training-schedule bar.
3. The cascade masked any *secondary* v5/v6 deltas. Once `_imports` succeeds, watch for further AttributeErrors — e.g. confirm `Chart.interactive(name=...)` and the `alt.layer`/`vconcat`/`hconcat` calls behave on Pyodide's Altair 5.x. Fix any the same cross-version way.

## 6. Re-release contract (what the portfolio build pulls)

`jacobbowie.com`'s `netlify.toml` pulls this exact asset at build time:

- **Repo/tag:** `JacobBowie/rtsd` `v0.2.0`
- **Asset name:** `rtsd-wasm.tar.gz` (exact)
- **Layout:** `index.html` + `assets/` at the **tarball root**, and **exclude `CLAUDE.md`**:
  ```bash
  tar -czf /tmp/rtsd-wasm.tar.gz -C python/rtsd/build/wasm --exclude=./CLAUDE.md .
  gh release upload v0.2.0 /tmp/rtsd-wasm.tar.gz --clobber --repo JacobBowie/rtsd
  ```
  (Or cut `v0.2.1` and tell the Netlify session to bump `RTSD_TAG`.)
- **Two cleanups while you're here:**
  - The exported `build/wasm/` ships a stray **`CLAUDE.md`** (a leak). I excluded it from the tarball manually; please make `build_wasm.py --export` not copy it so future builds are clean.
  - `build_wasm.py` and today's working-tree changes are **uncommitted**, so the `v0.2.0` tag points at the pre-build_wasm.py commit. Commit them so the release is reproducible (clears the provenance caveat).

## 7. State on the Netlify / portfolio side (already done — do not redo)

- Branch `feat/rtsd-marimo-launch` + **PR #10** on `JacobBowie/jacobbowie-site` are fully staged: `/rtsd/` route, `/rtsd/notebook/` pull, `SAMEORIGIN` header, 301 `/work/synthesim` → `/rtsd/`, rebranded home tile + Work listing.
- `v0.2.0` release exists (with the **broken** asset). HTTP/routing/headers/redirect/extraction all verified green; only the bundle's JS runtime is broken.
- **PR #10 is held, not merged.** Once you re-release the fixed `rtsd-wasm.tar.gz`, the Netlify session re-triggers PR #10's deploy-preview, re-verifies in a browser, and merges to production.

## 8. Provenance

- Deploy + diagnosis: Netlify session, 2026-05-28 (live preview at `deploy-preview-10--jacobbowie.netlify.app`).
- Altair 5.5 theme-API change: confirmed via local `AltairDeprecationWarning` ("Deprecated since altair=5.5.0").

---

## 9. Re-release runbook (rtSD session → Netlify session, post-fix — EXECUTE THIS)

Supersedes §6's now-stale bits: the stray `CLAUDE.md` is auto-stripped by
`build_wasm.py` (no manual `--exclude` needed), and the fix IS committed.

- **Fix commit:** `b511b08` on `main` (rtSD repo). **NOT pushed yet** — `gh release`
  needs the commit on the `JacobBowie/rtsd` remote, so step 1 is a push (do it with
  Jacob's OK; the rtSD session deliberately did not push).

```bash
# 1. Push the fix (authorize first)
git -C Projects/synthesim push origin main

# 2. Build a fresh, clean WASM bundle (CLAUDE.md now auto-stripped)
python Projects/synthesim/python/rtsd/build_wasm.py --export

# 3. Tarball (index.html + assets/ at root; no --exclude needed now)
tar -czf /tmp/rtsd-wasm.tar.gz -C Projects/synthesim/python/rtsd/build/wasm .

# 4. Cut v0.2.1 at the FIX commit (v0.2.0 points at pre-fix code → don't reuse it)
git -C Projects/synthesim tag v0.2.1 b511b08
git -C Projects/synthesim push origin v0.2.1
gh release create v0.2.1 /tmp/rtsd-wasm.tar.gz --repo JacobBowie/rtsd \
   --title "rtSD Explorer v0.2.1 — WASM Altair cross-version fix"
```

- **5. Bump `RTSD_TAG=v0.2.1`** in the portfolio `netlify.toml`, re-trigger PR #10's
  deploy preview, **browser-verify** (Pyodide boots; sliders drive the 4 panels;
  Save run + `×` delete; Stock-and-flow tab renders; training bar), then merge.
- If anything else throws in the browser, it's likely another Altair v5/v6 delta —
  fix it the same cross-version way and re-cut.
