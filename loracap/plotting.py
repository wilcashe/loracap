#!/usr/bin/env python3
"""
loracap.plotting
=========================

Two-panel DER-versus-nodes figure: the full range, plus a detail around the
operational threshold where the curves actually cross it.

The style is deliberately restrained. Curves are distinguished by greyscale
level, line style and marker together, so the figure survives being printed in
black and white, and colour is reserved for one highlighted scenario and for
the threshold reference line. That is the convention most journals' figures
follow, and it is what makes a multi-curve plot readable at column width.

matplotlib is the only dependency in the whole package, and only this module
needs it.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, ScalarFormatter

from .analysis import crossing, group_by_scenario
from .study import Study, output_dir

LINESTYLES = ["-", "--", ":", "-.", (0, (3, 1, 1, 1)), (0, (5, 1)), (0, (1, 1))]
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]
GREYS = ["0.15", "0.40", "0.60", "0.0", "0.50", "0.70", "0.30"]
THRESHOLD_COLOR = "#c0392b"


def _nice_log_ticks(lo, hi):
    """Plain-number ticks (5, 10, 20, 50, ...) instead of 10^1, 10^2, which are
    hard to read when the interesting range spans less than two decades."""
    candidates = [1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 70, 100, 150, 200, 300,
                  500, 700, 1000, 2000, 5000, 10000]
    return [c for c in candidates if lo <= c <= hi]


def _build_style(scenarios, highlight, highlight_color):
    style = {}
    grey_i = 0
    for i, scen in enumerate(scenarios):
        if scen == highlight:
            color = highlight_color
        else:
            color = GREYS[grey_i % len(GREYS)]
            grey_i += 1
        style[scen] = {
            "color": color,
            "ls": LINESTYLES[i % len(LINESTYLES)],
            "marker": MARKERS[i % len(MARKERS)],
        }
    return style


def _style_axis(ax, xlim, ylim, threshold):
    ax.axhline(threshold, color=THRESHOLD_COLOR, linewidth=1.3, linestyle="--", zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel("Number of nodes")
    ax.grid(True, which="major", linestyle="--", linewidth=0.6, color="0.85", zorder=0)
    ax.grid(True, which="minor", linestyle="--", linewidth=0.4, color="0.92", zorder=0)
    ax.xaxis.set_major_locator(FixedLocator(_nice_log_ticks(*xlim)))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_axisbelow(True)


def plot_study(study: Study, rows, root=None, formats=("pdf", "svg", "png")):
    by = group_by_scenario(rows)
    scenarios = [s for s in study.scenarios if s in by]
    style = _build_style(scenarios, study.highlight_scenario, study.highlight_color)
    th = study.der_threshold

    crossings = {}
    for scen in scenarios:
        rs = by[scen]
        crossings[scen] = crossing(
            [r["n_nodes"] for r in rs], [r["der_mean"] for r in rs], th
        )

    full_xlim = study.plot_full_xlim or (min(study.node_counts), max(study.node_counts))
    if study.plot_zoom_xlim:
        zoom_xlim = study.plot_zoom_xlim
    else:
        found = [c for c in crossings.values() if c]
        if found:
            zoom_xlim = (max(1, min(found) * 0.5), max(found) * 2.0)
        else:
            zoom_xlim = full_xlim

    plt.rcParams.update({
        "font.size": 12, "axes.labelsize": 12, "legend.fontsize": 9.5,
        "xtick.labelsize": 11, "ytick.labelsize": 11,
    })
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))

    for scen in scenarios:
        rs = by[scen]
        ns = [r["n_nodes"] for r in rs]
        mean = [r["der_mean"] for r in rs]
        std = [r["der_std"] for r in rs]
        s = style[scen]
        for ax in axes:
            ax.plot(ns, mean, color=s["color"], linestyle=s["ls"], marker=s["marker"],
                    markersize=4.5, markevery=2, linewidth=1.7, label=scen)
            ax.fill_between(ns, [m - d for m, d in zip(mean, std)],
                            [m + d for m, d in zip(mean, std)],
                            color=s["color"], alpha=0.15, linewidth=0)

    ax = axes[0]
    _style_axis(ax, full_xlim, (0, 1.02), th)
    ax.set_ylabel("Data Extraction Rate (DER)")
    ax.text(full_xlim[0] * 1.08, th - 0.035, f"DER = {th:g} threshold",
            fontsize=10, va="top", color=THRESHOLD_COLOR)
    ax.legend(loc="lower left", frameon=True, framealpha=0.9)

    ax = axes[1]
    _style_axis(ax, zoom_xlim, study.plot_zoom_ylim, th)
    y0 = study.plot_zoom_ylim[0]
    for i, scen in enumerate(scenarios):
        xc = crossings[scen]
        if not xc:
            continue
        ax.axvline(xc, color=style[scen]["color"], linewidth=0.9,
                   linestyle=":", alpha=0.8, zorder=1)
        # stagger labels vertically so adjacent crossings do not overprint
        ax.annotate(f"{xc:.0f}", xy=(xc, y0 + 0.004 + 0.022 * (i % 2)),
                    color="0.15", fontsize=9.5, ha="center", fontweight="bold")

    fig.text(0.27, -0.02, "(a)", ha="center", fontsize=12)
    fig.text(0.775, -0.02, "(b)", ha="center", fontsize=12)
    fig.tight_layout()

    out = output_dir(study.name, root)
    base = os.path.join(out, study.figure_basename)
    written = []
    for ext in formats:
        path = f"{base}.{ext}"
        fig.savefig(path, bbox_inches="tight", dpi=200 if ext == "png" else None)
        written.append(path)
    plt.close(fig)
    return written
