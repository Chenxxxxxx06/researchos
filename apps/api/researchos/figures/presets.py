"""Versioned, allowlisted figure style presets.

Presets are code (not DB rows): hand-written rcParams dicts restricted to the
allowlisted keys below — fonts, sizes, spines, grid, legend, figure size/dpi,
colors — never arbitrary keys or code. Bumping a preset's ``version`` marks
figures rendered with the old version as ``style_outdated``.

Fonts are restricted to matplotlib's generic families (DejaVu is bundled) so
CI renders identically offline.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

DEFAULT_STYLE_SLUG = "clean-serif"

# The only rcParams keys a preset may set (documented allowlist).
ALLOWED_RCPARAM_KEYS: frozenset[str] = frozenset(
    {
        # fonts
        "font.family",
        "font.size",
        "axes.titlesize",
        "axes.labelsize",
        "xtick.labelsize",
        "ytick.labelsize",
        "legend.fontsize",
        # spines / axes
        "axes.spines.top",
        "axes.spines.right",
        "axes.spines.left",
        "axes.spines.bottom",
        "axes.linewidth",
        "axes.axisbelow",
        "axes.edgecolor",
        "axes.labelcolor",
        "axes.facecolor",
        # grid
        "axes.grid",
        "axes.grid.axis",
        "grid.alpha",
        "grid.linestyle",
        "grid.linewidth",
        "grid.color",
        # legend
        "legend.frameon",
        # figure geometry / output
        "figure.figsize",
        "figure.dpi",
        "savefig.dpi",
        "figure.facecolor",
        "savefig.facecolor",
        # marks
        "lines.linewidth",
        "lines.markersize",
        # colors / text (dark preset)
        "text.color",
        "xtick.color",
        "ytick.color",
        # series color cycle (reserved; palettes are applied by render.py)
        "axes.prop_cycle",
    }
)


@dataclass(frozen=True)
class StylePreset:
    slug: str
    version: str
    name: str
    description: str
    rcparams: Mapping[str, Any]
    palette: tuple[str, ...]
    # Drives the frontend SVG thumbnail "style" object.
    font_family: str = "serif"  # "serif" | "sans"
    grid: bool = True
    legend_frame: bool = False
    dpi: int = 200
    # Optional per-series mark differentiation (used by render.py, not rcparams).
    markers: tuple[str, ...] = field(default=())
    linestyles: tuple[str, ...] = field(default=())


_OKABE_ITO = ("#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")

PRESETS: dict[str, StylePreset] = {
    "clean-serif": StylePreset(
        slug="clean-serif",
        version="1.0.0",
        name="Clean serif",
        description="Serif text, thin open spines, muted palette, subtle y-grid.",
        rcparams={
            "font.family": "serif",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.alpha": 0.3,
            "grid.linestyle": "-",
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "legend.frameon": False,
            "figure.figsize": (6.0, 3.8),
            "lines.linewidth": 1.6,
        },
        palette=("#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"),
        font_family="serif",
        grid=True,
        legend_frame=False,
    ),
    "ieee": StylePreset(
        slug="ieee",
        version="1.0.0",
        name="IEEE",
        description="Compact single-column style: 8pt sans, grayscale-safe lines.",
        rcparams={
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.titlesize": 8,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.linewidth": 0.6,
            "axes.grid": False,
            "legend.frameon": True,
            "figure.figsize": (3.5, 2.4),
            "lines.linewidth": 1.0,
            "lines.markersize": 3.0,
        },
        palette=("#000000", "#4D4D4D", "#0072B2", "#D55E00", "#009E73", "#CC79A7"),
        font_family="sans",
        grid=False,
        legend_frame=True,
        linestyles=("-", "--", "-.", ":"),
    ),
    "nature": StylePreset(
        slug="nature",
        version="1.0.0",
        name="Nature",
        description="Compact sans style with the Okabe-Ito colorblind-safe palette.",
        rcparams={
            "font.family": "sans-serif",
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "legend.frameon": False,
            "figure.figsize": (4.6, 3.0),
            "lines.linewidth": 1.4,
        },
        palette=_OKABE_ITO,
        font_family="sans",
        grid=False,
        legend_frame=False,
    ),
    "dark": StylePreset(
        slug="dark",
        version="1.0.0",
        name="Dark",
        description="Dark background with vivid lines for slides.",
        rcparams={
            "font.family": "sans-serif",
            "font.size": 10,
            "figure.facecolor": "#111318",
            "savefig.facecolor": "#111318",
            "axes.facecolor": "#111318",
            "axes.edgecolor": "#C9D1D9",
            "axes.labelcolor": "#E6EDF3",
            "text.color": "#E6EDF3",
            "xtick.color": "#C9D1D9",
            "ytick.color": "#C9D1D9",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#30363D",
            "grid.alpha": 0.6,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "legend.frameon": False,
            "figure.figsize": (6.0, 3.8),
            "lines.linewidth": 1.8,
        },
        palette=("#58A6FF", "#F778BA", "#3FB950", "#D29922", "#BC8CFF", "#39C5CF"),
        font_family="sans",
        grid=True,
        legend_frame=False,
    ),
    "minimal-gray": StylePreset(
        slug="minimal-gray",
        version="1.0.0",
        name="Minimal gray",
        description="Grayscale only; markers differentiate series.",
        rcparams={
            "font.family": "sans-serif",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "legend.frameon": False,
            "figure.figsize": (5.2, 3.4),
            "lines.linewidth": 1.2,
            "lines.markersize": 4.0,
        },
        palette=("#111111", "#555555", "#888888", "#AAAAAA"),
        font_family="sans",
        grid=False,
        legend_frame=False,
        markers=("o", "s", "^", "D", "v", "P"),
    ),
}


def get_preset(slug: str | None) -> StylePreset:
    """Return the preset for ``slug``, falling back to the default preset."""

    if slug and slug in PRESETS:
        return PRESETS[slug]
    return PRESETS[DEFAULT_STYLE_SLUG]
