"""Pure render-core and preset-registry tests (no DB, no network)."""

from __future__ import annotations

import re

import pytest

from researchos.figures.presets import (
    ALLOWED_RCPARAM_KEYS,
    DEFAULT_STYLE_SLUG,
    PRESETS,
    get_preset,
)
from researchos.figures.render import render_figure_bytes

SERIES = [[(0.0, 0.1), (1.0, 0.4), (2.0, 0.3)], [(0.0, 0.2), (1.0, 0.1), (2.0, 0.5)]]
LABELS = ["baseline", "ours"]
OPTS = {"title": "t", "x_label": "x", "y_label": "y", "legend": True, "y_scale": "linear"}


@pytest.mark.parametrize("chart", ["line", "bar", "scatter"])
@pytest.mark.parametrize("slug", ["clean-serif", "ieee"])
def test_render_produces_svg_and_png(chart: str, slug: str) -> None:
    out = render_figure_bytes(chart, SERIES, LABELS, OPTS, PRESETS[slug])
    assert set(out) == {"svg", "png"}
    assert out["svg"].startswith(b"<?xml") or out["svg"].lstrip().startswith(b"<svg")
    assert out["png"].startswith(b"\x89PNG")
    assert len(out["svg"]) > 0 and len(out["png"]) > 0


def test_render_is_deterministic_for_svg() -> None:
    first = render_figure_bytes("line", SERIES, LABELS, OPTS, PRESETS["clean-serif"])
    second = render_figure_bytes("line", SERIES, LABELS, OPTS, PRESETS["clean-serif"])
    assert first["svg"] == second["svg"]


def test_log_scale_and_missing_labels() -> None:
    out = render_figure_bytes(
        "line",
        [[(0.0, 1.0), (1.0, 10.0)]],
        [None],
        {"legend": True, "y_scale": "log"},
        PRESETS["dark"],
    )
    assert out["svg"]


def test_preset_registry_invariants() -> None:
    assert set(PRESETS) == {"clean-serif", "ieee", "nature", "dark", "minimal-gray"}
    semver = re.compile(r"^\d+\.\d+\.\d+$")
    for slug, preset in PRESETS.items():
        assert preset.slug == slug  # dict key mirrors the slug
        assert semver.match(preset.version), slug
        assert preset.palette, slug
        assert preset.font_family in ("serif", "sans"), slug
        # rcparams restricted to the documented allowlist; no code, no surprises.
        assert set(preset.rcparams) <= ALLOWED_RCPARAM_KEYS, slug
        assert preset.dpi > 0


def test_get_preset_falls_back_to_default() -> None:
    assert get_preset(None).slug == DEFAULT_STYLE_SLUG
    assert get_preset("no-such-style").slug == DEFAULT_STYLE_SLUG
    assert get_preset("ieee").slug == "ieee"
