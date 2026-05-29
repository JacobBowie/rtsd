# Build/deploy reproducibility: pinning marimo==0.23.3 pins Pyodide 0.27.5, whose
# bundle is the WASM runtime — Altair 5.4.1 / pandas 2.2.3 / numpy 2.0.2. The
# scientific deps below are intentionally UNPINNED: host-side `marimo edit --sandbox`
# (Python 3.13) must resolve compatible versions (Altair 5.4.1 won't install on 3.13),
# while the browser always gets Pyodide's bundled wheels regardless. See CLAUDE.md.
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo==0.23.3",
#     "altair",
#     "numpy",
#     "pandas",
#     "matplotlib",
# ]
# ///
"""rtSD Explorer — MEDv4 fitness-fatigue-signal explorer (marimo notebook).

Reactive Python surface for the rtSD model. Same model + RP program generator
as the Shiny app, restructured as a dashboard:

  - left sidebar of accordion-grouped controls (mo.sidebar + mo.accordion)
  - tabbed output area (mo.ui.tabs): trajectories / diagram / training / state
  - interactive altair trajectory charts (hover tooltips, zoom/pan)
  - snapshot overlay: save a run, compare later runs against it (mo.state)

Model logic lives in python/rtsd/model.py (single source of truth, gated by
tests/parity/). The notebook only imports it.

Run interactively:   python -m marimo edit python/rtsd/rtsd.py
Run as an app:       python -m marimo run  python/rtsd/rtsd.py

WASM note: `marimo export html-wasm` does NOT bundle the local imports
(`model.py`, `sd_diagram.py`); a build step that inlines them is required
before the WASM artifact is shippable. See CLAUDE.md.
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="full")


@app.cell
def _imports():
    import marimo as mo
    import numpy as np
    import pandas as pd
    import altair as alt
    import matplotlib.pyplot as plt

    # Trajectories can exceed altair's default 5000-row guard once snapshots
    # accumulate; data is local (and bundled in WASM), so disabling is safe.
    # Assign to _ so the registry repr isn't rendered as this cell's output.
    _ = alt.data_transformers.disable_max_rows()

    # Shared chart theme. CROSS-VERSION: alt.theme.register / alt.theme.ThemeConfig
    # are Altair >=5.5; Pyodide (the WASM runtime) ships older 5.x with only the
    # alt.themes registry. _imports is the root cell, so using the 5.5+ API
    # unconditionally blanks the entire WASM bundle (AttributeError cascade).
    # Both APIs accept a plain dict — no ThemeConfig wrapper.
    # See docs/handoff_wasm_altair_fix_2026_05_28.md.
    _RTSD_THEME = {
        "config": {
            "view": {"stroke": "transparent"},
            "axis": {
                "labelFontSize": 11, "titleFontSize": 12, "titleFontWeight": "normal",
                "labelColor": "#555555", "titleColor": "#333333", "gridColor": "#ededed",
                "domainColor": "#d0d0d0", "tickColor": "#d0d0d0",
            },
            "axisX": {"grid": False},
            "title": {
                "fontSize": 14, "fontWeight": "bold", "color": "#222222",
                "anchor": "start", "offset": 10,
            },
            "legend": {"labelFontSize": 11, "titleFontSize": 12, "titleColor": "#333333"},
            "background": "white",
            "font": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        }
    }
    if hasattr(getattr(alt, "theme", None), "register"):
        alt.theme.register("rtsd", enable=True)(lambda: _RTSD_THEME)  # Altair >=5.5 / 6
    else:
        alt.themes.register("rtsd", lambda: _RTSD_THEME)              # Altair <5.5 (Pyodide)
        alt.themes.enable("rtsd")
    return alt, mo, np, pd, plt


@app.cell
def _palette():
    """Stock colors (synced with Shiny app.R) + a categorical palette for
    saved-run snapshots, chosen not to clash with the four stock colors."""
    STOCK_COLORS = {
        "Fitness": "#1565C0",
        "Fatigue": "#C62828",
        "Signal": "#F9A825",
        "Performance": "#2E7D32",
    }
    SNAP_PALETTE = [
        "#6A1B9A", "#00838F", "#EF6C00", "#5D4037",
        "#AD1457", "#558B2F", "#283593", "#00695C",
    ]
    return SNAP_PALETTE, STOCK_COLORS


@app.cell
def _model():
    """MEDv4 ODE + Euler integrator, imported from python/rtsd/model.py."""
    from model import simulate

    return (simulate,)


@app.cell
def _scenarios():
    """Training-scenario builders, imported from python/rtsd/model.py."""
    from model import (
        make_training_fn,
        scenario_detraining,
        scenario_high_freq,
        scenario_rp,
        scenario_standard,
        scenario_untrained,
    )

    return (
        make_training_fn,
        scenario_detraining,
        scenario_high_freq,
        scenario_rp,
        scenario_standard,
        scenario_untrained,
    )


@app.cell
def _ui_controls(mo):
    """Simulation controls (assembled into the sidebar by the _sidebar cell)."""
    variant = mo.ui.dropdown(
        options={"Linear (recommended)": "linear", "Quadratic": "quadratic"},
        value="Linear (recommended)",
        label="ODE variant",
    )
    scenario = mo.ui.dropdown(
        options={
            "Standard weekly": "standard",
            "High frequency": "high_freq",
            "Detraining": "detraining",
            "Untrained (ADL only)": "untrained",
            "Renaissance Periodization": "rp",
        },
        value="Standard weekly",
        label="Training scenario",
    )
    horizon = mo.ui.slider(4, 200, value=48, step=1, label="Horizon (weeks)", show_value=True)
    dt = mo.ui.dropdown(
        options={
            "Daily (1/7 wk)": "0.14285714285714285",
            "Sub-daily (1/16 wk)": "0.0625",
            "Coarse (1/4 wk)": "0.25",
        },
        value="Daily (1/7 wk)",
        label="Integration dt",
    )
    sessions_per_week = mo.ui.slider(1, 7, value=3, step=1, label="Sessions / week", show_value=True)
    vol = mo.ui.slider(0, 1500, value=400, step=10, label="Volume / session (impulse, model units)", show_value=True)
    detrain_start = mo.ui.slider(4, 100, value=24, step=1, label="Detrain after (wk)", show_value=True)
    return (
        detrain_start,
        dt,
        horizon,
        scenario,
        sessions_per_week,
        variant,
        vol,
    )


@app.cell
def _ui_rp(mo):
    """Renaissance Periodization controls (active when scenario = 'rp')."""
    rp_mev = mo.ui.slider(2, 30, value=8, step=1, label="MEV (sets/wk)", show_value=True)
    rp_mrv = mo.ui.slider(4, 40, value=18, step=1, label="MRV (sets/wk)", show_value=True)
    rp_accum = mo.ui.slider(2, 8, value=4, step=1, label="Accumulation weeks", show_value=True)
    rp_deload = mo.ui.slider(0, 3, value=1, step=1, label="Deload weeks", show_value=True)
    rp_n_meso = mo.ui.slider(1, 8, value=3, step=1, label="# Mesocycles", show_value=True)
    rp_work_per_set = mo.ui.slider(10, 300, value=80, step=5, label="Work / set (TRIMP)", show_value=True)
    rp_deload_frac = mo.ui.slider(0.2, 1.0, value=0.5, step=0.05, label="Deload fraction of MEV", show_value=True)
    rp_mev_creep = mo.ui.slider(0, 6, value=0, step=1, label="MEV creep / mesocycle", show_value=True)
    return (
        rp_accum,
        rp_deload,
        rp_deload_frac,
        rp_mev,
        rp_mev_creep,
        rp_mrv,
        rp_n_meso,
        rp_work_per_set,
    )


@app.cell
def _ui_params(mo):
    """ODE parameters.

    Defaults = GET-PAID's reference-mode-validated weights (handoff 2026-05-28):
    physiologically-grounded, fit-anchored, illustrative — NOT publication-grade.
    Capacity is an atrophy scale (NOT a fitness ceiling); its default 90 = 1.5×
    the default Baseline 60 (the validated 1.5×Baseline regime). Capacity stays
    an independent slider — it does not auto-track Baseline. Ranges/steps widened
    so each default is representable and explorable around the validated point.
    tau_fatigue, alpha, and the default training volume (≈400, raised from the
    Vensim-scale 81 toward the FIT20 fit scale) are PI/display tunings on top of
    the fitted set — illustrative, to give a sensible "training works" default."""
    adaptation_rate = mo.ui.slider(0.001, 0.05, value=0.018, step=0.001, label="adaptation_rate", show_value=True)
    adaptation_delay = mo.ui.slider(1.0, 20.0, value=5.75, step=0.25, label="adaptation_delay (wk)", show_value=True)
    max_frac_rate = mo.ui.slider(0.0001, 0.05, value=0.0077, step=0.0001, label="max_frac_rate", show_value=True)
    Capacity = mo.ui.slider(20, 400, value=90, step=5, label="atrophy-scale (Capacity)", show_value=True)
    tau_fatigue = mo.ui.slider(0.1, 5.0, value=0.5, step=0.05, label="tau_fatigue (wk)", show_value=True)
    tau_signal = mo.ui.slider(0.1, 30.0, value=1.0, step=0.1, label="tau_signal (wk)", show_value=True)
    adl_trimp = mo.ui.slider(0, 60, value=19, step=1, label="adl_trimp", show_value=True)
    alpha = mo.ui.slider(0.0, 2.0, value=0.15, step=0.05, label="alpha (Performance)", show_value=True)
    Baseline = mo.ui.slider(1.0, 120.0, value=60.0, step=0.5, label="Baseline Fitness", show_value=True)
    return (
        Baseline,
        Capacity,
        adaptation_delay,
        adaptation_rate,
        adl_trimp,
        alpha,
        max_frac_rate,
        tau_fatigue,
        tau_signal,
    )


@app.cell
def _snapshot_state(mo):
    """Shared snapshot list. The canonical mo.state use case: a 'save run'
    button appends to a list the trajectory chart overlays as colored lines."""
    get_snaps, set_snaps = mo.state([])
    return get_snaps, set_snaps


@app.cell
def _snap_title_input(mo):
    """Run-name input in its OWN cell (NO simulation dependencies), so the text
    the user types survives slider changes. _snap_controls reads it at click
    time. If this lived in _snap_controls (which depends on the live sim), the
    element would be re-created on every slider move and the name would be lost."""
    snap_title = mo.ui.text(placeholder="name this regime (optional)…", label="")
    return (snap_title,)


@app.cell
def _build_training(
    detrain_start,
    dt,
    horizon,
    make_training_fn,
    np,
    rp_accum,
    rp_deload,
    rp_deload_frac,
    rp_mev,
    rp_mev_creep,
    rp_mrv,
    rp_n_meso,
    rp_work_per_set,
    scenario,
    scenario_detraining,
    scenario_high_freq,
    scenario_rp,
    scenario_standard,
    scenario_untrained,
    sessions_per_week,
    vol,
):
    """Reactive training-schedule construction."""
    dt_v = float(dt.value)
    # seq-equivalent grid — must mirror model.simulate (matches R seq(); no
    # phantom step past horizon at dt that doesn't divide evenly, e.g. daily 1/7).
    grid = np.arange(round(horizon.value / dt_v) + 1) * dt_v

    if scenario.value == "standard":
        sched = scenario_standard(grid, sessions_per_week.value, vol.value, horizon.value)
    elif scenario.value == "high_freq":
        sched = scenario_high_freq(grid, sessions_per_week.value, vol.value, horizon.value)
    elif scenario.value == "detraining":
        sched = scenario_detraining(grid, detrain_start.value, sessions_per_week.value, vol.value)
    elif scenario.value == "untrained":
        sched = scenario_untrained(grid)
    else:  # "rp"
        sched = scenario_rp(
            grid,
            n_mesocycles=rp_n_meso.value,
            accumulation_weeks=rp_accum.value,
            deload_weeks=rp_deload.value,
            mev_sets=rp_mev.value,
            mrv_sets=rp_mrv.value,
            sessions_per_week=sessions_per_week.value,
            work_per_set=float(rp_work_per_set.value),
            deload_fraction=rp_deload_frac.value,
            mev_creep_per_cycle=rp_mev_creep.value,
        )
    training_fn = make_training_fn(grid, sched)
    return dt_v, sched, training_fn


@app.cell
def _run_sim(
    Baseline,
    Capacity,
    adaptation_delay,
    adaptation_rate,
    adl_trimp,
    alpha,
    dt_v,
    horizon,
    max_frac_rate,
    simulate,
    tau_fatigue,
    tau_signal,
    training_fn,
    variant,
):
    """Reactive forward simulation."""
    params = dict(
        adaptation_rate=adaptation_rate.value,
        adaptation_delay=adaptation_delay.value,
        max_frac_rate=max_frac_rate.value,
        Capacity=Capacity.value,
        tau_fatigue=tau_fatigue.value,
        tau_signal=tau_signal.value,
        adl_trimp=adl_trimp.value,
        Baseline=Baseline.value,
    )
    grid_t, traj = simulate(
        params=params,
        horizon=horizon.value,
        dt=dt_v,
        training_fn=training_fn,
        variant=variant.value,
    )
    Fitness = traj[:, 0]
    Fatigue = traj[:, 1]
    Signal = traj[:, 2]
    Performance = Fitness - alpha.value * Fatigue
    return Fatigue, Fitness, Performance, Signal, grid_t


@app.cell
def _snap_controls(
    Capacity,
    Fatigue,
    Fitness,
    Performance,
    SNAP_PALETTE,
    Signal,
    adaptation_rate,
    get_snaps,
    grid_t,
    max_frac_rate,
    mo,
    np,
    set_snaps,
    snap_title,
    variant,
    vol,
):
    """Save-run controls: name a regime (snap_title comes from _snap_title_input),
    save it (captures the current trajectory + a distinct color + a stable id),
    or clear all. The _saved_runs cell lists saved runs with per-run delete."""

    def _take_snapshot(_v):
        _existing = get_snaps()
        _nid = (max(x["id"] for x in _existing) + 1) if _existing else 0
        _auto = (
            f"vol{vol.value:.0f} ar{adaptation_rate.value:.3f} "
            f"mfr{max_frac_rate.value:.4f} C{Capacity.value:.0f} {variant.value}"
        )
        snap = {
            "id": _nid,
            "title": snap_title.value.strip() or _auto,
            "color": SNAP_PALETTE[_nid % len(SNAP_PALETTE)],
            "time": np.array(grid_t),
            "Fitness": np.array(Fitness),
            "Fatigue": np.array(Fatigue),
            "Signal": np.array(Signal),
            "Performance": np.array(Performance),
        }
        set_snaps(_existing + [snap])

    snapshot_btn = mo.ui.button(label="Save run", on_click=_take_snapshot, kind="success")
    clear_btn = mo.ui.button(label="Clear all", on_click=lambda _: set_snaps([]), kind="neutral")
    return clear_btn, snapshot_btn


@app.cell
def _saved_runs(get_snaps, mo, set_snaps):
    """Saved-run legend + per-run delete (rendered in the sidebar). The color
    swatches here ARE the chart legend — the trajectory panels carry no legend."""
    _snaps = get_snaps()
    if not _snaps:
        saved_runs_panel = mo.md("*No saved runs yet. Set parameters, then **Save run**.*")
    else:
        _rows = []
        for _s in _snaps:
            _del = mo.ui.button(
                label="×",
                on_click=lambda _v, _i=_s["id"]: set_snaps(
                    [x for x in get_snaps() if x["id"] != _i]
                ),
            )
            _swatch = mo.md(
                f"<span style='display:inline-block;width:11px;height:11px;"
                f"background:{_s['color']};border-radius:2px;'></span>"
            )
            _rows.append(
                mo.hstack(
                    [_swatch, mo.md(f"<small>{_s['title']}</small>"), _del],
                    justify="start",
                    align="center",
                    gap=0.4,
                )
            )
        saved_runs_panel = mo.vstack(_rows, gap=0.25)
    return (saved_runs_panel,)


@app.cell
def _sidebar(
    Baseline,
    Capacity,
    adaptation_delay,
    adaptation_rate,
    adl_trimp,
    alpha,
    clear_btn,
    detrain_start,
    dt,
    horizon,
    max_frac_rate,
    mo,
    rp_accum,
    rp_deload,
    rp_deload_frac,
    rp_mev,
    rp_mev_creep,
    rp_mrv,
    rp_n_meso,
    rp_work_per_set,
    saved_runs_panel,
    scenario,
    sessions_per_week,
    snap_title,
    snapshot_btn,
    tau_fatigue,
    tau_signal,
    variant,
    vol,
):
    """Left control rail: accordion-grouped controls + save-run/compare panel.
    Conditional reveal mirrors the Shiny conditionalPanel logic."""
    _sim = [variant, scenario, horizon, dt, sessions_per_week]
    if scenario.value != "rp":
        _sim.append(vol)
    if scenario.value == "detraining":
        _sim.append(detrain_start)

    _controls = mo.accordion(
        {
            "Simulation": mo.vstack(_sim),
            "Renaissance Periodization": mo.vstack(
                [rp_mev, rp_mrv, rp_accum, rp_deload, rp_n_meso,
                 rp_work_per_set, rp_deload_frac, rp_mev_creep]
            ),
            "Adaptation & atrophy": mo.vstack(
                [adaptation_rate, adaptation_delay, max_frac_rate, Capacity]
            ),
            "Time constants & baseline": mo.vstack(
                [tau_fatigue, tau_signal, adl_trimp, alpha, Baseline]
            ),
        },
        multiple=True,
    )

    mo.sidebar(
        [
            mo.md("## rtSD Explorer"),
            mo.md("*MEDv4 fitness-fatigue-signal model*"),
            _controls,
            mo.md("---"),
            mo.md("**Compare regimes** — save the current run to overlay it"),
            snap_title,
            mo.hstack([snapshot_btn, clear_btn], justify="start", gap=0.5),
            saved_runs_panel,
        ],
        width="360px",
    )
    return


@app.cell
def _traj_chart(
    Fatigue,
    Fitness,
    Performance,
    STOCK_COLORS,
    Signal,
    alt,
    get_snaps,
    grid_t,
    np,
    pd,
):
    """Interactive 4-panel trajectory chart (altair). Live run in color;
    saved snapshots overlaid as gray lines."""
    _stocks = list(STOCK_COLORS.keys())
    _live = pd.DataFrame(
        {
            "time": np.tile(grid_t, len(_stocks)),
            "value": np.concatenate([Fitness, Fatigue, Signal, Performance]),
            "stock": np.repeat(_stocks, len(grid_t)),
        }
    )

    _snap_list = get_snaps()
    _snap_frames = []
    for _s in _snap_list:
        for _name in _stocks:
            _snap_frames.append(
                pd.DataFrame(
                    {
                        "time": _s["time"],
                        "value": _s[_name],
                        "stock": _name,
                        "sid": str(_s["id"]),
                        "title": _s["title"],
                    }
                )
            )
    _snaps = (
        pd.concat(_snap_frames, ignore_index=True)
        if _snap_frames
        else pd.DataFrame(columns=["time", "value", "stock", "sid", "title"])
    )
    # Snapshot lines use each run's stored color (id-keyed so duplicate titles
    # don't collide); the sidebar swatches serve as the legend, so legend=None.
    _snap_color = alt.Scale(
        domain=[str(s["id"]) for s in _snap_list],
        range=[s["color"] for s in _snap_list],
    )

    # One independent chart per stock, arranged 2x2. Per-panel charts (rather
    # than a faceted layered chart) are required because altair cannot facet a
    # layer whose sub-layers have different data (live vs. snapshot rows).
    def _panel(_stock):
        _layers = []
        if len(_snaps):
            _ss = _snaps[_snaps["stock"] == _stock]
            _layers.append(
                alt.Chart(_ss)
                .mark_line(strokeWidth=1.3, opacity=0.75)
                .encode(
                    x=alt.X("time:Q", title="Time (weeks)"),
                    y=alt.Y("value:Q", title=_stock, scale=alt.Scale(zero=False)),
                    color=alt.Color("sid:N", scale=_snap_color, legend=None),
                    detail="sid:N",
                    tooltip=[
                        alt.Tooltip("title:N", title="Run"),
                        alt.Tooltip("value:Q", title=_stock, format=".2f"),
                    ],
                )
            )
        _ls = _live[_live["stock"] == _stock]
        _layers.append(
            alt.Chart(_ls)
            .mark_line(strokeWidth=2.5, color=STOCK_COLORS[_stock])
            .encode(
                x=alt.X("time:Q", title="Time (weeks)"),
                y=alt.Y("value:Q", title=_stock, scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("time:Q", title="Week", format=".2f"),
                    alt.Tooltip("value:Q", title=_stock, format=".2f"),
                ],
            )
        )
        _chart = _layers[0] if len(_layers) == 1 else alt.layer(*_layers)
        _chart = _chart.properties(width=380, height=220, title=_stock)
        # interactive(name=) gives independent per-panel zoom on Altair 5.x+.
        # Guard it: if a particular Altair build rejects the call, fall back to a
        # static panel (tooltips still work) rather than break the Trajectories
        # tab. Belt-and-braces alongside the cross-version theme fix in _imports.
        try:
            return _chart.interactive(name="zoom_" + _stock)
        except Exception:
            return _chart

    _panels = [_panel(s) for s in _stocks]
    traj_chart = alt.vconcat(
        alt.hconcat(_panels[0], _panels[1]),
        alt.hconcat(_panels[2], _panels[3]),
    )
    return (traj_chart,)


@app.cell
def _training_chart(alt, grid_t, pd, scenario, sched):
    """Training-schedule bar chart (altair)."""
    _df = pd.DataFrame({"time": grid_t, "TRIMP": sched})
    training_chart = (
        alt.Chart(_df)
        .mark_bar(width=2, color="#1565C0")
        .encode(
            x=alt.X("time:Q", title="Time (weeks)"),
            y=alt.Y("TRIMP:Q", title="TRIMP / step"),
            tooltip=[alt.Tooltip("time:Q", format=".2f"), alt.Tooltip("TRIMP:Q", format=".1f")],
        )
        .properties(width=780, height=170, title=f"Training schedule — scenario: {scenario.value}")
    )
    return (training_chart,)


@app.cell
def _diagram(plt):
    """Vensim-style stock-and-flow diagram of MEDv4 (matplotlib via sd_diagram)."""
    from sd_diagram import draw_medv4_diagram, VENSIM_RC

    with plt.rc_context(VENSIM_RC):
        diagram_fig = draw_medv4_diagram(figsize=(11, 6))
    return (diagram_fig,)


@app.cell
def _summary(Fatigue, Fitness, Performance, Signal, mo):
    """Summary tab: start/end/min/max per stock as a static table.
    (Parameter values aren't echoed here — the sidebar already shows them live.)"""
    _rows = [("Fitness", Fitness), ("Fatigue", Fatigue), ("Signal", Signal), ("Performance", Performance)]
    _lines = ["| Stock | Start | End | Min | Max |", "|---|--:|--:|--:|--:|"]
    for _name, _y in _rows:
        _lines.append(
            f"| {_name} | {_y[0]:.2f} | {_y[-1]:.2f} | {float(_y.min()):.2f} | {float(_y.max()):.2f} |"
        )
    state_panel = mo.md("\n".join(_lines))
    return (state_panel,)


@app.cell
def _outputs(diagram_fig, mo, state_panel, training_chart, traj_chart):
    """Tabbed main output area. Trajectories tab leads with the wide
    training-schedule bar spanning both columns, then the 2x2 stock panels."""
    mo.vstack(
        [
            mo.md("# rtSD Explorer — MEDv4 model for resistance training"),
            mo.md(
                "Three-stock fitness-fatigue ODE driven by a TRIMP forcing function. "
                "Set a scenario and drag the parameters in the sidebar; the panels recompute live. "
                "**Snapshot** a run to overlay it on later runs for comparison. "
                "*Defaults are illustrative, physiologically-grounded calibrated values "
                "(GET-PAID 2026-05-28) — not publication-grade estimates.*"
            ),
            mo.ui.tabs(
                {
                    "Trajectories": mo.vstack([training_chart, traj_chart]),
                    "Stock-and-flow": diagram_fig,
                    "Summary": state_panel,
                }
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
