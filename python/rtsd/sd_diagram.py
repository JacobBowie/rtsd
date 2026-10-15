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
              arrow_size=0.10, label_offset=(0, 0.30), fontsize=10):
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
            ha="center", va="center", fontsize=fontsize, fontweight="bold",
            color=COLOR_FLOW, zorder=6,
            bbox=dict(boxstyle="square,pad=0.15", facecolor="white",
                      edgecolor="none", alpha=0.95),
        )


def draw_param(ax, x, y, label, fontsize=10):
    """Vensim constant / parameter: plain italic text, no shape."""
    ax.text(
        x, y, label, ha="center", va="center",
        fontsize=fontsize, fontstyle="italic", color=COLOR_PARAM, zorder=4,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                  edgecolor="none", alpha=0.85),
    )


def draw_aux(ax, x, y, label, fontsize=10):
    """Vensim auxiliary (a computed variable, not a constant): upright dark
    text, no shape. Distinguished from draw_param's italic constants."""
    ax.text(
        x, y, label, ha="center", va="center",
        fontsize=fontsize, fontweight="bold", color=COLOR_STOCK_EDGE, zorder=4,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                  edgecolor="none", alpha=0.9),
    )


def _toward(src_xy, dst_xy, gap):
    """Point `gap` short of dst along the src→dst line, so a causal arrow ends
    at a valve's rim (gap = valve radius + clearance) instead of its center."""
    src = np.asarray(src_xy, dtype=float)
    dst = np.asarray(dst_xy, dtype=float)
    d = dst - src
    n = np.linalg.norm(d)
    return tuple(dst - d / n * gap) if n > 1e-9 else tuple(dst)


def draw_causal(ax, src_xy, dst_xy, polarity=None, curvature=0.20, nudge=0.18,
                fontsize=12, show_sign=True):
    """Vensim causal-link arrow: thin curved Bézier with optional ± label.
    `nudge` offsets the ± label perpendicular to the link; flip its sign to
    move the label to the other side (e.g. off a flow pipe). `show_sign=False`
    keeps the polarity color but omits the ± glyph."""
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
    if show_sign and polarity in ("+", "-"):
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
        lx += perp[0] * nudge
        ly += perp[1] * nudge
        ax.text(
            lx, ly, polarity, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=color, zorder=5,
        )


# ---------------------------------------------------------------------------
# MEDv4-specific layout
# ---------------------------------------------------------------------------


def draw_medv4_diagram(ax=None, figsize=(13, 8), title=None, show_key=True,
                       fontscale=1.0, detail=True):
    """Render the MEDv4 stock-and-flow diagram in Vensim aesthetic.

    Three stocks (Fatigue, Signal, Fitness) with flow pipes, clouds for
    sources and sinks, and a causal link for every term in model.med_rhs:

      effective TRIMP = training + adl_trimp      (inflow to Fatigue AND Signal)
      recovery        = Fatigue / tau_fatigue
      adaptation      = f(Signal, adaptation_rate, adaptation_delay)
      signal loss     = f(Signal, tau_signal)
      atrophy         = f(Fitness, max_frac_rate, Capacity)
      Performance     = Fitness - alpha * Fatigue  (readout, not a stock)

    Pass `title=""` to suppress the title and `show_key=False` to drop the
    notation key (e.g. when composing into a larger figure). For a small
    rendering (a page hero), `detail=False` drops the parameters and their
    links so `fontscale` can enlarge the remaining labels without collisions.

    Returns the Figure object.
    """
    own_fig = ax is None
    if own_fig:
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

    # ---- Layout ---------------------------------------------------------
    # Top lane:    cloud → Fatigue → recovery → cloud
    # Middle lane: cloud → Signal → adaptation → Fitness → atrophy → cloud
    # Signal also drains downward through signal loss.
    # Fatigue and Signal share an x so their inflow valves stack vertically,
    # with the shared driver (effective TRIMP) between them.
    stock_w, stock_h = 1.9, 0.95
    valve_r = 0.16
    gap = valve_r + 0.06          # causal arrows stop at the valve rim

    fatigue_pos = (5.0, 7.0)
    signal_pos  = (5.0, 3.5)
    fitness_pos = (10.0, 3.5)

    cloud_T_top   = (1.3, 7.0)      # source for Fatigue inflow
    cloud_T_mid   = (1.3, 3.5)      # source for Signal inflow
    cloud_recov   = (8.6, 7.0)      # recovery sink
    cloud_sigloss = (5.0, 0.75)     # signal-loss sink
    cloud_atrophy = (13.1, 3.5)     # atrophy sink

    def left_edge(p):   return (p[0] - stock_w / 2, p[1])
    def right_edge(p):  return (p[0] + stock_w / 2, p[1])
    def top_edge(p):    return (p[0], p[1] + stock_h / 2)
    def bottom_edge(p): return (p[0], p[1] - stock_h / 2)

    # Valve centers (draw_flow puts the valve at the pipe midpoint)
    fat_in_valve  = ((cloud_T_top[0] + left_edge(fatigue_pos)[0]) / 2, fatigue_pos[1])
    sig_in_valve  = ((cloud_T_mid[0] + left_edge(signal_pos)[0]) / 2, signal_pos[1])
    recov_valve   = ((right_edge(fatigue_pos)[0] + cloud_recov[0]) / 2, fatigue_pos[1])
    adapt_valve   = ((right_edge(signal_pos)[0] + left_edge(fitness_pos)[0]) / 2, signal_pos[1])
    atrophy_valve = ((right_edge(fitness_pos)[0] + cloud_atrophy[0]) / 2, fitness_pos[1])
    sigloss_valve = (signal_pos[0], (bottom_edge(signal_pos)[1] + cloud_sigloss[1]) / 2)

    # Text helpers carry fontscale; the param helpers are no-ops when
    # detail=False, which drops every constant and its link and keeps the
    # stocks, flows, drivers and state-to-flow links.
    fs = fontscale

    def flow(src, dst, **kw):
        draw_flow(ax, src, dst, valve_radius=valve_r, fontsize=10 * fs, **kw)

    def stock(p, name):
        draw_stock(ax, *p, stock_w, stock_h, name, fontsize=11 * fs)

    def aux(p, name):
        draw_aux(ax, *p, name, fontsize=10 * fs)

    def link(src, dst, **kw):
        # Compact view keeps the red "−" glyphs (the non-obvious links) and
        # lets color alone mark the "+" links.
        sign = detail or kw.get("polarity") == "-"
        draw_causal(ax, src, dst, fontsize=12 * fs, show_sign=sign, **kw)

    def param(p, name):
        if detail:
            draw_param(ax, *p, name, fontsize=10 * fs)

    def plink(src, dst, **kw):
        if detail:
            link(src, dst, **kw)

    # ---- Stocks, flows, clouds -------------------------------------------
    for c in (cloud_T_top, cloud_T_mid, cloud_recov, cloud_sigloss, cloud_atrophy):
        draw_cloud(ax, *c, scale=0.55)

    flow(cloud_T_top, left_edge(fatigue_pos))
    stock(fatigue_pos, "Fatigue")
    flow(right_edge(fatigue_pos), cloud_recov,
         label="recovery", label_offset=(0, 0.45 * max(1.0, fs * 0.9)))

    flow(cloud_T_mid, left_edge(signal_pos))
    stock(signal_pos, "Signal")
    # Middle-lane flow names sit high enough that the stock→valve links can
    # arc in underneath them and visibly reach the valve rim.
    flow(right_edge(signal_pos), left_edge(fitness_pos),
         label="adaptation", label_offset=(0, 0.95))
    stock(fitness_pos, "Fitness")
    flow(right_edge(fitness_pos), cloud_atrophy,
         label="atrophy", label_offset=(0, 0.95))

    flow(bottom_edge(signal_pos), cloud_sigloss,
         label="signal\nloss", label_offset=(-0.75 * max(1.0, fs * 0.85), 0))

    # ---- Training drive: training + adl_trimp -> effective TRIMP -> both
    #      inflow valves (the same rate enters Fatigue and Signal) ----------
    eff_pos = (fat_in_valve[0], (fatigue_pos[1] + signal_pos[1]) / 2)
    if detail:
        training_pos = (0.75, eff_pos[1] + 0.55)
        adl_pos = (0.75, eff_pos[1] - 0.55)
        aux(eff_pos, "effective\nTRIMP")
        aux(training_pos, "training")
        param(adl_pos, "adl_trimp")
        link((training_pos[0] + 0.55, training_pos[1] - 0.05),
             (eff_pos[0] - 0.62, eff_pos[1] + 0.12), polarity="+", curvature=0.0)
        plink((adl_pos[0] + 0.62, adl_pos[1] + 0.05),
              (eff_pos[0] - 0.62, eff_pos[1] - 0.12), polarity="+", curvature=0.0)
    else:
        # Compact view: one driver node (adl_trimp is a constant, so it is
        # dropped with the other parameters).
        aux(eff_pos, "training\nload")
    eff_half_h = 0.42 * max(1.0, fs * 0.8)
    link((eff_pos[0], eff_pos[1] + eff_half_h),
         _toward((eff_pos[0], eff_pos[1] + eff_half_h), fat_in_valve, gap),
         polarity="+", curvature=0.0)
    link((eff_pos[0], eff_pos[1] - eff_half_h),
         _toward((eff_pos[0], eff_pos[1] - eff_half_h), sig_in_valve, gap),
         polarity="+", curvature=0.0)

    # ---- Recovery: Fatigue (+), tau_fatigue (-) ---------------------------
    # Both links enter from BELOW the top lane: the space above it carries the
    # flow label and the Fatigue→Performance arc.
    tau_f_pos = (recov_valve[0] + 0.85, recov_valve[1] - 1.0)
    param(tau_f_pos, "tau_fatigue")
    link((fatigue_pos[0] + 0.5, fatigue_pos[1] - stock_h / 2),
         _toward((recov_valve[0] - 0.4, recov_valve[1] - 0.6), recov_valve, gap),
         polarity="+", curvature=0.35, nudge=-0.25)
    plink((tau_f_pos[0] - 0.3, tau_f_pos[1] + 0.17),
          _toward((tau_f_pos[0] - 0.3, tau_f_pos[1] + 0.17), recov_valve, gap),
          polarity="-", curvature=0.0)

    # ---- Adaptation: Signal (+), adaptation_rate (+), adaptation_delay (-) -
    ar_pos = (adapt_valve[0] - 1.0, adapt_valve[1] - 1.0)
    ad_pos = (adapt_valve[0] + 1.0, adapt_valve[1] - 1.0)
    param(ar_pos, "adaptation_rate")
    param(ad_pos, "adaptation_delay")
    link((signal_pos[0] + 0.6, signal_pos[1] + stock_h / 2),
         _toward((adapt_valve[0] - 0.5, adapt_valve[1] + 0.45), adapt_valve, gap),
         polarity="+", curvature=-0.25)
    plink((ar_pos[0] + 0.2, ar_pos[1] + 0.17),
          _toward((ar_pos[0] + 0.2, ar_pos[1] + 0.17), adapt_valve, gap),
          polarity="+", curvature=0.0)
    plink((ad_pos[0] - 0.2, ad_pos[1] + 0.17),
          _toward((ad_pos[0] - 0.2, ad_pos[1] + 0.17), adapt_valve, gap),
          polarity="-", curvature=0.0)

    # ---- Signal loss: Signal (+), tau_signal (-) ---------------------------
    tau_s_pos = (sigloss_valve[0] + 1.25, sigloss_valve[1] - 0.35)
    param(tau_s_pos, "tau_signal")
    link((signal_pos[0] + 0.6, signal_pos[1] - stock_h / 2),
         _toward((sigloss_valve[0] + 0.6, sigloss_valve[1] + 0.5), sigloss_valve, gap),
         polarity="+", curvature=-0.30)
    plink((tau_s_pos[0] - 0.5, tau_s_pos[1] + 0.05),
          _toward((tau_s_pos[0] - 0.5, tau_s_pos[1] + 0.05), sigloss_valve, gap),
          polarity="-", curvature=0.0)

    # ---- Atrophy: Fitness (+), max_frac_rate (+), Capacity (-) -------------
    mfr_pos = (atrophy_valve[0] - 0.75, atrophy_valve[1] - 1.0)
    cap_pos = (atrophy_valve[0] + 0.75, atrophy_valve[1] - 1.0)
    param(mfr_pos, "max_frac_rate")
    param(cap_pos, "Capacity")
    link((fitness_pos[0] + 0.6, fitness_pos[1] + stock_h / 2),
         _toward((atrophy_valve[0] - 0.5, atrophy_valve[1] + 0.45), atrophy_valve, gap),
         polarity="+", curvature=-0.25)
    plink((mfr_pos[0] + 0.2, mfr_pos[1] + 0.17),
          _toward((mfr_pos[0] + 0.2, mfr_pos[1] + 0.17), atrophy_valve, gap),
          polarity="+", curvature=0.0)
    plink((cap_pos[0] - 0.2, cap_pos[1] + 0.17),
          _toward((cap_pos[0] - 0.2, cap_pos[1] + 0.17), atrophy_valve, gap),
          polarity="-", curvature=0.0)

    # ---- Performance readout: Fitness (+), Fatigue (-), alpha (-) ----------
    perf_pos = (11.4, 7.0)
    alpha_pos = (13.25, 7.0)
    perf_half_w = 0.75 * max(1.0, fs * 0.9)
    aux(perf_pos, "Performance")
    param(alpha_pos, "alpha")
    link((fitness_pos[0] + 0.1, fitness_pos[1] + stock_h / 2),
         (perf_pos[0] - 0.15, perf_pos[1] - 0.25), polarity="+", curvature=0.0)
    # Arcs high over the recovery flow and its label
    link((fatigue_pos[0] + 0.3, fatigue_pos[1] + stock_h / 2),
         (perf_pos[0] - 0.45, perf_pos[1] + 0.22), polarity="-", curvature=-0.28)
    plink((alpha_pos[0] - 0.35, alpha_pos[1]),
          (perf_pos[0] + perf_half_w, perf_pos[1]), polarity="-", curvature=0.0)

    # ---- Title ----------------------------------------------------------
    if title is None:
        title = "MEDv4 stock-and-flow"
    if title:
        ax.text(
            7.0, 8.6, title, ha="center", va="center",
            fontsize=14 * fs, fontweight="bold", color=COLOR_STOCK_EDGE,
        )

    # ---- Notation key ---------------------------------------------------
    if show_key:
        ax.text(
            0.4, 0.1,
            "box = stock    pipe + valve = flow    cloud = outside the model    "
            "thin arrow = influence (blue + raises, red − lowers)    "
            "bold = computed    italic = parameter",
            ha="left", va="center", fontsize=8 * fs, color="#5A5A5A", style="italic",
        )

    if own_fig:
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
