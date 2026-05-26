#' Stock-and-flow diagram of MEDv4, generated from R
#'
#' DiagrammeR + Graphviz gives us a reproducible, source-controllable diagram
#' that matches the R ODE port. Shapes used:
#'   - Stocks     = box (the INTEG state variables)
#'   - Flows      = ellipse (derivative terms added/subtracted on stocks)
#'   - Parameters = plaintext (constants from `default_params()`)
#'   - Clouds     = plaintext ☁ (sources/sinks of stock conservation)
#'
#' Use `grViz()` to render interactively or `DiagrammeRsvg::export_svg()` to
#' freeze a copy on disk.

med_diagram_dot <- function() {
  '
digraph MEDv4 {
  graph [rankdir = LR, splines = spline, nodesep = 0.5, ranksep = 1.0,
         fontname = "Helvetica", bgcolor = "white"];
  node  [fontname = "Helvetica", fontsize = 11];
  edge  [fontname = "Helvetica", fontsize = 9];

  // ----- Stocks (rectangles) -----
  {
    node [shape = box, style = "filled,bold", color = "#1565C0",
          fontcolor = "#0D47A1", penwidth = 2];
    Fitness [fillcolor = "#BBDEFB", label = "Fitness\n(kg)"];
    Fatigue [fillcolor = "#FFCDD2", label = "Fatigue"];
    Signal  [fillcolor = "#FFF9C4", label = "Signal"];
  }

  // ----- Flows (ellipses) -----
  {
    node [shape = ellipse, style = filled, color = "#2E7D32"];
    adaptation  [fillcolor = "#C8E6C9"];
    atrophy     [fillcolor = "#FFE0B2"];
    TRIMP_F     [fillcolor = "#FFCCBC", label = "TRIMP"];
    TRIMP_S     [fillcolor = "#FFCCBC", label = "TRIMP"];
    recovery    [fillcolor = "#B2DFDB"];
    signal_loss [fillcolor = "#D1C4E9", label = "signal loss"];
  }

  // ----- Parameters (plaintext) -----
  {
    node [shape = plaintext, fontcolor = "#616161", fontsize = 10];
    adaptation_rate [label = "adaptation_rate"];
    adaptation_delay[label = "adaptation_delay"];
    max_frac_rate   [label = "max_frac_rate"];
    Capacity        [label = "Capacity"];
  }

  // ----- Sources / sinks (clouds) -----
  {
    node [shape = plaintext, label = "☁", fontsize = 18, fontcolor = "#9E9E9E"];
    src_Fa; src_Si; sink_Fi; sink_Fa; sink_Si;
  }

  // ========== Stock-and-flow edges (solid, bold) ==========
  edge [color = "#212121", penwidth = 2, arrowsize = 0.9];

  // Fitness stock
  adaptation -> Fitness;
  Fitness    -> atrophy -> sink_Fi;

  // Fatigue stock
  src_Fa     -> TRIMP_F -> Fatigue;
  Fatigue    -> recovery -> sink_Fa;

  // Signal stock — TRIMP in, adaptation + signal_loss out
  src_Si     -> TRIMP_S -> Signal;
  Signal     -> adaptation;                 // adaptation consumes Signal
  Signal     -> signal_loss -> sink_Si;

  // ========== Causal / parameter influences (dashed, thin) ==========
  edge [style = dashed, color = "#616161", penwidth = 1, arrowsize = 0.7];

  // adaptation depends on adaptation_rate, adaptation_delay, Signal (already linked)
  adaptation_rate  -> adaptation;
  adaptation_delay -> adaptation;

  // atrophy depends on Fitness (already linked), max_frac_rate, Capacity
  max_frac_rate    -> atrophy;
  Capacity         -> atrophy;

  // Layout hints — group parameters above stocks
  { rank = source; adaptation_rate; adaptation_delay; max_frac_rate; Capacity; }
  { rank = same; Fitness; Fatigue; Signal; }
}
'
}

#' Render MEDv4 diagram in-session
med_diagram <- function() {
  if (!requireNamespace("DiagrammeR", quietly = TRUE)) {
    stop("Install DiagrammeR: renv::install('DiagrammeR')")
  }
  DiagrammeR::grViz(med_diagram_dot())
}

#' Save MEDv4 diagram to SVG on disk
#'
#' @param path Output path. Defaults to `docs/med_diagram.svg`.
save_med_diagram_svg <- function(path = "docs/med_diagram.svg") {
  if (!requireNamespace("DiagrammeRsvg", quietly = TRUE) ||
      !requireNamespace("rsvg", quietly = TRUE)) {
    stop("Install rendering deps: renv::install(c('DiagrammeRsvg', 'rsvg'))")
  }
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  gr <- DiagrammeR::grViz(med_diagram_dot())
  svg <- DiagrammeRsvg::export_svg(gr)
  writeLines(svg, path)
  invisible(path)
}
