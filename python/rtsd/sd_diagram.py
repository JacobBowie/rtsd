"""Vensim-style stock-and-flow diagrammer for MEDv4.

Hand-crafted matplotlib renderer that captures Vensim's visual grammar:

  - **Stocks** as bordered rectangles with bold centered labels
  - **Flows** as thick pipes (line) with a circular valve in the middle
    and a bowtie marker showing flow direction
  - **Clouds** for sources/sinks (multi-bump outline)
  - **Auxiliaries / parameters** as plain text (no shape)
  - **Causal links** as thin curved arrows with optional ± polarity

Outputs a matplotlib Figure suitable for marimo cell rendering OR for SVG
export via `fig.savefig(path, format='svg', bbox_inches='tight')`.

Designed for the MEDv4 three-stock fitness-fatigue model. Layout is
hand-positioned for readability; redo `draw_medv4_diagram()` if the model
structure changes (cell-flow grammar is generic enough to repurpose).
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import (
    Rectangle, Circle, FancyArrowPatch, PathPatch, Polygon,
)
from matplotlib.path import Path


# ---------------------------------------------------------------------------
# Vensim-style aesthetic primitives
# ---------------------------------------------------------------------------

VENSIM_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10,
    "axes.linewidth": 0,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
}

# Vensim's default "blue/black on white" palette
COLOR_STOCK_FILL  = "#FFFFFF"
COLOR_STOCK_EDGE  = "#1B1B1B"
COLOR_FLOW        = "#1B1B1B"
COLOR_VALVE_FILL  = "#FFFFFF"
COLOR_CLOUD       = "#7A7A7A"
COLOR_PARAM       = "#3A3A3A"
COLOR_CAUSAL_POS  = "#1565C0"   # blue for + polarity
COLOR_CAUSAL_NEG  = "#C62828"   # red for − polarity
COLOR_CAUSAL_NONE = "#5A5A5A"


def draw_stock(ax, x, y, width, height, label, fontsize=11):
    """Vensim-style stock: white rectangle, thin black border, bold label."""
    rect = Rectangle(
        (x - width / 2, y - height / 2), width, height,
        linewidth=1.5, edgecolor=COLOR_STOCK_EDGE,
        facecolor=COLOR_STOCK_FILL, zorder=3,
    )
    ax.add_patch(rect)
    ax.text(
        x, y, label, ha="center", va="center",
        fontsize=fontsize, fontweight="bold", color=COLOR_STOCK_EDGE,
        zorder=4,
    )


def draw_cloud(ax, x, y, scale=0.6):
    """Vensim cloud — multi-circle bumpy outline. Used for sources / sinks."""
    # Five overlapping circles, sized to be unmistakably "cloud" not "blob"
    blobs = [
        (-0.55, -0.10, 0.40),
        (-0.20, +0.20, 0.45),
        (+0.20, +0.25, 0.42),
        (+0.55, +0.05, 0.40),
        (+0.30, -0.20, 0.38),
        (-0.10, -0.25, 0.42),
    ]
    for dx, dy, r in blobs:
        c = Circle(
            (x + dx * scale, y + dy * scale), r * scale,
            linewidth=1.0, edgecolor=COLOR_CLOUD, facecolor="white", zorder=2,
        )
        ax.add_patch(c)


def draw_flow(ax, src_xy, dst_xy, label=None, valve_radius=0.16,
              arrow_size=0.10, label_offset=(0, 0.30)):
    """Vensim flow: thick pipe from src to dst with a valve+bowtie in middle.

    src and dst can be (x, y) of any anchor (typically a cloud center or a
    stock edge). The valve sits at the midpoint; flow direction is implied
    by an arrowhead on the dst side and the bowtie inside the valve.
    """
    src = np.array(src_xy, dtype=float)
    dst = np.array(dst_xy, dtype=float)
    mid = (src + dst) / 2
    direction = dst - src
    length = np.linalg.norm(direction)
    if length < 1e-6:
        return
    unit = direction / length
    # Pipe to and from valve
    valve_in_anchor = mid - unit * valve_radius
    valve_out_anchor = mid + unit * valve_radius

    # Inbound pipe (no arrow at this end — that's the valve side)
    ax.plot(
        [src[0], valve_in_anchor[0]],
        [src[1], valve_in_anchor[1]],
        color=COLOR_FLOW, linewidth=3.0, solid_capstyle="butt", zorder=2,
    )
    # Outbound pipe — arrowhead at dst
    arrow = FancyArrowPatch(
        valve_out_anchor, dst,
        arrowstyle=f"-|>,head_length={arrow_size*8},head_width={arrow_size*5}",
        color=COLOR_FLOW, linewidth=3.0, mutation_scale=10, zorder=2,
        shrinkA=0, shrinkB=0,
    )
    ax.add_patch(arrow)

    # Valve: white circle with bowtie inside
    valve = Circle(
        mid, valve_radius, linewidth=1.5, edgecolor=COLOR_FLOW,
        facecolor=COLOR_VALVE_FILL, zorder=4,
    )
    ax.add_patch(valve)

    # Bowtie/hourglass inside valve, oriented along flow direction.
    # Two triangles that meet tip-to-tip at `mid`, bases perpendicular to flow.
    perp = np.array([-unit[1], unit[0]])
    bow_w = valve_radius * 0.65   # half-length along flow
    bow_h = valve_radius * 0.55   # half-height of base
    base_left  = mid - unit * bow_w
    base_right = mid + unit * bow_w
    tri_left = Polygon(
        [base_left + perp * bow_h, base_left - perp * bow_h, mid],
        closed=True, linewidth=0,
        edgecolor=COLOR_FLOW, facecolor=COLOR_FLOW, zorder=5,
    )
    tri_right = Polygon(
        [base_right + perp * bow_h, base_right - perp * bow_h, mid],
        closed=True, linewidth=0,
        edgecolor=COLOR_FLOW, facecolor=COLOR_FLOW, zorder=5,
    )
    ax.add_patch(tri_left)
    ax.add_patch(tri_right)

    if label is not None:
        ax.text(
            mid[0] + label_offset[0], mid[1] + label_offset[1], label,
            ha="center", va="center", fontsize=10, fontweight="bold",
            color=COLOR_FLOW, zorder=6,
            bbox=dict(boxstyle="square,pad=0.15", facecolor="white",
                      edgecolor="none", alpha=0.95),
        )


def draw_param(ax, x, y, label, fontsize=10):
    """Vensim auxiliary / parameter: plain italic-ish text, no shape."""
    ax.text(
        x, y, label, ha="center", va="center",
        fontsize=fontsize, fontstyle="italic", color=COLOR_PARAM, zorder=4,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                  edgecolor="none", alpha=0.85),
    )


def draw_causal(ax, src_xy, dst_xy, polarity=None, curvature=0.20):
    """Vensim causal-link arrow: thin curved Bézier with optional ± label."""
    color = {
        "+": COLOR_CAUSAL_POS,
        "-": COLOR_CAUSAL_NEG,
    }.get(polarity, COLOR_CAUSAL_NONE)
    arrow = FancyArrowPatch(
        src_xy, dst_xy,
        connectionstyle=f"arc3,rad={curvature}",
        arrowstyle="-|>,head_length=6,head_width=4",
        color=color, linewidth=1.2, alpha=0.85, zorder=1,
    )
    ax.add_patch(arrow)
    if polarity in ("+", "-"):
        # Place the polarity label near the arrowhead
        sx, sy = src_xy
        dx, dy = dst_xy
        # 80% along the curve toward dst
        lx = sx + 0.85 * (dx - sx)
        ly = sy + 0.85 * (dy - sy)
        # Nudge perpendicular for readability
        perp = np.array([-(dy - sy), (dx - sx)])
        norm = np.linalg.norm(perp)
        if norm > 1e-6:
            perp = perp / norm
        lx += perp[0] * 0.18
        ly += perp[1] * 0.18
        ax.text(
            lx, ly, polarity, ha="center", va="center",
            fontsize=12, fontweight="bold", color=color, zorder=5,
        )


# ---------------------------------------------------------------------------
# MEDv4-specific layout
# ---------------------------------------------------------------------------


def draw_medv4_diagram(ax=None, figsize=(13, 8), title=None):
    """Render the MEDv4 stock-and-flow diagram in Vensim aesthetic.

    Three stocks (Fitness, Fatigue, Signal) arranged left-to-right with
    flow pipes, clouds for TRIMP source and sinks, and causal links from
    parameters to flows.

    Returns the Figure object.
    """
    if ax is None:
        with plt.rc_context(VENSIM_RC):
            fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()
        for k, v in VENSIM_RC.items():
            plt.rcParams[k] = v

    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # ---- Layout (left → right, three horizontal lanes) ------------------
    # Top lane: TRIMP_src(L) → effective_TRIMP → Fatigue → recovery → sink(R)
    # Mid lane: TRIMP_src(L) → trimp_in_S → Signal → adaptation → Fitness → atrophy → sink(R)
    # Bottom lane: signal_loss flows downward from Signal to a sink
    stock_w, stock_h = 1.9, 0.95

    # Stocks
    fatigue_pos = (5.0, 7.0)
    signal_pos  = (4.5, 3.5)
    fitness_pos = (10.0, 3.5)

    # Source / sink clouds
    cloud_T_top    = (1.2, 7.0)        # TRIMP source for Fatigue
    cloud_T_mid    = (1.2, 3.5)        # TRIMP source for Signal
    cloud_recov    = (8.5, 7.0)        # Fatigue → recovery sink
    cloud_sigloss  = (4.5, 0.7)        # Signal → signal_loss sink
    cloud_atrophy  = (13.0, 3.5)       # Fitness → atrophy sink

    # Edge helpers
    def left_edge(p):   return (p[0] - stock_w / 2, p[1])
    def right_edge(p):  return (p[0] + stock_w / 2, p[1])
    def top_edge(p):    return (p[0], p[1] + stock_h / 2)
    def bottom_edge(p): return (p[0], p[1] - stock_h / 2)

    # ---- Source clouds --------------------------------------------------
    draw_cloud(ax, *cloud_T_top, scale=0.55)
    draw_cloud(ax, *cloud_T_mid, scale=0.55)
    # Single shared "TRIMP" annotation between the two source clouds
    ax.text(cloud_T_top[0] - 0.3, (cloud_T_top[1] + cloud_T_mid[1]) / 2,
            "TRIMP\nforcing", ha="center", va="center",
            fontsize=10, fontweight="bold", color=COLOR_PARAM)

    # ---- Top lane: Fatigue ---------------------------------------------
    draw_flow(ax, cloud_T_top, left_edge(fatigue_pos),
              label="effective\nTRIMP", label_offset=(0, 0.65))
    draw_stock(ax, *fatigue_pos, stock_w, stock_h, "Fatigue")
    draw_cloud(ax, *cloud_recov, scale=0.55)
    draw_flow(ax, right_edge(fatigue_pos), cloud_recov,
              label="recovery", label_offset=(0, 0.55))

    # ---- Mid lane: Signal → adaptation → Fitness → atrophy --------------
    draw_flow(ax, cloud_T_mid, left_edge(signal_pos), label=None)
    draw_stock(ax, *signal_pos, stock_w, stock_h, "Signal")
    draw_flow(ax, right_edge(signal_pos), left_edge(fitness_pos),
              label="adaptation", label_offset=(0, 0.55))
    draw_stock(ax, *fitness_pos, stock_w, stock_h, "Fitness")
    draw_cloud(ax, *cloud_atrophy, scale=0.55)
    draw_flow(ax, right_edge(fitness_pos), cloud_atrophy,
              label="atrophy", label_offset=(0, 0.55))

    # ---- Signal-loss: Signal → sink (downward) --------------------------
    draw_cloud(ax, *cloud_sigloss, scale=0.55)
    draw_flow(ax, bottom_edge(signal_pos), cloud_sigloss,
              label="signal\nloss", label_offset=(0.85, 0))

    # ---- Parameters (placed BELOW their valves so they don't collide
    #      with the flow-name labels above) -------------------------------
    draw_param(ax, 2.6, 5.6,  "adl_trimp")        # influences eff_TRIMP
    draw_param(ax, 7.5, 6.4,  "tau_fatigue")      # → recovery (top lane)
    draw_param(ax, 6.0, 1.7,  "tau_signal")       # → signal_loss
    draw_param(ax, 7.0, 2.7,  "adaptation_rate")  # → adaptation valve
    draw_param(ax, 8.4, 2.7,  "adaptation_delay") # → adaptation valve
    draw_param(ax, 11.6, 2.7, "max_frac_rate")    # → atrophy valve
    draw_param(ax, 12.7, 2.7, "Capacity")         # → atrophy valve

    # ---- Causal links — minimal set, only the key dependencies ---------
    adapt_valve = ((signal_pos[0] + stock_w/2 + fitness_pos[0] - stock_w/2) / 2,
                   signal_pos[1])
    atrophy_valve = ((fitness_pos[0] + stock_w/2 + cloud_atrophy[0]) / 2,
                     fitness_pos[1])
    recov_valve = ((fatigue_pos[0] + stock_w/2 + cloud_recov[0]) / 2,
                   fatigue_pos[1])
    sigloss_valve = (signal_pos[0],
                     (signal_pos[1] - stock_h/2 + cloud_sigloss[1]) / 2)
    eff_trimp_valve = ((cloud_T_top[0] + fatigue_pos[0] - stock_w/2) / 2,
                       cloud_T_top[1])

    # Signal → adaptation valve  (main coupling that gates Fitness growth)
    draw_causal(ax, top_edge(signal_pos), (adapt_valve[0], adapt_valve[1] + 0.18),
                polarity="+", curvature=0.35)
    # adaptation_rate (param below valve) → adaptation valve
    draw_causal(ax, (7.0, 2.85), (adapt_valve[0] - 0.10, adapt_valve[1] - 0.18),
                polarity="+", curvature=-0.20)
    # adaptation_delay → adaptation valve  (− because larger delay slows adaptation)
    draw_causal(ax, (8.4, 2.85), (adapt_valve[0] + 0.10, adapt_valve[1] - 0.18),
                polarity="-", curvature=0.20)
    # Fitness → atrophy
    draw_causal(ax, top_edge(fitness_pos), (atrophy_valve[0], atrophy_valve[1] + 0.18),
                polarity="+", curvature=0.30)
    # max_frac_rate → atrophy (+)
    draw_causal(ax, (11.6, 2.85), (atrophy_valve[0] - 0.10, atrophy_valve[1] - 0.18),
                polarity="+", curvature=-0.20)
    # Capacity → atrophy (− because larger capacity → smaller fractional rate)
    draw_causal(ax, (12.7, 2.85), (atrophy_valve[0] + 0.10, atrophy_valve[1] - 0.18),
                polarity="-", curvature=0.20)
    # Fatigue → recovery
    draw_causal(ax, top_edge(fatigue_pos), (recov_valve[0] - 0.05, recov_valve[1] + 0.18),
                polarity="+", curvature=0.25)
    # tau_fatigue → recovery (− because larger tau → slower recovery)
    draw_causal(ax, (7.5, 6.55), (recov_valve[0] + 0.05, recov_valve[1] - 0.18),
                polarity="-", curvature=-0.20)
    # tau_signal → signal_loss (−)
    draw_causal(ax, (6.0, 1.85), (sigloss_valve[0] + 0.18, sigloss_valve[1]),
                polarity="-", curvature=0.25)
    # adl_trimp → effective_TRIMP flow
    draw_causal(ax, (2.6, 5.45), (eff_trimp_valve[0], eff_trimp_valve[1] + 0.18),
                polarity="+", curvature=-0.30)

    # ---- Title ----------------------------------------------------------
    if title is None:
        title = "MEDv4 stock-and-flow"
    ax.text(
        7.0, 8.55, title, ha="center", va="center",
        fontsize=14, fontweight="bold", color=COLOR_STOCK_EDGE,
    )

    # ---- Legend ---------------------------------------------------------
    ax.text(
        0.4, 0.15,
        "thick pipe + valve = stock-and-flow    "
        "thin arrow = information link    "
        "blue + = positive influence    red − = negative influence",
        ha="left", va="center", fontsize=8, color="#5A5A5A", style="italic",
    )

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# CLI: produce a static SVG for embedding in the Quarto site
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "medv4_sd.svg"
    with plt.rc_context(VENSIM_RC):
        fig = draw_medv4_diagram()
        fig.savefig(out, format="svg", bbox_inches="tight",
                    facecolor="white", dpi=150)
    print(f"Wrote {out}")
