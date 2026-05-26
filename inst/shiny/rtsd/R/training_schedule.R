#' PULSE TRAIN, Vensim semantics
#'
#' Vectorised port of Vensim's `PULSE TRAIN(start, duration, repeat_time, end)`.
#' Returns 1 when `t` falls inside a pulse window
#' `[start + k*repeat_time, start + k*repeat_time + duration]`
#' for non-negative integer `k`, while `start + k*repeat_time <= end`.
#'
#' @param t Numeric vector of query times.
#' @param start First pulse start time.
#' @param duration Pulse width.
#' @param repeat_time Period between pulse starts. Must be > 0.
#' @param end Last time at which a pulse may begin.
#' @return Numeric vector, 0 or 1, same length as `t`.
pulse_train <- function(t, start, duration, repeat_time, end, tol = 1e-9) {
  stopifnot(repeat_time > 0, duration >= 0)
  if (end < start) return(rep(0, length(t)))
  k_max <- floor((end - start) / repeat_time + tol)
  active <- logical(length(t))
  for (k in 0:k_max) {
    pks <- start + k * repeat_time
    # Half-open [pks, pks + duration) with float tolerance at the upper edge.
    active <- active | (t >= pks - tol & t < pks + duration - tol)
  }
  as.numeric(active)
}

#' Build the MEDv4 training forcing schedule on a time grid
#'
#' Ports the Vensim `training` equation:
#'   training = volume_load * PULSE TRAIN(1, 1/7, 1 - frequency/7, 16)
#'           + volume_load * PULSE TRAIN(17, 1/7, 1 - frequency/21, 48)
#'
#' @param grid Numeric vector of times (weeks) at which to evaluate.
#' @param params List containing `volume_load`, `frequency`.
#' @return Numeric vector, same length as `grid`, giving the training input
#'   (TRIMP) at each grid point.
build_training_schedule <- function(grid, params) {
  f <- params$frequency
  vl <- params$volume_load
  block1 <- pulse_train(grid, start = 1,  duration = 1/7,
                        repeat_time = 1 - f / 7,  end = 16)
  block2 <- pulse_train(grid, start = 17, duration = 1/7,
                        repeat_time = 1 - f / 21, end = 48)
  vl * (block1 + block2)
}

#' Build a training schedule from a list of discrete training events
#'
#' Generalisation of `pulse_train()`/`build_training_schedule()` that accepts
#' arbitrary event times (e.g. real session dates from a training log) and per-event
#' heights (e.g. work done at each session = exerciseWeight * exerciseDuration).
#'
#' At each event time `t_i`, a rectangular pulse of height `h_i` is added to
#' the grid over the half-open window `[t_i, t_i + width)`. Overlapping pulses
#' sum (should be rare in practice since session dates are unique per subject).
#'
#' @param grid Numeric vector of evaluation times (weeks, ascending).
#' @param event_times Numeric vector of event start times (same units as grid).
#' @param event_heights Numeric vector of per-event pulse heights. Same length
#'   as `event_times`.
#' @param width Pulse width (same units as grid). Default `1/7` week (one day).
#' @param tol Float tolerance at pulse boundaries. Matches `pulse_train()`.
#' @return Numeric vector same length as `grid`.
pulse_from_events <- function(grid, event_times, event_heights,
                              width = 1/7, tol = 1e-9) {
  stopifnot(length(event_times) == length(event_heights), width >= 0)
  out <- numeric(length(grid))
  for (i in seq_along(event_times)) {
    t_i <- event_times[i]
    h_i <- event_heights[i]
    active <- grid >= t_i - tol & grid < t_i + width - tol
    out[active] <- out[active] + h_i
  }
  out
}

#' Make a step-function interpolator for the training input
#'
#' `deSolve::ode` calls the RHS at internal integrator times that may not
#' land on the grid. `method = "constant"` gives the piecewise-constant
#' behaviour that matches Vensim's fixed-step interpretation of PULSE TRAIN.
#'
#' @param grid Numeric vector of times.
#' @param schedule Numeric vector of training values on `grid`.
#' @return A function of `t` returning interpolated training.
make_training_fn <- function(grid, schedule) {
  approxfun(grid, schedule, method = "constant", rule = 2, f = 0, ties = "ordered")
}
