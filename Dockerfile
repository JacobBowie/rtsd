# syntax=docker/dockerfile:1.7
#
# synthesim — reproducible R + Python runtime for the MEDv4 explorer.
#
# Three entrypoints share one image:
#   1. shiny    (port 3838)  — the R Shiny app
#   2. marimo   (port 2718)  — the marimo notebook (editable)
#   3. validate              — runs the 7-test reference-mode validator
#
# Build:    docker build -t synthesim .
# Default:  docker run --rm -p 3838:3838 synthesim   # Shiny on http://localhost:3838

FROM rocker/r-ver:4.5.2

# --- PPM as default repo, with binary dispatch ------------------------------
# Bake the Posit Package Manager URL + HTTPUserAgent override into
# Rprofile.site so every R invocation in this image (build-time installs and
# runtime shiny boot) inherits the binary-dispatch contract. Without the
# HTTPUserAgent header, PPM may silently fall back to source tarballs.
# rocker/r-ver:4.5.2 is built on Ubuntu noble; reverify before bumping.
RUN echo 'options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/noble/latest"))' \
      > /usr/local/lib/R/etc/Rprofile.site \
 && echo 'options(HTTPUserAgent = sprintf("R/%s R (%s)", getRversion(), paste(getRversion(), R.version$platform, R.version$arch, R.version$os)))' \
      >> /usr/local/lib/R/etc/Rprofile.site

# --- System deps (slim: no LaTeX, no GIS, no cmdstan) -----------------------
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      libcurl4-openssl-dev \
      libssl-dev \
      libxml2-dev \
      libfontconfig1-dev \
      libfreetype6-dev \
      libpng-dev \
      python3 \
      python3-pip \
      python3-venv \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- R packages -------------------------------------------------------------
# Repo + binary dispatch already wired via Rprofile.site above.
RUN R -e "install.packages(c('shiny', 'bslib', 'ggplot2', 'patchwork', \
                             'dplyr', 'tidyr', 'tibble', 'deSolve', \
                             'DiagrammeR')); \
          stopifnot(requireNamespace('shiny',       quietly = TRUE), \
                    requireNamespace('bslib',       quietly = TRUE), \
                    requireNamespace('ggplot2',     quietly = TRUE), \
                    requireNamespace('patchwork',   quietly = TRUE), \
                    requireNamespace('dplyr',       quietly = TRUE), \
                    requireNamespace('tidyr',       quietly = TRUE), \
                    requireNamespace('tibble',      quietly = TRUE), \
                    requireNamespace('deSolve',     quietly = TRUE), \
                    requireNamespace('DiagrammeR',  quietly = TRUE))"

# --- Python deps for the marimo notebook ------------------------------------
# Isolated venv avoids the PEP 668 --break-system-packages escape hatch.
# /opt/venv/bin is first on PATH, so `python3 -m marimo ...` resolves here.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --no-cache-dir \
      marimo \
      numpy \
      matplotlib

# --- Project ----------------------------------------------------------------
WORKDIR /synthesim
COPY . /synthesim

EXPOSE 3838 2718

# Default entrypoint = Shiny. Override via `docker run synthesim <command>`.
CMD ["R", "-e", "shiny::runApp('inst/shiny/synthesim', host = '0.0.0.0', port = 3838)"]
