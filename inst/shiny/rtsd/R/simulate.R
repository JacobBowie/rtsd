#' Simulate the MEDv4 fitness-fatigue model
#'
#' @param params Parameter list (see `default_params()`).
#' @param horizon Simulation horizon in weeks. Default 48 to match Vensim
#'   FINAL TIME.
#' @param dt Output time step in weeks. Default 0.0625 to match Vensim
#'   TIME STEP.
#' @param method deSolve integrator. `"euler"` is the default — at
#'   `dt = 0.0625` it reproduces PySD/Vensim bit-exactly, which is the
#'   reference we validated against. Switch to `"lsoda"` for
#'   adaptive-step accuracy (useful in calibration, but trajectories
#'   will differ from Vensim at the third decimal place).
#' @param training_fn Optional pre-built training forcing function of the
#'   form `function(t) -> TRIMP`. If `NULL` (default), the schedule is
#'   built from `params$frequency` and `params$volume_load` via the
#'   legacy Vensim PULSE TRAIN parameterization (`build_training_schedule()`),
#'   which is what the PySD oracle test validates. Passing a
#'   non-NULL `training_fn` bypasses that path entirely — used by
#'   `R/scenarios.R` for arbitrary training programs (e.g. detraining,
#'   return-from-break, custom event sequences) and by data-fitting
#'   workflows that consume real per-subject session histories.
#' @return A tibble with columns: time, Fitness, Fatigue, Signal, TRIMP,
#'   adaptation, atrophy, recovery, signal_loss.
simulate_med <- function(params = default_params(),
                         horizon = 48,
                         dt = 0.0625,
                         method = c("euler", "lsoda", "rk4"),
                         training_fn = NULL,
                         variant = c("quadratic", "linear")) {
  method  <- match.arg(method)
  variant <- match.arg(variant)
  grid <- seq(0, horizon, by = dt)

  if (is.null(training_fn)) {
    schedule    <- build_training_schedule(grid, params)
    training_fn <- make_training_fn(grid, schedule)
  }

  parameters <- list(params = params, training_fn = training_fn)
  state <- c(Fitness = params$Baseline, Fatigue = 0, Signal = 0)
  rhs <- if (variant == "linear") med_ode_linear else med_ode

  out <- deSolve::ode(
    y      = state,
    times  = grid,
    func   = rhs,
    parms  = parameters,
    method = method
  )
  tibble::as_tibble(as.data.frame(out))
}
