#' Scenario builders for MEDv4 plausibility testing
#'
#' Each `scenario_*()` function returns a `training_fn` (callable of `t`)
#' suitable for `simulate_med(training_fn = ...)`. Building training as
#' an event list (via `pulse_from_events()`) rather than a Vensim-style
#' PULSE TRAIN parameterization makes the scenarios composable and lets
#' us model arbitrary programs (detraining, return-from-break, custom
#' periodisation) using the same code path that ingests real session data.
#'
#' The intent is to verify MEDv4 produces qualitatively expected
#' behaviour across canonical training paradigms BEFORE calibrating to
#' real data.

#' Build a constant-zero training function on the given grid.
scenario_untrained <- function(grid) {
  schedule <- numeric(length(grid))
  make_training_fn(grid, schedule)
}

#' Standard weekly training: one session per week for `n_weeks`.
scenario_standard <- function(grid,
                              sessions_per_week = 1,
                              vol = 81,
                              n_weeks = 48,
                              start_week = 1) {
  events <- build_session_events(
    start_week        = start_week,
    end_week          = start_week + n_weeks - 1,
    sessions_per_week = sessions_per_week,
    vol               = vol
  )
  schedule <- pulse_from_events(grid, events$times, events$heights)
  make_training_fn(grid, schedule)
}

#' High-frequency training (default 3 sessions/week).
scenario_high_freq <- function(grid,
                               sessions_per_week = 3,
                               vol = 81,
                               n_weeks = 48) {
  scenario_standard(grid,
                    sessions_per_week = sessions_per_week,
                    vol = vol,
                    n_weeks = n_weeks)
}

#' Detraining: train for `train_weeks`, then stop entirely.
scenario_detraining <- function(grid,
                                train_weeks = 24,
                                sessions_per_week = 1,
                                vol = 81) {
  events <- build_session_events(
    start_week        = 1,
    end_week          = train_weeks,
    sessions_per_week = sessions_per_week,
    vol               = vol
  )
  schedule <- pulse_from_events(grid, events$times, events$heights)
  make_training_fn(grid, schedule)
}

#' Return from break: train, gap, resume.
scenario_return_from_break <- function(grid,
                                       train1_weeks = 12,
                                       gap_weeks = 12,
                                       train2_weeks = 24,
                                       sessions_per_week = 1,
                                       vol = 81) {
  block1 <- build_session_events(
    start_week        = 1,
    end_week          = train1_weeks,
    sessions_per_week = sessions_per_week,
    vol               = vol
  )
  resume_start <- train1_weeks + gap_weeks + 1
  block2 <- build_session_events(
    start_week        = resume_start,
    end_week          = resume_start + train2_weeks - 1,
    sessions_per_week = sessions_per_week,
    vol               = vol
  )
  times   <- c(block1$times,   block2$times)
  heights <- c(block1$heights, block2$heights)
  schedule <- pulse_from_events(grid, times, heights)
  make_training_fn(grid, schedule)
}

#' Overreaching: high frequency AND high volume per session.
scenario_overreaching <- function(grid,
                                  sessions_per_week = 5,
                                  vol = 200,
                                  n_weeks = 48) {
  scenario_standard(grid,
                    sessions_per_week = sessions_per_week,
                    vol = vol,
                    n_weeks = n_weeks)
}

#' Internal: build (times, heights) for `sessions_per_week` evenly spaced
#' sessions starting at `start_week` (week 1 = week 1) and ending at
#' `end_week` inclusive. Each session gets pulse height `vol`.
build_session_events <- function(start_week,
                                 end_week,
                                 sessions_per_week,
                                 vol) {
  stopifnot(sessions_per_week >= 1, end_week >= start_week)
  spacing <- 1 / sessions_per_week
  weeks   <- seq(start_week, end_week, by = 1)
  offsets <- seq(0, 1 - spacing, by = spacing)
  times   <- as.numeric(outer(weeks, offsets, FUN = "+"))
  times   <- sort(times)
  heights <- rep(vol, length(times))
  list(times = times, heights = heights)
}

#' Parameter sensitivity sweep: simulate over a grid of
#' (adaptation_rate, Capacity) for the given training_fn and base params,
#' returning a tibble of final-Fitness per cell.
scenario_param_sweep <- function(adaptation_rates,
                                 capacities,
                                 base_params = default_params(),
                                 horizon = 48,
                                 dt = 0.0625,
                                 training_fn = NULL) {
  grid_df <- expand.grid(
    adaptation_rate = adaptation_rates,
    Capacity        = capacities
  )
  if (is.null(training_fn)) {
    sim_grid    <- seq(0, horizon, by = dt)
    training_fn <- scenario_standard(sim_grid, n_weeks = floor(horizon))
  }

  out <- vector("list", nrow(grid_df))
  for (i in seq_len(nrow(grid_df))) {
    p <- base_params
    p$adaptation_rate <- grid_df$adaptation_rate[i]
    p$Capacity        <- grid_df$Capacity[i]
    sim <- simulate_med(p,
                        horizon     = horizon,
                        dt          = dt,
                        method      = "lsoda",
                        training_fn = training_fn)
    out[[i]] <- tibble::tibble(
      adaptation_rate = grid_df$adaptation_rate[i],
      Capacity        = grid_df$Capacity[i],
      final_Fitness   = sim$Fitness[nrow(sim)],
      max_Fatigue     = max(sim$Fatigue),
      max_Signal      = max(sim$Signal)
    )
  }
  dplyr::bind_rows(out)
}
