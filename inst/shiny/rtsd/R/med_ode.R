#' MEDv4 secondary-signal fitness-fatigue ODE right-hand side
#'
#' Restructured from the original Vensim port:
#'   - tau_fatigue / tau_signal replace hardcoded /7*exp(2) and /14
#'   - adl_trimp provides baseline stimulus from activities of daily living
#'   - Performance = Fitness - alpha*Fatigue reported as shadow variable
#'
#' Three stocks: Fitness, Fatigue, Signal.
#' Continuous-time forcing via `parameters$training_fn(t)`.
#'
#' @param t Scalar current time.
#' @param state Named numeric vector: Fitness, Fatigue, Signal.
#' @param parameters List with elements:
#'   - `params`: list of model parameters (see `default_params()`)
#'   - `training_fn`: function(t) -> TRIMP value
#' @return deSolve-style list: derivatives plus diagnostic variables.
med_ode <- function(t, state, parameters) {
  Fitness <- state[["Fitness"]]
  Fatigue <- state[["Fatigue"]]
  Signal  <- state[["Signal"]]
  p       <- parameters$params

  prescribed_TRIMP <- parameters$training_fn(t)
  effective_TRIMP  <- prescribed_TRIMP + p$adl_trimp

  adaptation   <- (p$adaptation_rate * Signal)^2 / p$adaptation_delay
  frac_atrophy <- p$maximal_fractional_rate * (Fitness / p$Capacity)
  atrophy      <- abs(Fitness * frac_atrophy)
  recovery     <- Fatigue / p$tau_fatigue
  signal_loss  <- Signal^2 / p$tau_signal

  Performance  <- Fitness - p$alpha * Fatigue

  list(
    c(
      Fitness = adaptation - atrophy,
      Fatigue = effective_TRIMP - recovery,
      Signal  = effective_TRIMP - adaptation - signal_loss
    ),
    TRIMP        = prescribed_TRIMP,
    eff_TRIMP    = effective_TRIMP,
    adaptation   = adaptation,
    atrophy      = atrophy,
    recovery     = recovery,
    signal_loss  = signal_loss,
    Performance  = Performance
  )
}

#' MEDv4-LINEAR variant — the linear formulation of the MEDv4 ODE.
#'
#' This is the variant that won model selection on real RT data. The
#' ONLY differences from `med_ode()` above:
#'   - adaptation  = (ar * Signal) / adaptation_delay      [was square()]
#'   - signal_loss = Signal / tau_signal                   [was Signal^2 / tau_signal]
#'
#' Everything else identical. Use this when forward-simulating the linear form.
med_ode_linear <- function(t, state, parameters) {
  Fitness <- state[["Fitness"]]
  Fatigue <- state[["Fatigue"]]
  Signal  <- state[["Signal"]]
  p       <- parameters$params

  prescribed_TRIMP <- parameters$training_fn(t)
  effective_TRIMP  <- prescribed_TRIMP + (p$adl_trimp %||% 0)

  # LINEAR forms matching med_euler_linear.stan
  adaptation   <- (p$adaptation_rate * Signal) / p$adaptation_delay
  frac_atrophy <- (p$maximal_fractional_rate %||% p$max_frac_rate) * (Fitness / p$Capacity)
  atrophy      <- abs(Fitness * frac_atrophy)
  recovery     <- Fatigue / (p$tau_fatigue %||% (7 / exp(2)))
  signal_loss  <- Signal / (p$tau_signal %||% 14)

  Performance  <- Fitness - (p$alpha %||% 0) * Fatigue

  list(
    c(
      Fitness = adaptation - atrophy,
      Fatigue = effective_TRIMP - recovery,
      Signal  = effective_TRIMP - adaptation - signal_loss
    ),
    TRIMP        = prescribed_TRIMP,
    eff_TRIMP    = effective_TRIMP,
    adaptation   = adaptation,
    atrophy      = atrophy,
    recovery     = recovery,
    signal_loss  = signal_loss,
    Performance  = Performance
  )
}

`%||%` <- function(a, b) if (is.null(a)) b else a

#' Default parameter set for MEDv4
#'
#' Original Vensim values preserved. New parameters (tau_fatigue,
#' tau_signal, adl_trimp, alpha) default to values that produce
#' IDENTICAL dynamics to the original hardcoded version.
#' Forward-simulation probes found mfr=0.020 passes more scenarios —
#' override in scenario tests, not here (oracle test needs 0.029).
default_params <- function() {
  list(
    adaptation_rate         = 0.02,
    adaptation_delay        = 5,
    maximal_fractional_rate = 0.029,
    Capacity                = 200,
    Baseline                = 12.145,
    volume_load             = 81,
    frequency               = 3,
    tau_fatigue             = 7 / exp(2),
    tau_signal              = 14,
    adl_trimp               = 0,
    alpha                   = 0
  )
}

#' Corrected parameter set for MEDv4 (per forward-simulation audit)
#'
#' Based on parameter-grid probe, Ibata 2021 bounds, and ADL
#' calibration. Use for scenario testing and calibration.
#' Oracle test uses default_params() which matches Vensim.
corrected_params <- function() {
  p <- default_params()
  p$maximal_fractional_rate <- 0.020
  p$adl_trimp               <- 19
  p
}
