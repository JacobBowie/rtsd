#' rtSD Explorer — MEDv4 fitness-fatigue-signal explorer for resistance training
#'
#' Single-file Shiny app for interactively exploring the MEDv4
#' fitness-fatigue-signal ODE through deterministic forward simulation
#' driven by sliders. The Shiny surface of the rtSD model
#' (system-dynamics implementation of GET-PAID for resistance training).
#' Canonical hosted demo is the marimo/WASM build at https://jacobbowie.com/rtsd/ ;
#' this Shiny app is runnable locally (below) or deployable to shinyapps.io.
#'
#' Run from project root:
#'   shiny::runApp("inst/shiny/rtsd")
#'
#' Or from anywhere:
#'   shiny::runApp(system.file("shiny/rtsd", package = "rtSD"))

library(shiny)
library(bslib)
library(ggplot2)
library(patchwork)
library(dplyr)
library(tidyr)
library(DiagrammeR)

# -----------------------------------------------------------------------------
# Helper R files in ./R/ are auto-sourced by Shiny on startup (>= 1.5).
# The app is self-contained for deployment — no walking up to a project root.
# -----------------------------------------------------------------------------

`%||%` <- function(a, b) if (is.null(a)) b else a

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

STOCK_COLORS <- c(
  Fitness     = "#1565C0",
  Fatigue     = "#C62828",
  Signal      = "#F9A825",
  Performance = "#2E7D32"
)

scenario_training_fn <- function(scenario, grid, params, sessions_per_week,
                                 vol, n_weeks, detrain_start,
                                 rp_mev, rp_mrv, rp_accum_weeks,
                                 rp_deload_weeks, rp_n_meso,
                                 rp_work_per_set, rp_deload_frac,
                                 rp_mev_creep) {
  switch(scenario,
    "standard"   = scenario_standard(grid, sessions_per_week, vol, n_weeks),
    "high_freq"  = scenario_high_freq(grid, sessions_per_week, vol, n_weeks),
    "detraining" = scenario_detraining(grid, train_weeks = detrain_start,
                                       sessions_per_week = sessions_per_week,
                                       vol = vol),
    "untrained"  = scenario_untrained(grid),
    "rp"         = scenario_rp(grid,
                               start_week         = 1,
                               n_mesocycles       = rp_n_meso,
                               accumulation_weeks = rp_accum_weeks,
                               deload_weeks       = rp_deload_weeks,
                               mev_sets           = rp_mev,
                               mrv_sets           = rp_mrv,
                               sessions_per_week  = sessions_per_week,
                               work_per_set       = rp_work_per_set,
                               deload_fraction    = rp_deload_frac,
                               mev_creep_per_cycle = rp_mev_creep),
    scenario_standard(grid, sessions_per_week, vol, n_weeks)
  )
}

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

ui <- page_sidebar(
  title = "rtSD Explorer — MEDv4 fitness-fatigue model for resistance training",
  theme = bs_theme(version = 5, preset = "flatly"),

  sidebar = sidebar(
    width = 340,
    accordion(
      open = c("sim", "rates"),

      accordion_panel(
        "Simulation", value = "sim",
        selectInput("variant", "ODE variant",
                    choices = c("Linear (winning)" = "linear",
                                "Quadratic (original)" = "quadratic"),
                    selected = "linear"),
        selectInput("scenario", "Training scenario",
                    choices = c("Standard weekly"            = "standard",
                                "High frequency"             = "high_freq",
                                "Detraining"                 = "detraining",
                                "Untrained (ADL only)"       = "untrained",
                                "Renaissance Periodization"  = "rp"),
                    selected = "standard"),
        numericInput("horizon", "Horizon (weeks)", value = 48, min = 4,
                     max = 520, step = 4),
        sliderInput("sessions_per_week", "Sessions / week",
                    min = 1, max = 7, value = 3, step = 1),
        conditionalPanel(
          condition = "input.scenario != 'rp'",
          sliderInput("vol", "Volume load per session",
                      min = 0, max = 500, value = 81, step = 1)
        ),
        conditionalPanel(
          condition = "input.scenario == 'detraining'",
          sliderInput("detrain_start", "Detrain after (weeks)",
                      min = 4, max = 100, value = 24, step = 1)
        ),
        numericInput("dt", "Integration dt (weeks)",
                     value = 0.0625, min = 0.01, max = 0.25, step = 0.01)
      ),

      accordion_panel(
        "Renaissance Periodization", value = "rp_panel",
        helpText("Active when scenario = 'Renaissance Periodization'. ",
                 "Each mesocycle ramps weekly volume MEV → MRV linearly across ",
                 "accumulation weeks, then deloads."),
        sliderInput("rp_mev", "MEV (sets / week)",
                    min = 2, max = 30, value = 8, step = 1),
        sliderInput("rp_mrv", "MRV (sets / week)",
                    min = 4, max = 40, value = 18, step = 1),
        sliderInput("rp_accum_weeks", "Accumulation weeks per mesocycle",
                    min = 2, max = 8, value = 4, step = 1),
        sliderInput("rp_deload_weeks", "Deload weeks per mesocycle",
                    min = 0, max = 3, value = 1, step = 1),
        sliderInput("rp_n_meso", "Number of mesocycles",
                    min = 1, max = 8, value = 3, step = 1),
        sliderInput("rp_work_per_set", "Work per set (TRIMP units)",
                    min = 10, max = 300, value = 80, step = 5),
        sliderInput("rp_deload_frac", "Deload volume (fraction of MEV)",
                    min = 0.2, max = 1.0, value = 0.5, step = 0.05),
        sliderInput("rp_mev_creep", "MEV creep per mesocycle (sets)",
                    min = 0, max = 6, value = 0, step = 1)
      ),

      accordion_panel(
        "Adaptation & atrophy", value = "rates",
        sliderInput("adaptation_rate", "adaptation_rate",
                    min = 0.001, max = 0.05, value = 0.02, step = 0.001),
        sliderInput("adaptation_delay", "adaptation_delay (weeks)",
                    min = 1, max = 20, value = 5, step = 0.5),
        sliderInput("maximal_fractional_rate", "max_frac_rate",
                    min = 0.001, max = 0.1, value = 0.020, step = 0.001),
        sliderInput("Capacity", "Capacity",
                    min = 20, max = 400, value = 200, step = 5)
      ),

      accordion_panel(
        "Time constants & baseline",
        sliderInput("tau_fatigue", "tau_fatigue (weeks)",
                    min = 0.1, max = 5, value = 7 / exp(2), step = 0.05),
        sliderInput("tau_signal", "tau_signal (weeks)",
                    min = 1, max = 60, value = 14, step = 0.5),
        sliderInput("adl_trimp", "adl_trimp (baseline stim)",
                    min = 0, max = 60, value = 19, step = 1),
        sliderInput("alpha", "alpha (Performance coupling)",
                    min = 0, max = 2, value = 1, step = 0.05),
        sliderInput("Baseline", "Baseline Fitness",
                    min = 1, max = 80, value = 12.145, step = 0.5)
      )
    ),

    hr(),
    actionButton("snapshot", "Snapshot trajectory", class = "btn-primary w-100"),
    actionButton("clear_snaps", "Clear snapshots", class = "btn-outline-secondary w-100 mt-2"),
    actionButton("reset", "Reset parameters", class = "btn-outline-danger w-100 mt-2")
  ),

  navset_card_tab(
    nav_panel("Trajectories", plotOutput("trajectory", height = "640px")),
    nav_panel("Stock-and-flow",
              helpText("MEDv4 as three stocks (boxes), flows (ellipses), and parameters (plain)."),
              DiagrammeR::grVizOutput("diagram", height = "640px")),
    nav_panel("Training schedule", plotOutput("training_plot", height = "300px"),
              helpText("TRIMP forcing function evaluated on the integration grid. ADL baseline is added inside the ODE.")),
    nav_panel("Current state",
              verbatimTextOutput("params_echo"),
              tableOutput("summary_table"))
  )
)

# -----------------------------------------------------------------------------
# Server
# -----------------------------------------------------------------------------

server <- function(input, output, session) {

  snapshots <- reactiveVal(list())

  current_params <- reactive({
    list(
      adaptation_rate         = input$adaptation_rate,
      adaptation_delay        = input$adaptation_delay,
      maximal_fractional_rate = input$maximal_fractional_rate,
      max_frac_rate           = input$maximal_fractional_rate,
      Capacity                = input$Capacity,
      Baseline                = input$Baseline,
      volume_load             = input$vol,
      frequency               = input$sessions_per_week,
      tau_fatigue             = input$tau_fatigue,
      tau_signal              = input$tau_signal,
      adl_trimp               = input$adl_trimp,
      alpha                   = input$alpha
    )
  })

  current_grid <- reactive({
    seq(0, input$horizon, by = input$dt)
  })

  current_training <- reactive({
    scenario_training_fn(
      input$scenario, current_grid(), current_params(),
      sessions_per_week = input$sessions_per_week,
      vol               = input$vol %||% 81,
      n_weeks           = input$horizon,
      detrain_start     = input$detrain_start %||% 24,
      rp_mev            = input$rp_mev,
      rp_mrv            = input$rp_mrv,
      rp_accum_weeks    = input$rp_accum_weeks,
      rp_deload_weeks   = input$rp_deload_weeks,
      rp_n_meso         = input$rp_n_meso,
      rp_work_per_set   = input$rp_work_per_set,
      rp_deload_frac    = input$rp_deload_frac,
      rp_mev_creep      = input$rp_mev_creep
    )
  })

  sim <- reactive({
    p   <- current_params()
    tfn <- current_training()
    out <- simulate_med(
      params      = p,
      horizon     = input$horizon,
      dt          = input$dt,
      method      = "euler",
      training_fn = tfn,
      variant     = input$variant
    )
    out$Performance <- out$Fitness - p$alpha * out$Fatigue
    out
  })

  observeEvent(input$snapshot, {
    p   <- current_params()
    tag <- sprintf("#%d  ar=%.3f  mfr=%.3f  C=%.0f  %s",
                   length(snapshots()) + 1,
                   p$adaptation_rate, p$maximal_fractional_rate,
                   p$Capacity, input$variant)
    snapshots(c(snapshots(), setNames(list(sim()), tag)))
  })

  observeEvent(input$clear_snaps, snapshots(list()))

  observeEvent(input$reset, {
    dp <- default_params()
    updateSliderInput(session, "adaptation_rate", value = dp$adaptation_rate)
    updateSliderInput(session, "adaptation_delay", value = dp$adaptation_delay)
    updateSliderInput(session, "maximal_fractional_rate", value = dp$maximal_fractional_rate)
    updateSliderInput(session, "Capacity", value = dp$Capacity)
    updateSliderInput(session, "tau_fatigue", value = dp$tau_fatigue)
    updateSliderInput(session, "tau_signal", value = dp$tau_signal)
    updateSliderInput(session, "adl_trimp", value = 0)
    updateSliderInput(session, "alpha", value = 0)
    updateSliderInput(session, "Baseline", value = dp$Baseline)
  })

  output$trajectory <- renderPlot({
    live <- sim() %>%
      dplyr::select(time, Fitness, Fatigue, Signal, Performance) %>%
      pivot_longer(-time, names_to = "stock", values_to = "value") %>%
      mutate(stock = factor(stock, levels = names(STOCK_COLORS)))

    p <- ggplot() +
      facet_wrap(~ stock, scales = "free_y", ncol = 2) +
      theme_minimal(base_size = 13) +
      theme(legend.position = "bottom",
            legend.text = element_text(size = 9),
            strip.text = element_text(face = "bold")) +
      labs(x = "Time (weeks)", y = NULL)

    if (length(snapshots()) > 0) {
      snaps_df <- purrr::imap(snapshots(), function(s, tag) {
        s %>% dplyr::select(time, Fitness, Fatigue, Signal, Performance) %>%
          pivot_longer(-time, names_to = "stock", values_to = "value") %>%
          mutate(snapshot = tag)
      }) %>% purrr::list_rbind() %>%
        mutate(stock = factor(stock, levels = names(STOCK_COLORS)))

      p <- p + geom_line(data = snaps_df,
                         aes(time, value, group = snapshot),
                         color = "gray60", linewidth = 0.4, alpha = 0.7)
    }

    p + geom_line(data = live,
                  aes(time, value, color = stock),
                  linewidth = 1.2, show.legend = FALSE) +
      scale_color_manual(values = STOCK_COLORS)
  })

  output$training_plot <- renderPlot({
    grid <- current_grid()
    tfn  <- current_training()
    tr   <- data.frame(time = grid, TRIMP = tfn(grid))
    title <- if (identical(input$scenario, "rp")) {
      sprintf("Renaissance Periodization — %d mesocycle(s) × (%d accum + %d deload) wk · MEV %d → MRV %d sets/wk · %d sessions/wk",
              input$rp_n_meso, input$rp_accum_weeks, input$rp_deload_weeks,
              input$rp_mev, input$rp_mrv, input$sessions_per_week)
    } else {
      sprintf("Scenario: %s — %d sessions/wk × %d volume",
              input$scenario, input$sessions_per_week, input$vol %||% 81)
    }
    ggplot(tr, aes(time, TRIMP)) +
      geom_col(width = input$dt, color = "#1565C0", fill = "#1565C0") +
      theme_minimal(base_size = 13) +
      labs(x = "Time (weeks)", y = "TRIMP", title = title)
  })

  output$diagram <- DiagrammeR::renderGrViz({
    DiagrammeR::grViz(med_diagram_dot())
  })

  output$params_echo <- renderPrint({
    str(current_params())
  })

  output$summary_table <- renderTable({
    s <- sim()
    data.frame(
      Stock = c("Fitness", "Fatigue", "Signal", "Performance"),
      Start = c(s$Fitness[1], s$Fatigue[1], s$Signal[1],
                s$Fitness[1] - current_params()$alpha * s$Fatigue[1]),
      End   = c(tail(s$Fitness, 1), tail(s$Fatigue, 1),
                tail(s$Signal, 1), tail(s$Performance, 1)),
      Min   = c(min(s$Fitness), min(s$Fatigue), min(s$Signal), min(s$Performance)),
      Max   = c(max(s$Fitness), max(s$Fatigue), max(s$Signal), max(s$Performance))
    )
  }, digits = 3)
}

shinyApp(ui, server)
