#' GraphPad-Prism-style ggplot2 theme for rtSD figures
#'
#' R mirror of the "Prism" Altair theme used by the rtSD Explorer dashboard.
#' SOURCE OF TRUTH: `_THEME_PRISM` in `python/rtsd/rtsd.py` (the `_imports`
#' cell), plus `STOCK_COLORS` / `SNAP_PALETTE` in the `_palette` cell of the
#' same notebook. The two themes must stay in sync: if you change an axis
#' width, font size or color there, change it here too (and vice versa), so
#' that static validator figures and the live dashboard read as one system.
#'
#' Unit mapping. Altair sizes are CSS px; ggplot2 text is in pt and
#' `linewidth` is in ggplot's mm-like unit (`lwd = linewidth * .pt`, with
#' 1 lwd = 1/96 in on ragg/png devices). This theme treats 1 Altair px as
#' `base_size / 12` pt, so at the default `base_size = 12` the dashboard's
#' 12 px axis labels become 12 pt labels and every stroke keeps the same
#' ratio to the text that it has on the dashboard. `rtsd_linewidth()` does
#' the px -> `linewidth` conversion and is exported for data layers.
#'
#' Altair key -> ggplot2 element:
#'   view.stroke = transparent             -> panel.border = blank
#'   background = white                    -> plot/panel.background = white
#'   axis.domainColor #000, domainWidth 2.5-> axis.line, black, 2.5 px
#'   axis.tickColor #000, tickWidth 2      -> axis.ticks, black, 2 px
#'   axis.tickSize 7 (outward)             -> axis.ticks.length = 7 px
#'   axis.labelFontSize 12, #000, Arial    -> axis.text
#'   axis.titleFontSize 14, bold, #000     -> axis.title
#'   axis/axisX/axisY grid = FALSE         -> panel.grid = blank
#'   axis.offset 6                         -> NOT mirrored (no native ggplot2
#'                                            axis offset; marked experimental
#'                                            on the dashboard)
#'   title 15, bold, #000, anchor start    -> plot.title, hjust 0,
#'                                            plot.title.position = "plot"
#'   title.offset 12                       -> plot.title/subtitle bottom margin
#'   legend.labelFontSize 12, title 13     -> legend.text / legend.title
#'   font = Arial                          -> base_family
#'   line.strokeWidth 3                    -> rtsd_linewidth(3) for geom_line;
#'                                            also the default geom linewidth
#'                                            on ggplot2 >= 4.0 (element_geom)
#'
#' Requires ggplot2 (a Suggests dependency; figures only). For Arial to
#' resolve reliably, save with `ragg::agg_png` (systemfonts font lookup).
#'
#' @param base_size Axis-label font size in pt (the Altair `labelFontSize`).
#'   All other sizes and stroke widths scale with it.
#' @param base_family Font family. Default "Arial", matching the dashboard.
#' @return A ggplot2 theme object.
#' @examples
#' \dontrun{
#' ggplot2::ggplot(df, ggplot2::aes(t, Fitness)) +
#'   ggplot2::geom_line(linewidth = rtsd_linewidth(3),
#'                      colour = RTSD_STOCK_COLORS[["Fitness"]]) +
#'   theme_rtsd_prism()
#' }
theme_rtsd_prism <- function(base_size = 12, base_family = "Arial") {
  k  <- base_size / 12                     # pt per Altair px
  px <- function(x) x * k                  # Altair px -> pt
  lw <- function(x) rtsd_linewidth(x, base_size = base_size)
  ink <- "#000000"

  th <- ggplot2::theme_classic(base_size = base_size,
                               base_family = base_family) +
    ggplot2::theme(
      text = ggplot2::element_text(family = base_family, colour = ink),

      # view.stroke transparent + white background
      panel.border     = ggplot2::element_blank(),
      panel.background = ggplot2::element_rect(fill = "white", colour = NA),
      plot.background  = ggplot2::element_rect(fill = "white", colour = NA),
      panel.grid       = ggplot2::element_blank(),

      # Heavy black L-axes, black outward ticks
      axis.line  = ggplot2::element_line(colour = ink, linewidth = lw(2.5),
                                         lineend = "square"),
      axis.ticks = ggplot2::element_line(colour = ink, linewidth = lw(2),
                                         lineend = "butt"),
      axis.ticks.length = ggplot2::unit(px(7), "pt"),

      # Axis labels 12 px, axis titles 14 px bold
      axis.text   = ggplot2::element_text(size = px(12), colour = ink),
      axis.text.x = ggplot2::element_text(margin = ggplot2::margin(t = px(4))),
      axis.text.y = ggplot2::element_text(margin = ggplot2::margin(r = px(4))),
      axis.title  = ggplot2::element_text(size = px(14), face = "bold",
                                          colour = ink),
      axis.title.x = ggplot2::element_text(margin = ggplot2::margin(t = px(8))),
      axis.title.y = ggplot2::element_text(angle = 90,
                                           margin = ggplot2::margin(r = px(8))),

      # Title 15 px bold, anchored at the start of the whole chart
      plot.title = ggplot2::element_text(size = px(15), face = "bold",
                                         colour = ink, hjust = 0,
                                         margin = ggplot2::margin(b = px(4))),
      plot.subtitle = ggplot2::element_text(size = px(12), colour = ink,
                                            hjust = 0,
                                            margin = ggplot2::margin(b = px(12))),
      plot.title.position = "plot",
      plot.caption = ggplot2::element_text(size = px(10), colour = ink,
                                           hjust = 0),
      plot.caption.position = "plot",
      plot.margin = ggplot2::margin(px(10), px(14), px(8), px(8)),

      # Legend 12 px labels / 13 px title (validator figures direct-label
      # instead, but keep the dashboard legend spec for other uses)
      legend.text  = ggplot2::element_text(size = px(12), colour = ink),
      legend.title = ggplot2::element_text(size = px(13), face = "bold",
                                           colour = ink),
      legend.background = ggplot2::element_blank(),
      legend.key        = ggplot2::element_blank(),

      # Facets: Prism style, no strip box
      strip.background = ggplot2::element_blank(),
      strip.text = ggplot2::element_text(size = px(13), face = "bold",
                                         colour = ink)
    )

  # ggplot2 >= 4.0: theme-level geom defaults, so geom_line()/geom_text()
  # pick up the 3 px data stroke and Arial without per-layer arguments.
  if (utils::packageVersion("ggplot2") >= "4.0.0") {
    th <- th + ggplot2::theme(
      geom = ggplot2::element_geom(
        ink = ink, paper = "white",
        linewidth = lw(3),
        family = base_family,
        fontsize = px(12)
      )
    )
  }
  th
}

#' Convert an Altair stroke width (CSS px) to a ggplot2 `linewidth`
#'
#' Uses the same scale as `theme_rtsd_prism()`: 1 Altair px = `base_size/12`
#' pt, and ggplot2 draws `lwd = linewidth * .pt` with 1 lwd = 1/96 in.
#'
#' @param px Stroke width in Altair px (e.g. 3 for `line.strokeWidth`).
#' @param base_size The `base_size` passed to `theme_rtsd_prism()`.
#' @return Numeric `linewidth` value.
rtsd_linewidth <- function(px, base_size = 12) {
  pt <- px * base_size / 12
  pt * (96 / 72.27) / ggplot2::.pt
}

#' Stock colors, synced with `STOCK_COLORS` in python/rtsd/rtsd.py and
#' inst/shiny/rtsd/app.R.
RTSD_STOCK_COLORS <- c(
  Fitness     = "#1565C0",
  Fatigue     = "#C62828",
  Signal      = "#F9A825",
  Performance = "#2E7D32"
)

#' Categorical palette for non-stock series (comparisons, snapshots), synced
#' with `SNAP_PALETTE` in python/rtsd/rtsd.py. Chosen not to clash with the
#' four stock colors.
RTSD_SNAP_PALETTE <- c(
  "#6A1B9A", "#00838F", "#EF6C00", "#5D4037",
  "#AD1457", "#558B2F", "#283593", "#00695C"
)
