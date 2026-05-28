# Handoff → Netlify deploy agent: rtSD Explorer (marimo WASM)

**From:** rtSD Explorer session, 2026-05-28
**To:** the agent deploying the marimo explorer as a static site on Netlify
**Goal:** publish `python/rtsd/rtsd.py` (the marimo notebook) as a self-contained
in-browser WASM app on Netlify — no server, free hosting.

---

## 1. What ships

The deployable artifact is a **WASM/Pyodide static bundle** built from the marimo
notebook. It runs entirely in the browser (Python via Pyodide); Netlify only
serves static files. Bundle = `index.html` + `assets/` (~682 files) + PWA icons +
`.nojekyll`.

## 2. The one sharp edge — local-module inlining (DO NOT skip)

`marimo export html-wasm` bundles **only the notebook file**. It does NOT include
sibling local modules. The notebook imports two: `model.py` (the MEDv4 model,
single source of truth) and `sd_diagram.py` (the stock-and-flow diagram). A raw
`marimo export html-wasm rtsd.py` therefore throws `ModuleNotFoundError` in the
browser. This is marimo issue **#5488** (open as of v0.23.8) — not a config error.

**The fix is already built:** [`python/rtsd/build_wasm.py`](../python/rtsd/build_wasm.py).
It generates `build/rtsd_wasm.py` — the notebook with both modules inlined
(base64) and registered in `sys.modules` via a `_bootstrap` cell, with the
`_boot` sentinel injected into the import cells' signatures so they run *after*
the bootstrap. (marimo does **not** execute top-level non-cell code before cells
— verified — so the bootstrap had to be a cell, not a top-level block.)

**Verified:** exporting the build file from a directory containing NO `model.py`
/ `sd_diagram.py` resolves all imports and renders cleanly (0 failed cells). So
the inlining works in marimo's execution model, which Pyodide shares.

## 3. Build + deploy

A ready `netlify.toml` is at the repo root:

```toml
[build]
  command = "pip install 'marimo>=0.23.0' numpy pandas altair matplotlib && python python/rtsd/build_wasm.py --export"
  publish = "python/rtsd/build/wasm"
[build.environment]
  PYTHON_VERSION = "3.12"
[[headers]]
  for = "/*.wasm"
  [headers.values]
    Content-Type = "application/wasm"
```

`build/` is gitignored — Netlify regenerates it at build time. Local dry-run:

```bash
python python/rtsd/build_wasm.py --export      # writes python/rtsd/build/wasm/
cd python/rtsd/build/wasm && python -m http.server 8000   # open http://localhost:8000
```

## 4. CRITICAL — verify in a browser before declaring done

The build was validated for *import resolution and cell execution* in marimo's
runtime, but the originating session is **source-blind and could not load the
bundle in a browser**. Pyodide-runtime correctness is unverified. On first
deploy (or local `http.server`), confirm in the browser:

- [ ] Page loads; Pyodide boots (first load ~10–30 s — add a loading note if jarring).
- [ ] No console `ModuleNotFoundError` / `micropip` failures (numpy, pandas, altair, matplotlib are all in Pyodide, but verify).
- [ ] Sliders drive the four trajectory panels reactively.
- [ ] **Save run** adds a named, colored line; sidebar swatch + `×` delete work.
- [ ] The **Stock-and-flow** tab renders the matplotlib diagram (this is the `sd_diagram.py` import — the second inlined module).
- [ ] Training-schedule bar renders atop the Trajectories tab.

If a cell errors only in WASM (not in `marimo run`), it's almost certainly a
Pyodide package-availability issue — check the browser console.

## 5. Security

Pin **`marimo>=0.23.0`** (done in `netlify.toml`). CVE-2026-39987 is a CVSS-9.3
pre-auth RCE in marimo ≤0.20.4, actively exploited. Static WASM exports have no
server and aren't themselves vulnerable, but the build environment must be patched.

## 6. Gotchas

- **Cold start / bundle size**: Pyodide + scientific stack is tens of MB first
  load, cached thereafter. ~25 MB/first-load on Netlify Free (100 GB/mo) ≈ a few
  thousand first-loads/month. Fine for a portfolio.
- **Embedding in a Quarto/portfolio site later**: a site-wide
  `X-Frame-Options: DENY` will silently block even a same-origin iframe — needs a
  per-route `SAMEORIGIN` override. See the marimo skill §20.4b (release-artifact
  pattern) if pulling this into `jacobbowie.com` rather than hosting standalone.
- **Local `build/wasm/` may contain stale files** from a prior export (e.g. an
  old `CLAUDE.md`); irrelevant for CI (Netlify builds fresh), but don't hand-copy
  the local dir as the deploy source.

## 7. Related / deferred (not blocking this deploy)

- **FIT20 Performance-overlay CSV** — pending from GET-PAID (handoff Part 3). When
  it lands, it gets bundled into the WASM build (place under a `public/` dir the
  notebook reads via `mo.notebook_location()`), then re-export. Will require a
  rebuild + redeploy.
- **Shiny `app.R` defaults** are out of sync with the marimo notebook (only marimo
  got the 2026-05-28 reworked defaults). Unrelated to this deploy.
- **Broken `get-paid.shinyapps.io/rtsd/` link** (404; app is live at the old
  `synthesim` slug) — a separate Shiny-deploy issue, not Netlify.

## 8. Provenance

- Build mechanism + validation: this session, 2026-05-28 (`build_wasm.py`,
  clean-dir export test).
- WASM local-import limitation: marimo issue #5488; deep-research report, 2026-05-28.
- The defaults the bundle ships: see `CURRENT_STATE.md` + the GET-PAID weights
  memory (illustrative, not publication-grade).
