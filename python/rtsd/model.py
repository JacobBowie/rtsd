"""rtSD MEDv4 model — pure Python source of truth.

The ODE right-hand side, the fixed-step Euler integrator, and the
training-scenario builders, factored out of the marimo notebook so they are
importable by both the notebook (for `marimo edit`/`run`) and the parity test
suite (`tests/parity/`).

Euler at dt=0.0625 matches the R reference (`R/simulate.R`, which defaults to
`deSolve::ode(method="euler")`) and the Vensim/PySD oracle. This module is the
gated Python counterpart to the R model; `tests/parity` proves the two agree.

WASM note: `marimo export html-wasm` does NOT bundle local module imports, so
the notebook cannot `from model import ...` and remain WASM-exportable as-is.
The deploy build step inlines this module into a self-contained notebook before
export. See CLAUDE.md / the parity-gate plan. Keep this module marimo-free.
"""

import numpy as np


def default_params():
    """Parity-reference parameter set (matches R `corrected_params()`).

    NOTE: this is NOT the explorer's UI defaults. The marimo notebook builds its
    params directly from slider values (the GET-PAID-reworked regime: Capacity=90,
    Baseline=60, max_frac_rate=0.0077, …) and never calls this function. This set
    exists as the R-parity reference; `tests/parity/cases.json` carries its own
    copy. Keys use the Python convention — note `max_frac_rate` here vs R's
    `maximal_fractional_rate` (the parity harness maps between them).
    """
    return dict(
        adaptation_rate=0.02,
        adaptation_delay=5.0,
        max_frac_rate=0.020,
        Capacity=200.0,
        tau_fatigue=7.0 / np.exp(2.0),
        tau_signal=14.0,
        adl_trimp=19.0,
        Baseline=12.145,
    )


def med_rhs(state, t, params, training_fn, variant):
    """MEDv4 three-stock RHS. `variant` in {"quadratic", "linear"}."""
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
    """Fixed-step explicit Euler forward simulation.

    Returns (grid, out) where grid is the time vector and out is an
    (n, 3) array of [Fitness, Fatigue, Signal].
    """
    # seq-equivalent grid (k*dt, lands exactly on horizon): matches R
    # simulate.R's seq(0, horizon, by=dt) and avoids np.arange's phantom
    # trailing step past horizon when dt doesn't divide horizon evenly (e.g.
    # the daily 1/7 default). rtsd.py:_build_training mirrors this.
    grid = np.arange(round(horizon / dt) + 1) * dt
    n = len(grid)
    out = np.zeros((n, 3))
    out[0] = [params["Baseline"], 0.0, 0.0]
    for i in range(1, n):
        t = grid[i - 1]
        d = med_rhs(out[i - 1], t, params, training_fn, variant)
        out[i] = out[i - 1] + dt * d
    return grid, out


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


def scenario_high_freq(grid, sessions_per_week=3, vol=81, n_weeks=48):
    """High-frequency preset. Thin wrapper over scenario_standard, matching
    R `scenario_high_freq()`."""
    return scenario_standard(grid, sessions_per_week, vol, n_weeks)


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

    Linear MEV->MRV ramp across accumulation weeks, then deload at
    `deload_fraction` x MEV. Mesocycles chain end-to-end with optional
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
                times.append((cur_start - 1) + w_idx + s / sessions_per_week)
                heights.append(sets_per_session * work_per_set)
        cur_start += meso_len
    return np.array(times), np.array(heights)


def scenario_rp(grid, **kwargs):
    times, heights = program_rp_macro(**kwargs)
    mask = times <= grid[-1]
    return pulse_from_events(grid, times[mask], heights[mask])
