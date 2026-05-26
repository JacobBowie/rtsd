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

- Single-file Python port of the Shiny app via marimo.
- Reactive: change a slider, downstream cells recompute.
- Static export to WASM via `marimo export html-wasm rtsd.py -o rtsd.html` — runs in any browser, no server.
- Same RP program generator as Shiny + R; verify both produce identical TRIMP schedules if you touch one.

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
