# Current state — rtSD Explorer

**v0.1.0** public (released as `synthesim` 2026-05-12; renamed to `rtSD Explorer` 2026-05-26 — same code, same model, just the brand).

**Status:** stable explorer + 7/7 reference-mode validator passing at v2 defaults. Three runtimes (Shiny / marimo / validator) all working via Docker.

**Python↔R parity gate landed (2026-05-28):** the marimo/Python model now lives in `python/rtsd/model.py` (single source of truth) and is gated by `tests/parity/` — 8/8 passing at machine-epsilon (~4e-15) relative deviation vs the R/deSolve reference (L0 ODE-core, L1 forcing-discretization, and the daily-dt default). The grid is built `seq`-equivalent so Python matches R `seq()` at any dt (no `np.arange` overshoot). This is the precondition for shipping marimo as the public surface. See CLAUDE.md → "Python↔R parity gate".

**marimo explorer redesigned into a dashboard (2026-05-28):** `mo.sidebar` + accordion controls + `mo.ui.tabs` + conditional reveal + interactive **altair** charts (shared theme, hover/zoom) + a `mo.state` snapshot overlay. Training-schedule bar sits atop the Trajectories tab. Defaults reworked to a *workable, illustrative* regime where Fitness grows: Baseline=60, Capacity=90 (static), **vol=400** (raised from 81 — FIT20 forcing is ~200× the Vensim scale; see the GET-PAID weights handoff memory), tau_fatigue=0.5, alpha=0.15, daily dt. These defaults are hand-picked demo values, NOT physically calibrated (absolute forcing scale unresolved — getpaid identifiability).

**B / E / F landed (2026-05-28):**
- **B — Snapshot annotation** ✓ named runs (`mo.ui.text` title) + per-run color + sidebar swatch legend + per-run delete. Save/compare regimes.
- **E — WASM-inline build** ✓ `python/rtsd/build_wasm.py` inlines `model.py` + `sd_diagram.py` (base64) into a `_bootstrap` cell (#5488 workaround). Validated by exporting from a dir with no sibling modules → clean. `python build_wasm.py --export` → `build/wasm/`.
- **F — Netlify handoff** ✓ `docs/handoff_netlify_deploy_2026_05_28.md` + root `netlify.toml`.

**Shipped (2026-06-03):** rtsd `v0.2.2` (interactive Prism trajectory dashboard) released; `jacobbowie-site` bumped `RTSD_TAG=v0.2.2`; deploy-preview browser-verified; merged to production. Live at <https://jacobbowie.com/rtsd/>.

**Next release** (v0.2) gated on:
- **L2 scenario-builder parity** — current gate covers L0+L1; full `scenario_*` parity (R vs Python builders) is a future pass.
- [verify] — sdviz spinoff scope decision
- [verify] — whether to ship `inst/shiny/rtsd/R/` mirror-sync as an automated check
- [verify] — landing of `posterior/` layer from the parent `getpaid/` hierarchical-calibration work

**Active blockers / open threads:**
- **Shiny app decommissioned (2026-06-03).** The `get-paid.shinyapps.io/synthesim/` app was terminated via `rsconnect::terminateApp`; both shinyapps slugs now 404. Canonical "Try it live" is the marimo/WASM build at `https://jacobbowie.com/rtsd/` (README/CITATION/DESCRIPTION repointed there in v0.2.2). Shiny source remains in `inst/shiny/rtsd/`, redeployable if ever needed.
- **Shiny `app.R` defaults now out of sync with marimo** — only the marimo notebook got the GET-PAID weights + the 2026-05-28 default rework. Decide whether to sync app.R.
- **FIT20 Performance-overlay CSV pending from GET-PAID** (handoff Part 3) — to bundle into the WASM build when delivered.
- Calibration work continues in `getpaid/`.
