# CLAUDE.md — rtSD Explorer

Orientation for future Claude sessions working in this repo. Project-specific facts only — general conventions live in `~/.claude/CLAUDE.md`.

## What this project is

**rtSD Explorer** is a public-facing Shiny + marimo interface for **rtSD**, a system-dynamics model of resistance-training adaptation. rtSD itself implements the **GET-PAID** framework — *Generating Expected Timelines of Predicted Adaptations to Imposed Demands*.

Three-tier picture:

| Tier | Name | Where it lives |
|---|---|---|
| Framework | **GET-PAID** | parent `getpaid/` project; theory + methodology papers |
| Model | **rtSD** | this repo's R package + the MEDv4 system-dynamics implementation |
| Tool | **rtSD Explorer** | this repo's Shiny app (`inst/shiny/rtsd/`) + marimo notebook (`python/rtsd/rtsd.py`) |

The repo was renamed from `synthesim` → `rtSD` on 2026-05-26 after discovering "SyntheSim" is a registered feature mark of Ventana Systems' Vensim DSS. The model and code are unchanged; only the name moved.

## Relationship to `getpaid/` (parent project)

This repo is a **slice from `getpaid/`**, not a fork or a successor. It carries:

- The MEDv4 three-stock fitness-fatigue-signal ODE
- The seven reference-mode validator
- A Shiny app + marimo notebook for interactive exploration
- Deterministic forward simulation only

What was **deliberately left behind** in `getpaid/`:

- Hierarchical Bayesian calibration of the MEDv4 family (Stan / cmdstanr)
- Individual-fitting pipeline against open RT cohort data
- Posterior-predictive scenario simulation
- Full PK/PD complexity

**Do NOT back-port new `getpaid/` features into rtSD without an explicit scope check.** The whole point of carving rtSD out was that it has a separable, minimal, public-shippable identity. Drifting back into being `getpaid-lite` defeats the purpose.

## What's load-bearing in `R/`

| File | What it does | Edit with care |
|---|---|---|
| `R/med_ode.R` | MEDv4 ODE right-hand side; linear + quadratic variants. The model itself. | Yes — changing equations changes the science. |
| `R/simulate.R` | Wrapper around `deSolve::ode`. Also called by Shiny app + marimo notebook. | Yes — API contract. |
| `R/scenarios.R` | Scenario builders (weekly training, detraining, RP mesocycles, custom event lists). | Add new scenarios here; don't inline in app code. |
| `R/training_schedule.R` | TRIMP forcing functions; Vensim-`PULSE TRAIN`-equivalent parameterization. | Yes — provenance trace back to Vensim. |
| `R/reference_mode_tests.R` | The seven-test physiological-plausibility validator with self-contained Euler integrator (no external solver). | Yes — this is the structural gate. Failing tests at sensible parameter values means the model is structurally wrong. |

## Shiny app (`inst/shiny/rtsd/`)

- **Self-contained.** `inst/shiny/rtsd/R/` carries its own copy of the simulator R files so the app deploys standalone to shinyapps.io without needing the package installed.
- This means changes to `R/*.R` at repo root need to be **mirrored** into `inst/shiny/rtsd/R/`. Not automated — easy to forget.
- Deployment: `https://get-paid.shinyapps.io/rtsd/`

## marimo notebook (`python/rtsd/rtsd.py`)

- Reactive Python surface. Change a slider, downstream cells recompute.
- **Model logic lives in `python/rtsd/model.py`** (the single source of truth: `med_rhs`, `simulate`, scenario builders). The notebook's `_model` / `_scenarios` cells are thin `from model import ...` shims. Edit the model in `model.py`, never inline in the notebook.
- **WASM export caveat — use the build script, never raw export.** `marimo export html-wasm` packages *only* `rtsd.py`; it does **not** bundle local module imports (`model.py`, `sd_diagram.py`; marimo issue #5488). A raw export throws `ModuleNotFoundError` in the browser. The fix is built: [`python/rtsd/build_wasm.py`](python/rtsd/build_wasm.py) inlines both modules (base64) into a `_bootstrap` cell and injects a `_boot` sentinel into the import cells so they run after it. Run `python python/rtsd/build_wasm.py --export` → `build/wasm/`. Validated for import resolution + cell execution, but **Pyodide runtime is unverified from source — verify in a browser on first deploy** (see `docs/handoff_netlify_deploy_2026_05_28.md`).
- **WASM ≠ `marimo run`: package versions differ.** `marimo run` uses host Python (e.g. Altair 6); the WASM bundle uses Pyodide's own (Altair <5.5). A v0.2.0 bundle broke in-browser because the theme used the Altair ≥5.5 API — fixed with cross-version registration in `_imports` (see `docs/handoff_wasm_altair_fix_2026_05_28.md`). **The faithful local test is the exported dist** (`build_wasm.py --export` → serve `build/wasm/` and open in a browser), not `marimo run`. Keep notebook code to the oldest Altair API or feature-detect.
- **Pinned runtime stack (so the WASM versions are reproducible, not emergent).** The browser runtime is determined by the marimo version that runs the export: **marimo 0.23.3 → Pyodide 0.27.5 → Altair 5.4.1 / pandas 2.2.3 / numpy 2.0.2** (read from Pyodide 0.27.5's lockfile; confirms the empirical "≥5.0, <5.5" band to the exact patch). This is pinned via a PEP 723 block in [`rtsd.py`](python/rtsd/rtsd.py) (`marimo==0.23.3`) and [`build_wasm.py`](python/rtsd/build_wasm.py); build reproducibly with **`uv run --script python/rtsd/build_wasm.py --export`**. The Netlify deploy MUST also use `marimo==0.23.3` or the stack drifts. To bump Altair, bump marimo (→ a newer Pyodide with a newer bundled Altair); you cannot pick Altair independently.
- **Local verification, no push needed (the payoff of pinning).** Because the stack is pinned, building + serving the dist locally is a faithful proxy for the deploy: `uv run --script python/rtsd/build_wasm.py --export`, then `python -m http.server 8000 -d build/wasm`, then open `localhost:8000` in a browser. That runs the *same* Pyodide 0.27.5 / Altair 5.4.1 Netlify would serve — so "works in my local browser" reliably predicts "works on Netlify." `marimo run` does NOT (host Altair 6 = false green); the browser-served dist is the test of record.
- `marimo edit` / `marimo run` work fine (real Python resolves the local imports); only the WASM export path is affected.

## Python↔R parity gate (`tests/parity/`)

- Proves `python/rtsd/model.py` reproduces the validated R model (`R/simulate.R`, deSolve euler — the Vensim/PySD-anchored authority) within tolerance. This is what makes the Python/marimo surface safe to ship.
- `cases.json` — shared spec read by both sides (identical inputs by construction). Layers: **L0** = pure ODE+Euler (constant forcing), **L1** = forcing discretization (explicit event list). L2 (full scenario-builder parity) is a future pass.
- `generate_golden.R` — R writes committed golden trajectories to `golden/*.csv`. Run only when equations change: `docker compose run --rm parity-golden` (needs deSolve + jsonlite, in the image).
- `test_parity.py` — pure-Python gate vs the goldens. Run on host (`python -m pytest tests/parity`) or via `docker compose run --rm parity`. Missing golden → skip, not fail.
- Known divergences the gate guards: **D1** param key rename (`max_frac_rate` ↔ `maximal_fractional_rate`), **D2** grid endpoint (`np.arange` vs `seq`).

## Vensim source (`inst/vensim/MEDv4_secondary_signal.mdl`)

The original Vensim `.mdl` file is shipped as read-only provenance. Do not edit it. If the model structure changes, update R + Python first, then regenerate or hand-update the Vensim file as a separate step.

## Docker (`Dockerfile`, `docker-compose.yml`)

- One image, three entrypoints (Shiny / marimo / validator) on `rocker/r-ver:4.5.2`.
- Posit Package Manager binaries (PPM) for fast R installs.
- Marimo + numpy + matplotlib in an isolated venv at `/opt/venv`.
- Build: `docker compose build` once, then `docker compose up shiny` / `marimo` / `run --rm validate`.
- **For this project, run Docker commands yourself** rather than handing them to the user (see [memory:run-docker-yourself]).

## Code conventions specific to this repo

- **Always `dplyr::select()`**, never bare `select()` (per `~/.claude/rules/r.md`).
- Stock colors are standardized as `STOCK_COLORS` in `inst/shiny/rtsd/app.R` — re-use don't redefine.
- Reference-mode test thresholds live in `R/reference_mode_tests.R` — anchored to citations in the README table; don't loosen thresholds without updating the citation anchor too.

## Roadmap / coming attractions (do not pre-implement)

- **Hierarchical Bayesian calibration** — lives in `getpaid/`, will land here later as a `posterior/` layer.
- **`sdviz`** — planned spin-off of the Vensim-style diagrammer + reference-mode dashboard plotting into a reusable Python visualization library. Not started.
- **GET-FIT calculator** — parked spinoff: a lay-audience thin surface on top of rtSD. See [memory:future-getfit-calculator]. Don't build until v0.2+ stable.

## When in doubt

- The MEDv4 model equations: `R/med_ode.R` + `docs/theory.md`
- The validation gate: `R/reference_mode_tests.R` + `tests/validate_reference_modes.R`
- The naming-workshop history (why "rtSD" and not "synthesim" or "Allostat" or "Athlos"): [memory:rename-to-rtsd]
