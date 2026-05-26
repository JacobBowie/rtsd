"""rtSD Explorer — MEDv4 fitness-fatigue-signal explorer (marimo notebook).

Reactive Python port of the Shiny rtSD Explorer app. Same model, same RP program
generator, same controls — but built on marimo, which means:

  - Single file, no server needed
  - Reactive: change a slider, downstream cells recompute automatically
  - Static export to WASM (Pyodide) for free in-browser hosting via
        `marimo export html-wasm rtsd.py -o rtsd.html`

Run interactively:

    python -m marimo edit python/rtsd/rtsd.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _imports():
    import numpy as np
    import matplotlib.pyplot as plt
    import marimo as mo

    return mo, np, plt


@app.cell
def _intro(mo):
    mo.md(r"""
    # rtSD Explorer — MEDv4 model for resistance training

    Three-stock fitness-fatigue ODE driven by a TRIMP forcing function.
    Pick a training scenario, drag the parameters, watch the dynamics.

    - **Fitness** — long-run adaptation
    - **Fatigue** — short-timescale recovery debt (decays with τ_fatigue)
    - **Signal** — secondary mediator, gates adaptation
    - **Performance** = Fitness − α · Fatigue
    """)
    return


@app.cell
def _diagram(plt):
    """Vensim-style stock-and-flow diagram of MEDv4 (rendered live)."""
    from sd_diagram import draw_medv4_diagram, VENSIM_RC
    with plt.rc_context(VENSIM_RC):
        _fig_sd = draw_medv4_diagram(figsize=(11, 6))
    _fig_sd
    return


@app.cell
def _model(np):
    """MEDv4 ODE right-hand side and Euler integrator.

    Linear and quadratic variants matching the R port. Euler with dt=0.0625
    matches the Vensim/PySD reference.
    """

    def med_rhs(state, t, params, training_fn, variant):
        Fitness, Fatigue, Signal = state
        T = training_fn(t)
        eff_T = T + params["adl_trimp"]

        if variant == "linear":
            adaptation = params["adaptation_rate"] * Signal / params["adaptation_delay"]
            signal_loss = Signal / params["tau_signal"]
        else:
            adaptation = (params["adaptation_rate"] * Signal) ** 2 / params["adaptation_delay"]
            signal_loss = Signal ** 2 / params["tau_signal"]

        frac_atrophy = params["max_frac_rate"] * (Fitness / params["Capacity"])
        atrophy = abs(Fitness * frac_atrophy)
        recovery = Fatigue / params["tau_fatigue"]

        dFitness = adaptation - atrophy
        dFatigue = eff_T - recovery
        dSignal = eff_T - adaptation - signal_loss
        return np.array([dFitness, dFatigue, dSignal])

    def simulate(params, horizon, dt, training_fn, variant):
        grid = np.arange(0.0, horizon + dt, dt)
        n = len(grid)
        out = np.zeros((n, 3))
        out[0] = [params["Baseline"], 0.0, 0.0]
        for i in range(1, n):
            t = grid[i - 1]
            d = med_rhs(out[i - 1], t, params, training_fn, variant)
            out[i] = out[i - 1] + dt * d
        return grid, out

    return (simulate,)


@app.cell
def _scenarios(np):
    """Training-scenario builders.

    Each returns a `training_fn(t) -> TRIMP`. `pulse_from_events` builds an
    arbitrary event-driven training program, matching `R/training_schedule.R`.
    """

    def pulse_from_events(grid, event_times, event_heights, width=1 / 7):
        """Vectorized rectangular-pulse forcing on a grid."""
        schedule = np.zeros_like(grid)
        for t_i, h_i in zip(event_times, event_heights):
            mask = (grid >= t_i - 1e-9) & (grid < t_i + width - 1e-9)
            schedule[mask] += h_i
        return schedule

    def make_training_fn(grid, schedule):
        """Step-function interpolator (constant between samples)."""
        def f(t):
            i = np.searchsorted(grid, t, side="right") - 1
            i = max(0, min(i, len(grid) - 1))
            return schedule[i]
        return f

    def scenario_standard(grid, sessions_per_week, vol, n_weeks, start_week=1):
        # Match R/Vensim convention: 1-indexed weeks, first session at t=start_week,
        # training spans weeks [start_week, start_week + n_weeks - 1].
        times = []
        heights = []
        for w in range(int(n_weeks)):
            for s in range(int(sessions_per_week)):
                times.append(start_week + w + s / sessions_per_week)
                heights.append(vol)
        times = np.array(times)
        heights = np.array(heights)
        # Discard sessions past the grid horizon
        mask = times <= grid[-1]
        return pulse_from_events(grid, times[mask], heights[mask])

    def scenario_detraining(grid, train_weeks, sessions_per_week, vol):
        return scenario_standard(grid, sessions_per_week, vol, n_weeks=train_weeks)

    def scenario_untrained(grid):
        return np.zeros_like(grid)

    def program_rp_macro(
        start_week=1,
        n_mesocycles=3,
        accumulation_weeks=4,
        deload_weeks=1,
        mev_sets=8,
        mrv_sets=18,
        sessions_per_week=3,
        work_per_set=80.0,
        deload_fraction=0.5,
        mev_creep_per_cycle=0,
    ):
        """Renaissance Periodization macrocycle.

        Linear MEV→MRV ramp across accumulation weeks, then deload at
        `deload_fraction` × MEV. Mesocycles chain end-to-end with optional
        MEV creep across cycles to reflect rising work tolerance.
        """
        meso_len = accumulation_weeks + deload_weeks
        times = []
        heights = []
        cur_start = start_week
        for m in range(n_mesocycles):
            creep = m * mev_creep_per_cycle
            mev = mev_sets + creep
            mrv = mrv_sets + creep
            # Build weekly volume profile for this mesocycle
            ramp = np.linspace(mev, mrv, accumulation_weeks)
            deload = np.full(deload_weeks, mev * deload_fraction)
            weekly_sets = np.concatenate([ramp, deload])
            for w_idx, sets_this_week in enumerate(weekly_sets):
                sets_per_session = sets_this_week / sessions_per_week
                for s in range(int(sessions_per_week)):
                    times.append(
                        (cur_start - 1) + w_idx + s / sessions_per_week
                    )
                    heights.append(sets_per_session * work_per_set)
            cur_start += meso_len
        return np.array(times), np.array(heights)

    def scenario_rp(grid, **kwargs):
        times, heights = program_rp_macro(**kwargs)
        mask = times <= grid[-1]
        return pulse_from_events(grid, times[mask], heights[mask])

    return (
        make_training_fn,
        scenario_detraining,
        scenario_rp,
        scenario_standard,
        scenario_untrained,
    )


@app.cell
def _ui_controls(mo):
    """Simulation controls. Last expression renders the panel."""
    variant = mo.ui.dropdown(
        options={"Linear (winning)": "linear", "Quadratic (original)": "quadratic"},
        value="Linear (winning)",
        label="ODE variant",
    )
    scenario = mo.ui.dropdown(
        options={
            "Standard weekly": "standard",
            "Detraining": "detraining",
            "Untrained (ADL only)": "untrained",
            "Renaissance Periodization": "rp",
        },
        value="Standard weekly",
        label="Training scenario",
    )
    horizon = mo.ui.slider(4, 200, value=48, step=1, label="Horizon (weeks)")
    dt = mo.ui.dropdown(
        options=["0.0625", "0.125", "0.25", "0.5"],
        value="0.0625",
        label="Integration dt (weeks)",
    )
    sessions_per_week = mo.ui.slider(1, 7, value=3, step=1, label="Sessions / week")
    vol = mo.ui.slider(0, 500, value=81, step=1, label="Volume / session (TRIMP)")
    detrain_start = mo.ui.slider(4, 100, value=24, step=1, label="Detrain after (wk)")
    mo.vstack([
        mo.md("### Simulation"),
        variant, scenario, horizon, dt,
        sessions_per_week, vol, detrain_start,
    ])
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
    """Renaissance Periodization controls — active when scenario = 'rp'."""
    rp_mev = mo.ui.slider(2, 30, value=8, step=1, label="MEV (sets/wk)")
    rp_mrv = mo.ui.slider(4, 40, value=18, step=1, label="MRV (sets/wk)")
    rp_accum = mo.ui.slider(2, 8, value=4, step=1, label="Accumulation weeks")
    rp_deload = mo.ui.slider(0, 3, value=1, step=1, label="Deload weeks")
    rp_n_meso = mo.ui.slider(1, 8, value=3, step=1, label="# Mesocycles")
    rp_work_per_set = mo.ui.slider(10, 300, value=80, step=5, label="Work / set (TRIMP)")
    rp_deload_frac = mo.ui.slider(
        0.2, 1.0, value=0.5, step=0.05, label="Deload fraction of MEV"
    )
    rp_mev_creep = mo.ui.slider(0, 6, value=0, step=1, label="MEV creep / mesocycle")
    mo.vstack([
        mo.md("### Renaissance Periodization *(used when scenario = RP)*"),
        rp_mev, rp_mrv, rp_accum, rp_deload, rp_n_meso,
        rp_work_per_set, rp_deload_frac, rp_mev_creep,
    ])
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
    """ODE parameters."""
    import math
    adaptation_rate = mo.ui.slider(0.001, 0.05, value=0.02, step=0.001, label="adaptation_rate")
    adaptation_delay = mo.ui.slider(1.0, 20.0, value=5.0, step=0.5, label="adaptation_delay (wk)")
    max_frac_rate = mo.ui.slider(0.001, 0.1, value=0.020, step=0.001, label="max_frac_rate")
    Capacity = mo.ui.slider(20, 400, value=200, step=5, label="Capacity")
    tau_fatigue = mo.ui.slider(0.1, 5.0, value=7 / math.exp(2), step=0.05, label="tau_fatigue (wk)")
    tau_signal = mo.ui.slider(1.0, 60.0, value=14.0, step=0.5, label="tau_signal (wk)")
    adl_trimp = mo.ui.slider(0, 60, value=19, step=1, label="adl_trimp")
    alpha = mo.ui.slider(0.0, 2.0, value=1.0, step=0.05, label="alpha (Performance)")
    Baseline = mo.ui.slider(1.0, 80.0, value=12.145, step=0.5, label="Baseline Fitness")
    mo.vstack([
        mo.md("### Adaptation & atrophy"),
        adaptation_rate, adaptation_delay, max_frac_rate, Capacity,
        mo.md("### Time constants & baseline"),
        tau_fatigue, tau_signal, adl_trimp, alpha, Baseline,
    ])
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
    scenario_rp,
    scenario_standard,
    scenario_untrained,
    sessions_per_week,
    vol,
):
    """Reactive training-schedule construction."""
    dt_v = float(dt.value)
    grid = np.arange(0.0, horizon.value + dt_v, dt_v)

    if scenario.value == "standard":
        sched = scenario_standard(grid, sessions_per_week.value, vol.value, horizon.value)
    elif scenario.value == "detraining":
        sched = scenario_detraining(
            grid, detrain_start.value, sessions_per_week.value, vol.value
        )
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
def _plot_traj(Fatigue, Fitness, Performance, Signal, grid_t, plt):
    """Four-panel trajectory plot."""
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    _series = [
        ("Fitness", Fitness, "#1565C0"),
        ("Fatigue", Fatigue, "#C62828"),
        ("Signal", Signal, "#F9A825"),
        ("Performance", Performance, "#2E7D32"),
    ]
    for _ax, (_name, _y, _c) in zip(axes.flat, _series):
        _ax.plot(grid_t, _y, color=_c, linewidth=2)
        _ax.set_title(_name, fontweight="bold")
        _ax.set_xlabel("Time (weeks)")
        _ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig  # last expression — renders the figure


@app.cell
def _plot_training(
    grid_t,
    plt,
    rp_accum,
    rp_deload,
    rp_mev,
    rp_mrv,
    rp_n_meso,
    scenario,
    sched,
    sessions_per_week,
):
    """Training schedule barplot."""
    fig2, ax2 = plt.subplots(figsize=(11, 2.6))
    width = grid_t[1] - grid_t[0] if len(grid_t) > 1 else 0.0625
    ax2.bar(grid_t, sched, width=width, color="#1565C0", edgecolor="none")
    ax2.set_xlabel("Time (weeks)")
    ax2.set_ylabel("TRIMP / step")

    if scenario.value == "rp":
        title = (
            f"RP — {rp_n_meso.value} meso × ({rp_accum.value} accum + "
            f"{rp_deload.value} deload) wk · MEV {rp_mev.value} → "
            f"MRV {rp_mrv.value} sets/wk · {sessions_per_week.value} sessions/wk"
        )
    else:
        title = f"Scenario: {scenario.value} — {sessions_per_week.value} sessions/wk"
    ax2.set_title(title)
    ax2.grid(True, alpha=0.3, axis="y")
    fig2.tight_layout()
    fig2  # last expression — renders the figure


@app.cell
def _summary(Fatigue, Fitness, Performance, Signal, mo):
    """Start/end/min/max summary."""
    import numpy as _np
    _rows = [
        ("Fitness",     Fitness),
        ("Fatigue",     Fatigue),
        ("Signal",      Signal),
        ("Performance", Performance),
    ]
    _md = ["| Stock | Start | End | Min | Max |", "|---|---:|---:|---:|---:|"]
    for _name, _y in _rows:
        _md.append(
            f"| {_name} | {_y[0]:.2f} | {_y[-1]:.2f} | {_np.min(_y):.2f} | {_np.max(_y):.2f} |"
        )
    mo.md("\n".join(_md))
    return


if __name__ == "__main__":
    app.run()
