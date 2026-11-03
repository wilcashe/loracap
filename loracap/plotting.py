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

import math
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


def plot_validation(study: Study, ladder, root=None, formats=("pdf", "svg", "png"),
                    out_dir=None):
    """The degeneracy ladder, in the two views that say different things.

    Panel (a) is DER against node count: each rung removes one mechanism the
    pure-ALOHA bound does not have, and the curves walk down onto the bound.
    The vertical distance between two neighbouring curves is what that
    mechanism is worth in this deployment.

    Panel (b) is the same runs on the axes the medium-access literature has
    used since 1970: normalised throughput against offered load, over the
    canonical S = G*exp(-2G). The fully degenerate rung should sit on that
    curve. The full model sits well above it, and that gap is the whole point
    of the figure, because it is what LoRa buys over ALOHA.

    Offered load is normalised per channel at one channel throughout, so every
    series shares an x axis and the comparison is like for like.

    A lock-rule ladder also carries the first-come runs. They are drawn as
    unjoined hollow markers over their own bound, exp(-G), in the reference
    colour with a dotted line, so the two bounds share a colour as references
    and are told apart by line style and by the legend, which survives a
    greyscale print.
    """
    import math

    labels = ladder["rung_labels"]
    rows = ladder["rows"]
    ns = [r["n_nodes"] for r in rows]
    gs = [r["offered_load"] for r in rows]

    style = {}
    grey_i = 0
    for i, lab in enumerate(labels):
        if i == 0:
            color = study.highlight_color
        else:
            color = GREYS[grey_i % len(GREYS)]
            grey_i += 1
        style[lab] = {"color": color, "ls": LINESTYLES[i % len(LINESTYLES)],
                      "marker": MARKERS[i % len(MARKERS)]}

    plt.rcParams.update({
        "font.size": 12, "axes.labelsize": 12, "legend.fontsize": 9,
        "xtick.labelsize": 11, "ytick.labelsize": 11,
    })
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))

    # ---- (a) DER against N, one curve per rung, bound dashed ----
    ax = axes[0]
    # Drawn most-degenerate first so the full model ends up on top. Where a
    # mechanism does not bind, two rungs coincide exactly, and without this
    # the curve that matters is the one hidden underneath.
    handles = {}
    for lab in reversed(labels):
        s = style[lab]
        handles[lab], = ax.plot(
            ns, [r["rungs"][lab]["der_mean"] for r in rows],
            color=s["color"], linestyle=s["ls"], marker=s["marker"],
            markersize=4.5, linewidth=1.7, label=lab)
    bound, = ax.plot(ns, [r["aloha_der"] for r in rows], color=THRESHOLD_COLOR,
                     linestyle="--", linewidth=1.5, label="pure ALOHA, exp(-2G)")
    lock = all("lock_bound" in r for r in rows)
    extra_h, extra_l = [], []
    if lock:
        lb_line, = ax.plot(ns, [r["lock_bound"]["bound"] for r in rows],
                           color=THRESHOLD_COLOR, linestyle=":", linewidth=1.8)
        lb_pts, = ax.plot(ns, [r["lock_bound"]["der_mean"] for r in rows],
                          linestyle="none", marker="o", markersize=7,
                          markerfacecolor="white", markeredgecolor="0.1",
                          markeredgewidth=1.3, clip_on=False, zorder=5)
        extra_h = [lb_pts, lb_line]
        extra_l = ["first-come (lock, bare)", "first-come bound, exp(-G)"]
    ax.set_xscale("log")
    ax.set_xlim(min(ns), max(ns))
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Number of nodes")
    ax.set_ylabel("Data Extraction Rate (DER)")
    ax.grid(True, which="major", linestyle="--", linewidth=0.6, color="0.85", zorder=0)
    ax.grid(True, which="minor", linestyle="--", linewidth=0.4, color="0.92", zorder=0)
    ax.xaxis.set_major_locator(FixedLocator(_nice_log_ticks(min(ns), max(ns))))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_axisbelow(True)
    # Legend in ladder order, which is the order the rungs are meant to be
    # read in, not the order they were drawn.
    ax.legend([handles[l] for l in labels] + [bound] + extra_h,
              labels + ["pure ALOHA, exp(-2G)"] + extra_l,
              loc="lower left", frameon=True, framealpha=0.9)

    # ---- (b) throughput against offered load, over the ALOHA curve ----
    ax = axes[1]
    g_hi = max(gs) * 1.05
    grid = [g_hi * i / 200.0 for i in range(1, 201)]
    ax.plot(grid, [g * math.exp(-2 * g) for g in grid], color=THRESHOLD_COLOR,
            linestyle="--", linewidth=1.5, label="S = G exp(-2G)")
    if lock:
        ax.plot(grid, [g * math.exp(-g) for g in grid], color=THRESHOLD_COLOR,
                linestyle=":", linewidth=1.8, label="S = G exp(-G)")
        ax.plot(gs, [g * r["lock_bound"]["der_mean"] for g, r in zip(gs, rows)],
                linestyle="none", marker="o", markersize=7,
                markerfacecolor="white", markeredgecolor="0.1",
                markeredgewidth=1.3, clip_on=False, zorder=5,
                label="first-come (lock, bare)")
    for lab in (labels[0], labels[-1]):
        s = style[lab]
        ax.plot(gs, [g * r["rungs"][lab]["der_mean"] for g, r in zip(gs, rows)],
                color=s["color"], linestyle=s["ls"], marker=s["marker"],
                markersize=4.5, linewidth=1.7, label=lab)
    ax.set_xlim(0, g_hi)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Offered load G (packets per packet duration)")
    ax.set_ylabel("Normalised throughput S")
    ax.grid(True, which="major", linestyle="--", linewidth=0.6, color="0.85", zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=True, framealpha=0.9)

    fig.text(0.27, -0.02, "(a)", ha="center", fontsize=12)
    fig.text(0.775, -0.02, "(b)", ha="center", fontsize=12)
    fig.tight_layout()

    out = out_dir or output_dir(study.name, root)
    os.makedirs(out, exist_ok=True)
    base = os.path.join(out, f"{study.figure_basename}_validation")
    written = []
    for ext in formats:
        path = f"{base}.{ext}"
        fig.savefig(path, bbox_inches="tight", dpi=200 if ext == "png" else None)
        written.append(path)
    plt.close(fig)
    return written


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


MARK_COLOR = "0.30"


def _draw_marks(ax, marks, xlim, ylim):
    """Reference node counts as labelled vertical lines. Returns the marks
    drawn, so a test can check that one outside the axis is left out rather
    than drawn at the edge, where it would read as a value it is not.

    Every mark shares one line style and is told apart by its label, which
    is written along the line in text ink: a mark is a number to read the
    curve against, not a series, so it gets no colour of its own.
    """
    drawn = []
    for x, label in marks:
        if not (xlim[0] <= x <= xlim[1]):
            continue
        ax.axvline(x, color=MARK_COLOR, linewidth=1.0, linestyle="-.",
                   zorder=1)
        # Written upward from near the floor, where a falling DER curve has
        # already left, and clear of the crossing labels on the floor itself.
        ax.text(x * 1.02, ylim[0] + 0.09 * (ylim[1] - ylim[0]),
                f"{label} ({x:g})", rotation=90, ha="left", va="bottom",
                fontsize=8.5, color="0.15")
        drawn.append((x, label))
    return drawn


def _save(fig, base, formats):
    written = []
    for ext in formats:
        path = f"{base}.{ext}"
        fig.savefig(path, bbox_inches="tight", dpi=200 if ext == "png" else None)
        written.append(path)
    plt.close(fig)
    return written


def study_figure(study: Study, rows, marks=()):
    """The two-panel figure of one run, built but not saved."""
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
    _draw_marks(ax, marks, full_xlim, (0, 1.02))

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
    _draw_marks(ax, marks, zoom_xlim, study.plot_zoom_ylim)

    fig.text(0.27, -0.02, "(a)", ha="center", fontsize=12)
    fig.text(0.775, -0.02, "(b)", ha="center", fontsize=12)
    fig.tight_layout()
    return fig


def plot_study(study: Study, rows, root=None, formats=("pdf", "svg", "png"),
               out_dir=None, marks=()):
    fig = study_figure(study, rows, marks)
    out = out_dir or output_dir(study.name, root)
    os.makedirs(out, exist_ok=True)
    return _save(fig, os.path.join(out, study.figure_basename), formats)


def _panel_ylim(panels, xlim):
    """From the lowest point any panel's band (mean less one standard
    deviation) reaches inside the x range, rounded down to 0.05, up to 1.
    Shared by every panel, so equal heights mean equal DER. The floor stays
    at or below 0.95 so a grid that never loses a packet still gets an axis
    with height rather than a degenerate one."""
    lo = 1.0
    for p in panels:
        for r in p["rows"]:
            if xlim[0] <= r["n_nodes"] <= xlim[1]:
                lo = min(lo, r["der_mean"] - r["der_std"])
    return (max(0.0, min(0.95, math.floor(lo * 20) / 20)), 1.0)


def panels_figure(panels):
    """One panel per configuration, side by side on a shared DER axis.

    Each panel carries the same scenarios in the same style, so a scenario
    is the same line in every panel and the eye compares a curve with its
    counterpart across panels. The capacity printed at each crossing, with
    its 95% interval drawn as a bar along the threshold, comes from the
    panel's `capacity.json`, the number the experiment's table prints.

    A panel's title states the receiver rule and the capture threshold it
    was run with, because every capacity here is conditional on both.
    """
    first = panels[0]["study"]
    scenarios = [s for s in first.scenarios
                 if any(r["scenario"] == s for p in panels for r in p["rows"])]
    style = _build_style(scenarios, first.highlight_scenario,
                         first.highlight_color)
    th = first.der_threshold
    xlim = first.plot_full_xlim or (
        min(r["n_nodes"] for p in panels for r in p["rows"]),
        max(r["n_nodes"] for p in panels for r in p["rows"]))
    ylim = _panel_ylim(panels, xlim)

    plt.rcParams.update({
        "font.size": 12, "axes.labelsize": 12, "legend.fontsize": 9.5,
        "xtick.labelsize": 11, "ytick.labelsize": 11,
    })
    # Every panel gets the same explicit y limits below, which is what makes
    # the axis shared, so sharey would add nothing.
    fig, axes = plt.subplots(1, len(panels), figsize=(5.5 * len(panels), 4.6),
                             squeeze=False)
    axes = axes[0]
    for k, (ax, p) in enumerate(zip(axes, panels)):
        by = group_by_scenario(p["rows"])
        labelled = []
        for i, scen in enumerate(scenarios):
            if scen not in by:
                continue
            rs = by[scen]
            ns = [r["n_nodes"] for r in rs]
            mean = [r["der_mean"] for r in rs]
            std = [r["der_std"] for r in rs]
            s = style[scen]
            ax.plot(ns, mean, color=s["color"], linestyle=s["ls"],
                    marker=s["marker"], markersize=4.5, markevery=2,
                    linewidth=1.7, label=scen)
            ax.fill_between(ns, [m - d for m, d in zip(mean, std)],
                            [m + d for m, d in zip(mean, std)],
                            color=s["color"], alpha=0.15, linewidth=0)
            c = p["capacity"].get(scen) or {}
            if c.get("capacity") is None:
                continue
            # Dotted drop line from the crossing to the floor, where the
            # number is printed: the floor is the one place no curve passes
            # through, the convention of the single-run figure.
            ax.plot([c["capacity"]] * 2, [ylim[0], th], color=s["color"],
                    linewidth=0.9, linestyle=":", alpha=0.8, zorder=1)
            ax.plot([c["ci_low"], c["ci_high"]], [th, th], color=s["color"],
                    linewidth=4, solid_capstyle="butt", zorder=4)
            ax.plot([c["capacity"]], [th], marker="o", markersize=6,
                    markerfacecolor="white", markeredgecolor=s["color"],
                    markeredgewidth=1.5, zorder=5)
            labelled.append((scen, c["capacity"]))
        _style_axis(ax, xlim, ylim, th)
        # Labels on the floor, staggered by order of capacity so two close
        # crossings do not overprint.
        for j, (scen, x) in enumerate(sorted(labelled, key=lambda t: t[1])):
            ax.annotate(f"{x:.0f}", xy=(x, ylim[0]),
                        xytext=(0, 4 + 12 * (j % 2)),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=9.5, fontweight="bold", color="0.15",
                        annotation_clip=False)
        s = p["study"]
        ax.set_title(f"{p['label']}, {s.capture_threshold_db:g} dB capture "
                     f"threshold", fontsize=11, loc="left")
        if k == 0:
            ax.set_ylabel("Data Extraction Rate (DER)")
            ax.legend(loc="lower left", frameon=True, framealpha=0.9)
        fig.text((k + 0.5) / len(panels), -0.02, f"({chr(97 + k)})",
                 ha="center", fontsize=12)
    fig.tight_layout()
    return fig


def plot_panels(panels, out_dir, basename, formats=("pdf", "svg", "png")):
    fig = panels_figure(panels)
    os.makedirs(out_dir, exist_ok=True)
    return _save(fig, os.path.join(out_dir, basename), formats)
