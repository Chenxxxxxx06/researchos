"""Pure matplotlib render core.

matplotlib is imported lazily inside the function (Agg backend, no GUI) so
API startup pays nothing. No DB or network access — inputs are resolved
series and a preset; output is raw SVG/PNG bytes. Determinism: fixed
``svg.hashsalt`` and no embedded creation date, so identical inputs produce
identical SVG bytes.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any, cast

from .presets import StylePreset

Point = tuple[float, float]


def render_figure_bytes(
    chart: str,
    series_data: Sequence[Sequence[Point]],
    labels: Sequence[str | None],
    opts: Mapping[str, Any],
    preset: StylePreset,
) -> dict[str, bytes]:
    """Render one figure; returns ``{"svg": ..., "png": ...}``."""

    import matplotlib

    matplotlib.use("Agg")  # idempotent; never touches a display
    import matplotlib.pyplot as plt

    rc = dict(preset.rcparams)
    rc["svg.hashsalt"] = "researchos"

    # matplotlib's rc_context stub wants a Literal-keyed dict; presets are
    # validated at registry definition time, so a cast is safe here.
    with matplotlib.rc_context(cast("Any", rc)):
        fig, ax = plt.subplots()
        try:
            _draw(ax, chart, series_data, labels, preset)
            if opts.get("y_scale") == "log":
                ax.set_yscale("log")
            if opts.get("title"):
                ax.set_title(str(opts["title"]))
            if opts.get("x_label"):
                ax.set_xlabel(str(opts["x_label"]))
            if opts.get("y_label"):
                ax.set_ylabel(str(opts["y_label"]))
            if opts.get("legend", True) and any(label for label in labels):
                ax.legend()

            svg_buf = io.BytesIO()
            fig.savefig(svg_buf, format="svg", metadata={"Date": None}, bbox_inches="tight")
            png_buf = io.BytesIO()
            fig.savefig(png_buf, format="png", dpi=preset.dpi, bbox_inches="tight")
        finally:
            plt.close(fig)

    return {"svg": svg_buf.getvalue(), "png": png_buf.getvalue()}


def _series_color(preset: StylePreset, index: int) -> str:
    return preset.palette[index % len(preset.palette)]


def _draw(
    ax: Any,
    chart: str,
    series_data: Sequence[Sequence[Point]],
    labels: Sequence[str | None],
    preset: StylePreset,
) -> None:
    if chart == "bar":
        _draw_bars(ax, series_data, labels, preset)
        return
    for i, points in enumerate(series_data):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        label = labels[i] if i < len(labels) else None
        color = _series_color(preset, i)
        if chart == "scatter":
            ax.scatter(xs, ys, label=label, color=color)
        else:  # line
            kwargs: dict[str, Any] = {}
            if preset.markers:
                kwargs["marker"] = preset.markers[i % len(preset.markers)]
            if preset.linestyles:
                kwargs["linestyle"] = preset.linestyles[i % len(preset.linestyles)]
            ax.plot(xs, ys, label=label, color=color, **kwargs)


def _draw_bars(
    ax: Any,
    series_data: Sequence[Sequence[Point]],
    labels: Sequence[str | None],
    preset: StylePreset,
) -> None:
    """Grouped bars over the (sorted) union of x values as categories."""

    categories = sorted({p[0] for points in series_data for p in points})
    positions = {x: idx for idx, x in enumerate(categories)}
    n = max(len(series_data), 1)
    width = 0.8 / n
    for i, points in enumerate(series_data):
        by_x = dict(points)
        xs = [positions[x] + (i - (n - 1) / 2) * width for x in categories if x in by_x]
        heights = [by_x[x] for x in categories if x in by_x]
        label = labels[i] if i < len(labels) else None
        ax.bar(xs, heights, width=width, label=label, color=_series_color(preset, i))
    ax.set_xticks(list(range(len(categories))))
    ax.set_xticklabels([_format_tick(x) for x in categories])


def _format_tick(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"
