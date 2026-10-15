#!/usr/bin/env python3
# Reproducible build: `uv run --script build_wasm.py --export` provisions
# marimo==0.23.3, which pins Pyodide 0.27.5 (→ Altair 5.4.1) in the exported WASM
# bundle. Plain `python build_wasm.py` still works but uses whatever marimo is on
# PATH — only the pinned invocation guarantees the deploy's runtime stack. See CLAUDE.md.
# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo==0.23.3"]
# ///
"""Build a self-contained, WASM-exportable copy of the rtSD Explorer notebook.

`marimo export html-wasm` bundles ONLY the notebook file — it does NOT include
sibling local modules (`model.py`, `sd_diagram.py`); see marimo issue #5488
(open as of v0.23.8). A raw export therefore throws `ModuleNotFoundError` in the
browser.

marimo does NOT execute top-level (non-cell) code before cells (verified), so
the inlining must be a *cell* whose output the import cells depend on. This
script produces `build/rtsd_wasm.py`:

  1. inserts a `_bootstrap` cell that decodes the inlined modules (base64) and
     registers them in `sys.modules`, returning a `_boot` sentinel;
  2. injects `_boot` into the signatures of the cells that import the local
     modules (`_model`, `_scenarios`, `_diagram`), forcing them to run after
     the bootstrap.

The notebook's `from model import ...` / `from sd_diagram import ...` then
resolve under Pyodide with no other edits. After export, a loading card is
injected into `index.html` (see LOADER_HTML) so the 30-60 s Pyodide boot does
not read as a blank page.

Usage (reproducible — pins marimo 0.23.3 → Pyodide 0.27.5 → Altair 5.4.1):
    uv run --script build_wasm.py            # write build/rtsd_wasm.py
    uv run --script build_wasm.py --export   # also run `marimo export html-wasm`

Plain `python build_wasm.py [--export]` also works but uses the marimo on PATH.

Edit rtsd.py / model.py / sd_diagram.py — NEVER the generated build file.
"""

import base64
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
APP_MARKER = "app = marimo.App"

# Cells that import a local module -> inject the _boot sentinel into their
# signature so marimo schedules them after _bootstrap.
SIGNATURE_PATCHES = {
    "def _model():": "def _model(_boot):",
    "def _scenarios():": "def _scenarios(_boot):",
    "def _diagram(plt):": "def _diagram(_boot, plt):",
}


# Loading cue injected into the exported index.html. marimo's WASM page is an
# empty <div id="root"> until Pyodide boots and the notebook runs (30-60 s on a
# first visit), which reads as a broken page. The card removes itself when the
# notebook's header (.rtsd-header, rendered by the _outputs cell, so after the
# charts) appears; the search also walks shadow roots in case marimo renders
# outputs inside one. Failsafes so it can never trap a visitor: tap to dismiss,
# and a hard timeout.
LOADER_HTML = """
    <div id="rtsd-loading" role="status" aria-live="polite" title="Tap to dismiss">
      <div class="rtsd-loading-card">
        <div class="rtsd-spinner" aria-hidden="true"></div>
        <p class="rtsd-loading-title">Loading the rtSD Explorer</p>
        <p class="rtsd-loading-note">The model runs in Python inside your browser,
        so the first load takes 30 to 60 seconds.</p>
      </div>
    </div>
    <style>
      #rtsd-loading { position: fixed; inset: 0; z-index: 10000; display: flex;
        align-items: center; justify-content: center; padding: 16px;
        background: #ffffff; transition: opacity 0.4s ease; cursor: pointer;
        font-family: Arial, system-ui, sans-serif; color: #111111; }
      #rtsd-loading.rtsd-done { opacity: 0; pointer-events: none; }
      .rtsd-loading-card { max-width: 340px; text-align: center; }
      .rtsd-spinner { width: 36px; height: 36px; margin: 0 auto 16px;
        border: 4px solid #e3e3e3; border-top-color: #1565C0; border-radius: 50%;
        animation: rtsd-spin 0.9s linear infinite; }
      .rtsd-loading-title { font-size: 18px; font-weight: bold; margin: 0 0 8px; }
      .rtsd-loading-note { font-size: 14px; line-height: 1.45; color: #444444; margin: 0; }
      @keyframes rtsd-spin { to { transform: rotate(360deg); } }
      @media (prefers-reduced-motion: reduce) { .rtsd-spinner { animation: none; } }
    </style>
    <script>
      (function () {
        var el = document.getElementById("rtsd-loading");
        var started = Date.now();
        function deepFind(root, sel) {
          if (root.querySelector && root.querySelector(sel)) return true;
          var nodes = root.querySelectorAll ? root.querySelectorAll("*") : [];
          for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].shadowRoot && deepFind(nodes[i].shadowRoot, sel)) return true;
          }
          return false;
        }
        function done() {
          clearInterval(timer);
          el.classList.add("rtsd-done");
          setTimeout(function () { el.remove(); }, 500);
        }
        el.addEventListener("click", done);
        var timer = setInterval(function () {
          if (deepFind(document, ".rtsd-header") || Date.now() - started > 150000) done();
        }, 500);
      })();
    </script>
"""


def _inject_loader(index_html: Path) -> None:
    html = index_html.read_text(encoding="utf-8")
    if html.count("</body>") != 1:
        raise SystemExit("expected exactly one </body> in the exported index.html")
    index_html.write_text(html.replace("</body>", LOADER_HTML + "  </body>"), encoding="utf-8")


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _bootstrap_cell() -> str:
    inlined = {"model": _b64(HERE / "model.py"), "sd_diagram": _b64(HERE / "sd_diagram.py")}
    return (
        "@app.cell\n"
        "def _bootstrap():\n"
        '    """Generated by build_wasm.py: register inlined local modules in\n'
        "    sys.modules so `from model import ...` / `from sd_diagram import ...`\n"
        "    resolve under WASM/Pyodide, where export does not bundle sibling files.\n"
        "    Returns `_boot`, which the import cells depend on (ordering).\"\"\"\n"
        "    import sys as _sys, types as _types, base64 as _b64\n\n"
        f"    _INLINED = {inlined!r}\n\n"
        "    def _register_inlined(_name, _src_b64):\n"
        "        _src = _b64.b64decode(_src_b64).decode('utf-8')\n"
        "        _m = _types.ModuleType(_name)\n"
        "        _m.__file__ = _name + '.py'\n"
        "        exec(compile(_src, _name + '.py', 'exec'), _m.__dict__)\n"
        "        _sys.modules[_name] = _m\n\n"
        "    for _n, _s in _INLINED.items():\n"
        "        _register_inlined(_n, _s)\n"
        "    _boot = True\n"
        "    return (_boot,)\n"
    )


def build() -> Path:
    nb = (HERE / "rtsd.py").read_text(encoding="utf-8")

    # 0. Strip the PEP 723 inline-deps block (the leading comment block + script
    #    metadata; see rtsd.py header). It pins marimo for `marimo edit --sandbox`
    #    and `uv run` builds, but must NOT ride into the export input: `marimo
    #    export html-wasm` detects inlined deps and prompts for a sandbox, which
    #    aborts a non-interactive build. The browser resolves packages from
    #    marimo's import auto-detection, not this block.
    nb = re.sub(r"\A(?:#.*\n)*?# /// script\n(?:#.*\n)*?# ///\n", "", nb, count=1)

    # 1. Insert the bootstrap cell right after the App() line.
    out, inserted = [], False
    for line in nb.splitlines(keepends=True):
        out.append(line)
        if not inserted and line.startswith(APP_MARKER):
            out.append("\n\n" + _bootstrap_cell())
            inserted = True
    if not inserted:
        raise SystemExit(f"could not find '{APP_MARKER}' line to insert the bootstrap")
    text = "".join(out)

    # 2. Inject _boot into the import cells' signatures.
    for old, new in SIGNATURE_PATCHES.items():
        if old not in text:
            raise SystemExit(f"signature to patch not found: {old!r}")
        text = text.replace(old, new, 1)

    BUILD.mkdir(exist_ok=True)
    target = BUILD / "rtsd_wasm.py"
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target}  ({target.stat().st_size // 1024} KB)")
    return target


def export(target: Path) -> None:
    out_dir = BUILD / "wasm"
    # Clean first so the bundle contains ONLY this export's output — no stale
    # files (e.g. a leftover CLAUDE.md) leaking into the deploy tarball.
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "marimo", "export", "html-wasm",
        str(target), "-o", str(out_dir / "index.html"), "--mode", "run",
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    # marimo's html-wasm export copies its bundled app assets (favicons,
    # manifest, logo) into the output AND sweeps in a stray CLAUDE.md from its
    # template; drop it so the deploy bundle/tarball is clean.
    stray = out_dir / "CLAUDE.md"
    if stray.exists():
        stray.unlink()
    _inject_loader(out_dir / "index.html")
    print(f"WASM bundle written to {out_dir}/ (with loading cue)")


if __name__ == "__main__":
    t = build()
    if "--export" in sys.argv:
        export(t)
