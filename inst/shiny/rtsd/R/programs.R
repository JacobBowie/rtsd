#' Structured training program generators
#'
#' Builds event lists (`times`, `heights`) suitable for `pulse_from_events()`
#' from named periodization schemes. Each generator returns a tibble with
#' columns `time` (week) and `height` (TRIMP per session).
#'
#' Renaissance Periodization (RP) — Israetel et al. — frames training
#' volume on a per-muscle-group, per-week basis bounded by:
#'   MEV (Minimum Effective Volume)    : minimum sets/wk that produces gains
#'   MAV (Maximum Adaptive Volume)     : sets/wk that produces best gains
#'   MRV (Maximum Recoverable Volume)  : most sets/wk you can recover from
#'   MV  (Maintenance Volume)          : minimum to retain gains
#'
#' A standard RP mesocycle ramps weekly volume linearly from MEV to MRV
#' over 3-5 accumulation weeks, then deloads (~50% volume + lighter
#' intensity) for one week. Macrocycles chain mesocycles, often raising
#' the MEV floor across cycles ("MEV creep") to reflect rising work
#' tolerance.
#'
#' Conversion to TRIMP: one "set" is multiplied by `work_per_set` to get
#' a TRIMP-equivalent height. Default 80 is a typical leg-press
#' volume_load order of magnitude; tune as appropriate for the
#' population at hand.

#' Build an RP mesocycle event list
#'
#' Linear volume ramp MEV → MRV across `accumulation_weeks`, then a
#' `deload_weeks`-long deload at `deload_fraction` of MEV. Volume is
#' distributed evenly across `sessions_per_week`.
#'
#' @param start_week Week (in simulation grid units) at which the
#'   mesocycle begins. Default 1.
#' @param mev_sets Minimum Effective Volume in sets/week. Default 8
#'   (typical chest/quads MEV in RP guidance).
#' @param mrv_sets Maximum Recoverable Volume in sets/week. Default 18.
#' @param accumulation_weeks Length of the ramp phase. Default 4.
#' @param deload_weeks Length of the deload tail. Default 1.
#' @param sessions_per_week Distribution of weekly sets across sessions.
#'   Default 3.
#' @param work_per_set TRIMP-equivalent of one set. Default 80.
#' @param deload_fraction Deload weekly volume as fraction of MEV.
#'   Default 0.5.
#' @return tibble with columns `time` (weeks since simulation start)
#'   and `height` (TRIMP per session).
program_rp_mesocycle <- function(start_week        = 1,
                                 mev_sets          = 8,
                                 mrv_sets          = 18,
                                 accumulation_weeks = 4,
                                 deload_weeks      = 1,
                                 sessions_per_week = 3,
                                 work_per_set      = 80,
                                 deload_fraction   = 0.5) {
  stopifnot(mev_sets > 0, mrv_sets >= mev_sets,
            accumulation_weeks >= 1, deload_weeks >= 0,
            sessions_per_week >= 1, work_per_set > 0,
            deload_fraction >= 0, deload_fraction <= 1)

  weekly_sets <- c(
    seq(mev_sets, mrv_sets, length.out = accumulation_weeks),
    rep(mev_sets * deload_fraction, deload_weeks)
  )

  rows <- vector("list", length(weekly_sets) * sessions_per_week)
  i <- 1L
  for (w in seq_along(weekly_sets)) {
    sets_this_week <- weekly_sets[w]
    sets_per_session <- sets_this_week / sessions_per_week
    for (s in 0:(sessions_per_week - 1)) {
      rows[[i]] <- data.frame(
        time   = (start_week - 1) + (w - 1) + s / sessions_per_week,
        height = sets_per_session * work_per_set
      )
      i <- i + 1L
    }
  }
  do.call(rbind, rows)
}

#' Build an RP macrocycle by chaining mesocycles
#'
#' Stacks `n_mesocycles` consecutive RP mesocycles. Optionally raises
#' the MEV floor by `mev_creep_per_cycle` sets per mesocycle to reflect
#' rising work tolerance over a macrocycle.
#'
#' @param n_mesocycles Number of consecutive mesocycles. Default 3.
#' @param mev_creep_per_cycle Sets/week added to MEV (and MRV) at each
#'   subsequent mesocycle. Default 0 (constant MEV/MRV).
#' @param ... Passed to `program_rp_mesocycle()`.
#' @return tibble of (time, height) events spanning all mesocycles.
program_rp_macro <- function(start_week         = 1,
                             n_mesocycles       = 3,
                             accumulation_weeks = 4,
                             deload_weeks       = 1,
                             mev_sets           = 8,
                             mrv_sets           = 18,
                             mev_creep_per_cycle = 0,
                             ...) {
  meso_len <- accumulation_weeks + deload_weeks
  out <- vector("list", n_mesocycles)
  cur_week <- start_week
  for (m in seq_len(n_mesocycles)) {
    creep <- (m - 1) * mev_creep_per_cycle
    out[[m]] <- program_rp_mesocycle(
      start_week         = cur_week,
      mev_sets           = mev_sets + creep,
      mrv_sets           = mrv_sets + creep,
      accumulation_weeks = accumulation_weeks,
      deload_weeks       = deload_weeks,
      ...
    )
    cur_week <- cur_week + meso_len
  }
  do.call(rbind, out)
}

#' Make a training_fn for an RP program
#'
#' Wraps `program_rp_macro()` (or single mesocycle when `n_mesocycles=1`)
#' through `pulse_from_events()` and `make_training_fn()` so the result
#' drops into `simulate_med(training_fn = ...)`.
#'
#' @param grid Numeric vector of evaluation times (weeks).
#' @param ... Passed to `program_rp_macro()`.
#' @param width Per-session pulse width (default 1/7 week ≈ one day).
scenario_rp <- function(grid, ..., width = 1 / 7) {
  events <- program_rp_macro(...)
  schedule <- pulse_from_events(grid, events$time, events$height, width = width)
  make_training_fn(grid, schedule)
}

#' RP volume landmarks for major muscle groups (Israetel reference card)
#'
#' Per-muscle-group MEV/MAV/MRV in sets/week, drawn from RP published
#' guidance. Use as defaults / sanity checks; individual responses vary.
rp_landmarks <- function() {
  data.frame(
    muscle_group = c("Chest", "Back", "Quads", "Hamstrings", "Glutes",
                     "Shoulders", "Biceps", "Triceps", "Calves", "Abs"),
    MV  = c(4,  6,  6,  3,  0,  4,  5,  4,  6,  0),
    MEV = c(8, 10,  8,  6,  0,  8,  8,  6,  8,  0),
    MAV = c(14, 18, 14, 12, 12, 16, 14, 12, 12,  16),
    MRV = c(22, 25, 20, 20, 16, 26, 26, 18, 16,  25),
    stringsAsFactors = FALSE
  )
}
