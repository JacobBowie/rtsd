# tests/validate_reference_modes.R
#
# Runs the RT reference-mode validation suite against the MEDv4-linear
# parameterization. Purpose: verify the simulator reproduces canonical
# RT dynamics across 7 forward-simulation scenarios. Runs in seconds.
#
# Usage (any R 4.x):
#   Rscript tests/validate_reference_modes.R

suppressPackageStartupMessages({
  library(ggplot2)
})

source("R/reference_mode_tests.R")
source("R/theme_rtsd_prism.R")   # Prism theme mirrored from python/rtsd/rtsd.py

cat("=== Reference-mode validation suite:",
    format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "===\n")
cat("    See R/reference_mode_tests.R for the per-test definitions.\n\n")

# ---- Run the suite under v2 defaults (ADL enabled) -------------------------
results <- run_reference_mode_tests()

# Pretty-print
cat("Results (v2 params, alpha=1.5, adl_trimp=100):\n")
for (i in seq_len(nrow(results))) {
  r <- results[i, ]
  marker <- if (r$status == "PASS") "[PASS]" else "[FAIL]"
  cat(sprintf("%s %-32s | %s\n", marker, r$name, r$metric))
  cat(sprintf("         expected: %s\n", r$expected))
  cat(sprintf("         citation: %s\n\n", r$citation))
}

n_pass <- sum(results$status == "PASS")
cat(sprintf("SUMMARY: %d/%d passed\n\n", n_pass, nrow(results)))

# ---- Save artifacts --------------------------------------------------------
out_dir <- "data/validation/reference_modes"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
saveRDS(results, file.path(out_dir, "results.rds"))
write.csv(results, file.path(out_dir, "results.csv"), row.names = FALSE)

# ---- Illustrative plots for key tests --------------------------------------
# Styled with theme_rtsd_prism() (R/theme_rtsd_prism.R), the R mirror of the
# dashboard's Prism Altair theme. Series are labelled directly at the line
# (no legend box). Color roles: blue (Fitness stock color) = the reference
# condition; orange (dashboard snapshot palette) = the manipulated/compared
# condition.
col_ref  <- RTSD_STOCK_COLORS[["Fitness"]]   # #1565C0
col_alt  <- RTSD_SNAP_PALETTE[3]             # #EF6C00
lw_data  <- rtsd_linewidth(3)                # Altair line.strokeWidth = 3
lw_guide <- rtsd_linewidth(1.5)              # reference lines
lab_size <- 12 / .pt                         # 12 pt direct labels (geom size is mm)
lab_font <- "Arial"
fig_device <- if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else "png"

save_fig <- function(plot, file) {
  ggsave(file.path(out_dir, file), plot, device = fig_device,
         width = 7, height = 4, dpi = 150, bg = "white")
}

# RM1: side-by-side dose response
p1_low  <- weekly_pulses(52, 2000)
p1_high <- weekly_pulses(52, 4000)
s_low  <- simulate_medv4(p1_low$times,  p1_low$heights,
                         params = default_params_v2(), baseline = 80, t_end = 52)
s_high <- simulate_medv4(p1_high$times, p1_high$heights,
                         params = default_params_v2(), baseline = 80, t_end = 52)
s_low$dose  <- "1× dose"
s_high$dose <- "2× dose"
df_rm1 <- rbind(s_low, s_high)
end_rm1 <- do.call(rbind, lapply(split(df_rm1, df_rm1$dose), function(d) d[nrow(d), ]))

p_rm1 <- ggplot(df_rm1, aes(t, Fitness, color = dose)) +
  geom_line(linewidth = lw_data, lineend = "round") +
  geom_text(data = end_rm1, aes(label = dose), hjust = 0, nudge_x = 1,
            size = lab_size, family = lab_font, fontface = "bold") +
  scale_color_manual(values = c("1× dose" = col_ref, "2× dose" = col_alt)) +
  scale_x_continuous(breaks = seq(0, 52, by = 13)) +   # quarter-years
  coord_cartesian(clip = "off") +
  labs(title = "RM1: dose-response (Schoenfeld 2017)",
       subtitle = "2× training stimulus should produce ~2× rate of gain",
       x = "Week", y = "Fitness (kg)") +
  theme_rtsd_prism() +
  theme(legend.position = "none",
        plot.margin = margin(10, 80, 8, 8))
save_fig(p_rm1, "RM1_dose_response.png")

# RM4: detraining curve
p4 <- weekly_pulses(104, 2000)
s_det <- simulate_medv4(p4$times, p4$heights,
                        params = default_params_v2(), baseline = 80, t_end = 156)
s_det$phase <- ifelse(s_det$t <= 104, "Training", "Detraining")
# Phase labels flank the training/cessation divider, below the trajectory.
lab_rm4 <- data.frame(t = c(104 - 3, 104 + 3), Fitness = 85,
                      phase = c("Training", "Detraining"), hjust = c(1, 0))
p_rm4 <- ggplot(s_det, aes(t, Fitness, color = phase)) +
  geom_vline(xintercept = 104, linetype = "dotted", colour = "grey35",
             linewidth = lw_guide) +
  geom_line(linewidth = lw_data, lineend = "round") +
  geom_text(data = lab_rm4, aes(label = phase, hjust = hjust),
            size = lab_size, family = lab_font, fontface = "bold") +
  scale_color_manual(values = c(Training = col_ref, Detraining = col_alt)) +
  scale_x_continuous(breaks = seq(0, 156, by = 26)) +  # half-years
  coord_cartesian(clip = "off") +
  labs(title = "RM4: detraining (Mujika & Padilla 2000; Bickel/Bamman 2011)",
       subtitle = "104wk training + 52wk cessation; expect gradual decay toward baseline",
       x = "Week", y = "Fitness (kg)") +
  theme_rtsd_prism() +
  theme(legend.position = "none")
save_fig(p_rm4, "RM4_detraining.png")

# RM5: ADL floor comparison (v1 vs v2)
s_noadl <- simulate_medv4(numeric(0), numeric(0), params = default_params_v1(),
                          baseline = 80, t_end = 104, signal_0 = 100)
s_adl   <- simulate_medv4(numeric(0), numeric(0), params = default_params_v2(),
                          baseline = 80, t_end = 104, signal_0 = 100)
s_noadl$model <- "v1"; s_adl$model <- "v2"
df_rm5 <- rbind(s_noadl, s_adl)
end_rm5 <- do.call(rbind, lapply(split(df_rm5, df_rm5$model), function(d) d[nrow(d), ]))
end_rm5$line1 <- c(v1 = "v1: adl=0", v2 = "v2: adl=100")[end_rm5$model]
end_rm5$line2 <- c(v1 = "C=50", v2 = "C=1.5×baseline")[end_rm5$model]
p_rm5 <- ggplot(df_rm5, aes(t, Fitness, color = model)) +
  geom_hline(yintercept = 80, linetype = "dashed", colour = "grey35",
             linewidth = lw_guide) +
  geom_line(linewidth = lw_data, lineend = "round") +
  geom_text(data = end_rm5, aes(label = line1), hjust = 0, vjust = -0.15,
            nudge_x = 2, size = lab_size, family = lab_font, fontface = "bold") +
  geom_text(data = end_rm5, aes(label = line2), hjust = 0, vjust = 1.15,
            nudge_x = 2, size = lab_size, family = lab_font) +
  annotate("text", x = 52, y = 80, label = "Baseline (80 kg)", vjust = -0.5,
           colour = "grey35", size = lab_size * 11 / 12, family = lab_font) +
  scale_color_manual(values = c(v1 = col_alt, v2 = col_ref)) +
  scale_x_continuous(breaks = seq(0, 104, by = 26)) +  # half-years
  scale_y_continuous(limits = c(15, 86), breaks = seq(20, 80, by = 20)) +
  coord_cartesian(clip = "off") +
  labs(title = "RM5: ADL floor (Thom 2005; LeBlanc 2000)",
       subtitle = "No training; only environmental stimulus. Only microgravity (adl=0) should give full decay.",
       x = "Week", y = "Fitness (kg)") +
  theme_rtsd_prism() +
  theme(legend.position = "none",
        plot.margin = margin(10, 125, 8, 8))
save_fig(p_rm5, "RM5_adl_floor.png")

cat("Artifacts in", out_dir, ":\n")
print(list.files(out_dir))
cat("=== Done at", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "===\n")
