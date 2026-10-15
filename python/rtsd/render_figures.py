#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "matplotlib"]
# ///
"""Render the rtSD Explorer's static showcase figures (PNG).

  rtsd-hero.png   1800x900  structure (stock-and-flow) + behavior (trajectories)
  rtsd-card.png   1200x630  behavior panel alone, sized for social link previews
                            (the two-panel composite's diagram is unreadable at
                            preview size, about 500 px wide)
  rtsd-tile.png   1600x900  behavior panel alone, for 16:9 project cards
  medv4_sd_preview.png      full-detail stock-and-flow diagram (python/rtsd/)

The trajectories come from `model.py` (the parity-tested Python model, gated
against the R reference by tests/parity/), never from a re-derived ODE. Styling
mirrors the explorer's Prism chart theme (`_THEME_PRISM` in rtsd.py): heavy
black L-axes, no grid, outward ticks, Arial with bold titles, thick lines, and
the explorer's stock colors. Lines carry direct labels instead of a legend box.

Usage (from the repo root):
    uv run --script python/rtsd/render_figures.py               # -> docs/figures/
    uv run --script python/rtsd/render_figures.py --out DIR
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from model import make_training_fn, scenario_rp, simulate
from sd_diagram import VENSIM_RC, draw_medv4_diagram

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DPI = 200

# Explorer defaults (rtsd.py `_ui_params` / `_ui_rp`), so the figure shows what
# a visitor gets on opening the explorer, except the program runs 10
# mesocycles (50 weeks) to fill the 52-week horizon.
PARAMS = dict(
    adaptation_rate=0.018,
    adaptation_delay=5.75,
    max_frac_rate=0.0077,
    Capacity=90.0,
    tau_fatigue=0.5,
    tau_signal=1.0,
    adl_trimp=19.0,
    Baseline=60.0,
)
ALPHA = 0.15
RP_PROGRAM = dict(
    n_mesocycles=10,
    accumulation_weeks=4,
    deload_weeks=1,
    mev_sets=8,
    mrv_sets=18,
    sessions_per_week=3,
    work_per_set=80.0,
    deload_fraction=0.5,
    mev_creep_per_cycle=0,
)
HORIZON = 52
DT = 1 / 7

# Same colors as the explorer's STOCK_COLORS (rtsd.py `_palette`)
STOCK_COLORS = {
    "Fitness": "#1565C0",
    "Fatigue": "#C62828",
    "Signal": "#F9A825",
    "Performance": "#2E7D32",
}


def _weekly_mean(y):
    """Centered 7-day moving average (7 daily steps), edge-corrected.

    At daily resolution each of the 3 weekly sessions spikes Fatigue, Signal
    and Performance, which buries the mesocycle pattern at figure size. The
    average shows the week-to-week build and deload; the figure says so in
    its subtitle.
    """
    k = np.ones(round(1 / DT))
    return np.convolve(y, k, mode="same") / np.convolve(np.ones_like(y), k, mode="same")


def run_trajectories():
    """Simulate the RP program; return time and per-stock series, each 7-day
    averaged then min-max normalized (the explorer overlay's normalization)."""
    grid = np.arange(round(HORIZON / DT) + 1) * DT
    sched = scenario_rp(grid, **RP_PROGRAM)
    t, traj = simulate(PARAMS, HORIZON, DT, make_training_fn(grid, sched), "linear")
    raw = {
        "Fitness": traj[:, 0],
        "Fatigue": traj[:, 1],
        "Signal": traj[:, 2],
        "Performance": traj[:, 0] - ALPHA * traj[:, 1],
    }
    norm = {}
    for name, y in raw.items():
        y = _weekly_mean(y)
        lo, hi = y.min(), y.max()
        norm[name] = (y - lo) / (hi - lo) if hi > lo else y * 0.0
    return t, norm


SUBTITLE = "7-day averages, each scaled 0 to 1"


def _spread(ys, min_gap):
    """Nudge label y-positions apart (keeping order) so none sit closer than
    min_gap; a minimal stand-in for a label-repel step."""
    order = np.argsort(ys)
    placed = np.array(ys, dtype=float)[order]
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + min_gap)
    overflow = placed[-1] - 1.04
    if overflow > 0:
        placed -= overflow
    out = np.empty_like(placed)
    out[order] = placed
    return out


def draw_trajectory(ax, t, norm, px, title=None, stocks=None):
    """Prism-styled normalized trajectories with direct end labels.

    `px` = points per CSS pixel at the figure's expected display size, so the
    theme's pixel values (axis 2.5, ticks 7, line 3, fonts 12/14/15) land at
    the same apparent size as in the explorer.
    """
    stocks = stocks or list(STOCK_COLORS)
    # Draw order: Fatigue and Signal at the back; Performance and Fitness on top
    z = {"Fatigue": 2, "Signal": 3, "Performance": 4, "Fitness": 5}
    lw = {"Fatigue": 2.4, "Signal": 2.4, "Performance": 3.0, "Fitness": 3.0}
    for name in stocks:
        ax.plot(t, norm[name], color=STOCK_COLORS[name], lw=lw[name] * px,
                solid_capstyle="round", zorder=z[name])

    # Direct labels at the right end, spread vertically to avoid collisions
    end_y = [float(norm[n][-1]) for n in stocks]
    label_y = _spread(end_y, min_gap=0.105)
    x_end = t[-1]
    for name, y in zip(stocks, label_y):
        ax.text(x_end + 1.2, y, name, color=STOCK_COLORS[name], va="center",
                ha="left", fontsize=13 * px, fontweight="bold", clip_on=False)

    ax.set_xlim(0, x_end)
    ax.set_ylim(-0.03, 1.05)
    ax.set_xticks([0, 13, 26, 39, 52])
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_yticklabels(["0", "0.5", "1"])
    ax.set_xlabel("Week", fontsize=14 * px, fontweight="bold", labelpad=4 * px)
    ax.set_ylabel("Normalized level", fontsize=14 * px, fontweight="bold",
                  labelpad=4 * px)
    if title:
        ax.set_title(title, loc="left", fontsize=15 * px, fontweight="bold",
                     pad=10 * px)

    # Prism look: L-axes only, offset from the data, outward ticks, no grid
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_linewidth(2.5 * px)
        ax.spines[side].set_position(("outward", 6 * px))
    ax.tick_params(direction="out", width=2 * px, length=7 * px,
                   labelsize=12 * px, color="black", labelcolor="black")
    ax.grid(False)


def _panel_title(fig, x, y, text, px, subtitle=None):
    fig.text(x, y, text, fontsize=15 * px, fontweight="bold", ha="left",
             va="top", color="black")
    if subtitle:
        fig.text(x, y - 15 * px * 1.55 / (fig.get_figheight() * 72), subtitle,
                 fontsize=12 * px, ha="left", va="top", color="#333333")


def render_composite(path, size_px, display_px, diagram_fontscale,
                     diagram_rect, traj_rect, right_title_x):
    """Two-panel figure: structure (left) + behavior (right).

    The rects are figure fractions [left, bottom, width, height]; the diagram
    keeps its aspect and is pinned to the top of its rect.
    """
    w, h = size_px[0] / DPI, size_px[1] / DPI
    px = (size_px[0] / display_px) * 72 / DPI
    t, norm = run_trajectories()
    with plt.rc_context({**VENSIM_RC, "font.family": "Arial"}):
        fig = plt.figure(figsize=(w, h), dpi=DPI)
        ax_d = fig.add_axes(diagram_rect)
        draw_medv4_diagram(ax=ax_d, title="", show_key=False,
                           fontscale=diagram_fontscale, detail=False)
        ax_d.set_anchor("N")
        ax_t = fig.add_axes(traj_rect)
        draw_trajectory(ax_t, t, norm, px)
        _panel_title(fig, 0.025, 0.95, "Structure: three stocks driven by training", px)
        _panel_title(fig, right_title_x, 0.95, "Behavior: a year of RP mesocycles", px,
                     subtitle=SUBTITLE)
        fig.savefig(path, dpi=DPI, facecolor="white")
        plt.close(fig)
    return path


def render_tile(path, size_px=(1600, 900), display_px=450):
    """Behavior panel alone, sized to read on a ~450 px wide project card."""
    w, h = size_px[0] / DPI, size_px[1] / DPI
    px = (size_px[0] / display_px) * 72 / DPI
    t, norm = run_trajectories()
    with plt.rc_context({"font.family": "Arial"}):
        fig = plt.figure(figsize=(w, h), dpi=DPI)
        ax = fig.add_axes([0.13, 0.19, 0.6, 0.56])
        draw_trajectory(ax, t, norm, px)
        _panel_title(fig, 0.04, 0.965, "rtSD: a year of RP training", px,
                     subtitle=SUBTITLE)
        fig.savefig(path, dpi=DPI, facecolor="white")
        plt.close(fig)
    return path


def render_diagram_preview(path):
    """Full-detail stock-and-flow diagram (what the explorer's tab shows)."""
    with plt.rc_context(VENSIM_RC):
        fig = draw_medv4_diagram(figsize=(11, 6.6))
        fig.savefig(path, dpi=150, facecolor="white")
        plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "figures",
                    help="output directory for hero, card and tile")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    written = [
        render_composite(args.out / "rtsd-hero.png", (1800, 900), 1000, 0.8,
                         diagram_rect=[0.0, 0.0, 0.55, 0.86],
                         traj_rect=[0.62, 0.17, 0.27, 0.62], right_title_x=0.565),
        render_tile(args.out / "rtsd-card.png", size_px=(1200, 630), display_px=500),
        render_tile(args.out / "rtsd-tile.png"),
        render_diagram_preview(HERE / "medv4_sd_preview.png"),
    ]
    for p in written:
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
