#!/usr/bin/env Rscript
# Golden-trajectory generator for the Python<->R parity gate.
#
# R is the authoritative reference: simulate_med() defaults to
# deSolve::ode(method = "euler"), which reproduces the Vensim/PySD oracle
# bit-exactly at dt = 0.0625. These goldens are committed; the Python parity
# test (tests/parity/test_parity.py) compares against them.
#
# Run in Docker (deSolve + jsonlite live in the image, not on the host):
#   docker compose run --rm parity-golden
#
# Reads the SAME tests/parity/cases.json the Python test reads, so inputs are
# identical by construction.

options(repos = c(CRAN = "https://cloud.r-project.org"))  # no-op if site repo set

suppressPackageStartupMessages({
  library(deSolve)
  library(jsonlite)
})

# CWD = repo root (Docker WORKDIR is /rtsd; pass --rm parity-golden from root).
root <- getwd()
source(file.path(root, "R", "med_ode.R"))
source(file.path(root, "R", "simulate.R"))
source(file.path(root, "R", "training_schedule.R"))

spec <- jsonlite::fromJSON(
  file.path(root, "tests", "parity", "cases.json"),
  simplifyVector = TRUE, simplifyDataFrame = FALSE
)
jp <- spec$params

golden_dir <- file.path(root, "tests", "parity", "golden")
dir.create(golden_dir, recursive = TRUE, showWarnings = FALSE)

# D1: Python param keys -> R param keys. The ONLY rename is
# max_frac_rate -> maximal_fractional_rate; everything else is shared.
make_r_params <- function(jp) {
  list(
    adaptation_rate         = jp$adaptation_rate,
    adaptation_delay        = jp$adaptation_delay,
    maximal_fractional_rate = jp$max_frac_rate,
    Capacity                = jp$Capacity,
    Baseline                = jp$Baseline,
    tau_fatigue             = jp$tau_fatigue,
    tau_signal              = jp$tau_signal,
    adl_trimp               = jp$adl_trimp,
    alpha                   = 0
  )
}

build_tfn <- function(case, grid) {
  f <- case$forcing
  if (f$type == "constant") {
    val <- as.numeric(f$value)
    force(val)
    function(t) val
  } else if (f$type == "events") {
    sched <- pulse_from_events(
      grid,
      as.numeric(f$times),
      as.numeric(f$heights),
      width = as.numeric(f$width)
    )
    make_training_fn(grid, sched)
  } else {
    stop("unknown forcing type: ", f$type)
  }
}

for (case in spec$cases) {
  p       <- make_r_params(jp)
  horizon <- as.numeric(case$horizon)
  dt      <- as.numeric(case$dt)
  grid    <- seq(0, horizon, by = dt)
  tfn     <- build_tfn(case, grid)

  sim <- simulate_med(
    params      = p,
    horizon     = horizon,
    dt          = dt,
    method      = "euler",
    training_fn = tfn,
    variant     = case$variant
  )

  out <- data.frame(
    time    = sim$time,
    Fitness = sim$Fitness,
    Fatigue = sim$Fatigue,
    Signal  = sim$Signal
  )
  fp <- file.path(golden_dir, paste0(case$name, ".csv"))
  write.csv(out, fp, row.names = FALSE)
  cat(sprintf(
    "wrote %-26s n=%4d final=[%.3f, %.3f, %.3f]\n",
    basename(fp), nrow(out),
    tail(out$Fitness, 1), tail(out$Fatigue, 1), tail(out$Signal, 1)
  ))
}
cat("golden generation complete (", length(spec$cases), "cases ).\n")
