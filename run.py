#!/usr/bin/env python3
"""
run.py
======

Single entry point. Everything is done through a study name.

    python3 run.py list                 what studies exist
    python3 run.py new <name>           scaffold a new study from the template
    python3 run.py check <name>         validate the configuration, run nothing
    python3 run.py run <name>           simulate, analyse, plot
    python3 run.py plot <name>          re-plot from saved results
    python3 run.py capacity <name>      re-derive capacity from saved results
    python3 run.py sweep <name>         how much does the propagation model matter?
    python3 run.py validate <name>      does the engine reduce to ALOHA theory?
    python3 run.py compare <name>       what does not measuring cost?
    python3 run.py reproduce <name>     regenerate every result a document cites
    python3 run.py test                 fast checks on the engine itself
    python3 run.py serve                set a study up through a local web page

`check` is worth running before every `run`. It reports the coverage each
spreading factor reaches, the deployment area, and anything inconsistent in
the configuration. A simulation with a bad parameter does not fail, it just
quietly returns a wrong answer.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from loracap import analysis, experiment, study as study_mod

TEMPLATE = "_template"


def cmd_list(args):
    names = [n for n in study_mod.list_studies() if n != TEMPLATE]
    if not names:
        print("No studies yet. Create one:  python3 run.py new <name>")
        return 0
    print("Studies:")
    for n in names:
        try:
            s = study_mod.load_study(n)
            label = f" - {s.site}" if s.site else ""
            print(f"  {n}{label}")
        except Exception as e:
            print(f"  {n}  (failed to load: {e})")
    return 0


def cmd_new(args):
    name = args.name
    if not name.replace("_", "").replace("-", "").isalnum():
        sys.exit("Use a simple name: letters, digits, hyphen or underscore.")
    dest = study_mod.study_dir(name)
    if os.path.exists(dest):
        sys.exit(f"{dest} already exists.")
    src = study_mod.study_dir(TEMPLATE)
    if not os.path.isdir(src):
        sys.exit(f"Template missing at {src}.")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("outputs"))

    path = os.path.join(dest, "study.py")
    with open(path) as f:
        text = f.read()
    text = text.replace('name="_template"', f'name="{name}"')
    with open(path, "w") as f:
        f.write(text)

    print(f"Created {dest}\n")
    print("Next:")
    print(f"  1. Edit {os.path.join(dest, 'study.py')} — every field is commented,")
    print("     and the ones you must supply are marked TODO.")
    print("  2. Convert your site boundary:")
    print(f"       python3 tools/kml_to_polygon.py YOUR.kml --lat <gw_lat> --lon <gw_lon> \\")
    print(f"           -o {os.path.join(dest, 'site_polygon.py')}")
    print("  3. Fit the propagation model from your field measurements:")
    print("       python3 tools/fit_path_loss.py YOUR_DATA.csv --lat <gw_lat> --lon <gw_lon>")
    print(f"  4. python3 run.py check {name}")
    print(f"  5. python3 run.py run {name}")
    return 0


def _adhoc(s):
    """Provenance for a command typed by hand, so the file it writes says so."""
    from loracap import reproduce
    return reproduce.adhoc_provenance(s, sys.argv[1:])


def _load(name):
    try:
        return study_mod.load_study(name)
    except Exception as e:
        sys.exit(str(e))


def cmd_check(args):
    s = _load(args.name)
    errors, warnings, info = study_mod.validate(s)
    print(study_mod.format_report(s, errors, warnings, info))
    return 1 if errors else 0


def cmd_run(args):
    s = _load(args.name)
    errors, warnings, info = study_mod.validate(s)
    print(study_mod.format_report(s, errors, warnings, info))
    if errors:
        return 1
    print()
    rows = experiment.run_study(s)
    prov = _adhoc(s)
    csv_path, json_path = experiment.write_results(s, rows, provenance=prov)
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")

    cap = analysis.capacity_with_ci(rows, threshold=s.der_threshold,
                                    n_boot=args.bootstrap)
    print()
    print(analysis.format_capacity(cap, s.der_threshold))
    fcap = analysis.capacity_with_ci(
        [dict(r, der_mean=r["der_fleet_mean"], der_runs=r["der_fleet_runs"])
         for r in rows], threshold=s.der_threshold, n_boot=args.bootstrap)
    print(f"\nWrote {analysis.write_capacity(s.name, cap, s.der_threshold, provenance=prov, fleet_capacity=fcap)}")

    _report_energy(s, rows, cap)

    # Where an adaptive scenario leaves nodes with no usable data rate, the
    # headline DER is computed over the nodes that got on the air and says
    # nothing about the ones that did not. The fleet figure counts them, and
    # the two diverging is the signal that coverage, not collisions, is the
    # binding constraint.
    worst = max((r.get("unreachable_fraction_mean", 0.0) for r in rows),
                default=0.0)
    if worst > 0.005:
        print(f"\n  Up to {100 * worst:.1f}% of nodes have no usable data rate at "
              f"some node count.")
        print("  Those nodes never transmit, so they cannot lower the DER above.")
        print("  Counting them as lost traffic instead:")
        for scen in cap:
            a, b = cap[scen]["capacity"], fcap.get(scen, {}).get("capacity")
            print(f"    {scen:<8} {('%.1f' % a) if a else 'no crossing':>12}"
                  f"  ->  {('%.1f' % b) if b else 'no crossing':>12}")
        print("  Report the second figure, or report both and say which is which.")

    if not args.no_plot:
        try:
            from loracap import plotting
            for p in plotting.plot_study(s, rows):
                print(f"Wrote {p}")
        except ImportError:
            print("\nmatplotlib is not installed, so no figure was drawn.")
            print("Install it with:  pip install matplotlib")
    return 0


def cmd_plot(args):
    """Redraw every figure from saved JSON: the ad hoc run in outputs/, if
    there is one, and every manifest experiment that draws a figure."""
    from loracap import plotting, reproduce
    s = _load(args.name)
    drew = False
    try:
        rows = experiment.load_results(s.name)
    except FileNotFoundError:
        rows = None
    if rows is not None:
        for p in plotting.plot_study(s, rows):
            print(f"Wrote {p}")
        drew = True
    if reproduce.has_manifest(s.name):
        for p in reproduce.replot(s.name):
            print(f"Wrote {p}")
            drew = True
    if not drew:
        sys.exit(f"Nothing to plot for {s.name}. Run it first:  "
                 f"python3 run.py run {s.name}")
    return 0


def cmd_capacity(args):
    s = _load(args.name)
    rows = experiment.load_results(s.name)
    cap = analysis.capacity_with_ci(rows, threshold=s.der_threshold,
                                    n_boot=args.bootstrap)
    print(analysis.format_capacity(cap, s.der_threshold))
    analysis.write_capacity(s.name, cap, s.der_threshold, provenance=_adhoc(s))
    return 0


def cmd_sweep(args):
    s = _load(args.name)
    errors, warnings, info = study_mod.validate(s)
    if errors:
        print(study_mod.format_report(s, errors, warnings, info))
        return 1

    from loracap import sweep as sweep_mod

    if args.check_intercept:
        print("Checking whether the propagation model's intercept affects capacity.\n")
        inv = sweep_mod.verify_intercept_invariance(
            s, scenario=args.scenario, n_runs=args.runs)
        print(sweep_mod.format_invariance(inv))
        print(f"Wrote {sweep_mod.write_invariance(s.name, inv, provenance=_adhoc(s))}")
        return 0

    low, high = args.low, args.high
    provenance = ("a bracket, not a recommendation: narrow it with a source "
                  "for your terrain")
    if args.terrain:
        from loracap import presets
        try:
            low, high, median, n_studies, freqs = presets.terrain_range(args.terrain)
        except KeyError as e:
            sys.exit(str(e))
        provenance = (
            f"range observed for '{args.terrain}' across {n_studies} published LoRa "
            f"campaigns at {', '.join(str(f) for f in freqs)} MHz, median {median}\n"
            f"source: {presets.TERRAIN_SOURCE}\n"
            f"these are the source review's own environment labels, pooled across\n"
            f"frequency and distance range: treat the span as context, not as a value"
        )

    import warnings
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            exps = sweep_mod.exponent_range(low, high, args.steps)
    except ValueError as e:
        sys.exit(str(e))
    for w in caught:
        # Reported as a clean note rather than a raw warning: when the range
        # comes from --terrain, a sub-2 exponent is in the published data and
        # is expected, not a mistake by the user.
        print(f"Note: {w.message}\n")

    print(f"Sweeping the path-loss exponent over {exps}")
    print(f"({provenance})\n")
    sw = sweep_mod.sweep_propagation(s, exponents=exps, scenario=args.scenario,
                                     n_runs=args.runs)
    print()
    print(sweep_mod.format_sweep(sw))
    print(f"Wrote {sweep_mod.write_sweep(s.name, sw, provenance=_adhoc(s))}")
    return 0


def cmd_validate(args):
    """Walk the degeneracy ladder down onto the pure-ALOHA bound.

    This is the check that the engine is right, as opposed to `check`, which
    verifies that a study is configured sensibly. It is slow, because it runs
    the grid once per rung, so it takes its own node counts rather than the
    study's full sweep.
    """
    from loracap import validation as val

    s = _load(args.name)
    errors, _, _ = study_mod.validate(s)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1

    scenario = args.scenario or s.highlight_scenario or s.scenarios[0]
    counts = ([int(x) for x in args.nodes.split(",")] if args.nodes
              else [10, 30, 60, 100, 200])
    runs = args.runs if args.runs is not None else min(s.n_runs, 10)
    sim_time = args.sim_time if args.sim_time is not None else s.sim_time_s

    cfg = s.to_sim_config()
    try:
        val.scenario_sf(scenario, cfg)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"Validating {s.name} against the analytical bound")
    print(f"  scenario {scenario}, {len(counts)} node counts, {runs} runs each, "
          f"{sim_time:.0f} s simulated")
    rungs = val.ladder_for(cfg)
    extra = 1 if cfg.receiver_model == "lock" else 0
    print(f"  {len(rungs)} rungs, so {len(counts) * (len(rungs) + extra)} batches"
          + (", including the lock rule's own bound" if extra else "") + "\n")

    def progress(done, total, n, label, der):
        print(f"  [{done}/{total}] N={n:<5} {label:<16} DER={der:.4f}")

    ladder = val.run_ladder(cfg, scenario, counts, sim_time_s=sim_time,
                            n_runs=runs, base_seed=s.base_seed, progress=progress)
    verdict = val.assess(ladder)
    print()
    print(val.format_ladder(ladder, verdict))
    print(f"\nWrote {val.write_ladder(s.name, ladder, verdict, provenance=_adhoc(s))}")

    if not args.no_plot:
        try:
            from loracap import plotting
            for p in plotting.plot_validation(s, ladder):
                print(f"Wrote {p}")
        except ImportError:
            print("matplotlib is not installed, so no figure was drawn.")

    return 0 if verdict["passes"] else 2


def _life_text(life):
    if not life:
        return "-"
    days = life["service_life_days"]
    return f"{days / 365.25:.1f} y" if days > 400 else f"{days:.0f} d"


def _report_energy(s, rows, cap):
    """Energy per extracted message, and a service life if one can be had.

    Reported at each scenario's own capacity rather than at a fixed node
    count, because that is the operating point the rest of the output is
    about, and because the cost per message rises with congestion: every
    packet that collides was paid for.
    """
    if rows[0].get("tx_energy_j_mean") is None:
        return
    print()
    print("Energy")
    header = f"  {'scenario':<10}{'at N':>7}{'per message':>14}{'life':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    any_life = False
    for scen, c in cap.items():
        n = c.get("capacity")
        pool = [r for r in rows if r["scenario"] == scen]
        if not pool:
            continue
        target = n or pool[-1]["n_nodes"]
        row = min(pool, key=lambda r: abs(r["n_nodes"] - target))
        nec = row.get("nec_j_per_message_mean")
        life = analysis.service_life(row, s)
        if life:
            any_life = True
        print(f"  {scen:<10}{row['n_nodes']:>7}"
              f"{(f'{1000 * nec:.1f} mJ' if nec else 'n/a'):>14}"
              f"{_life_text(life):>12}")
    if any_life:
        sample = analysis.service_life(rows[-1], s)
        print(f"  Transmitting is {100 * sample['transmit_share']:.1f}% of the "
              f"average current; the rest is sleep.")
    else:
        print("  Set sleep_current_ua and battery_capacity_mah for a service "
              "life.")
        print("  Transmit energy alone is not one, and which of the two terms")
        print("  dominates depends on your reporting interval.")


def cmd_compare(args):
    """Resolve one study under its fitted model and under an assumed one.

    Only meaningful where the study HAS a fitted model, since that is the
    ground truth the assumed one is checked against. A site without
    measurements is served by `sweep` instead.
    """
    from loracap import compare as cmp_mod

    s = _load(args.name)
    errors, warnings, info = study_mod.validate(s)
    print(study_mod.format_report(s, errors, warnings, info))
    if errors:
        return 1

    try:
        if args.keep_intercept:
            label, overrides, provenance = cmp_mod.exponent_only_variant(
                s, args.terrain, exponent=args.exponent)
        else:
            label, overrides, provenance = cmp_mod.terrain_variant(
                s, args.terrain, range_m=args.range_m, anchor_sf=args.anchor_sf,
                exponent=args.exponent)
    except (KeyError, ValueError) as e:
        print(f"ERROR: {e}")
        return 1

    print()
    print(f"Fitted model:  n = {s.path_loss_exponent:.3f}, "
          f"L(d0) = {s.path_loss_ref_db:.2f} dB at "
          f"{s.path_loss_ref_distance_m:.0f} m")
    if not s.path_loss_source:
        print("  WARNING: this study records no source for its propagation")
        print("  model, so there is no reason to treat it as ground truth.")
    print(f"Assumed model: n = {provenance['exponent']:.3f} "
          f"(median for {args.terrain}, published range "
          f"{provenance['range_low']} to {provenance['range_high']}), "
          f"L(d0) = {provenance['path_loss_ref_db']:.2f} dB")
    if provenance["anchor_range_m"] is None:
        print("  intercept kept from the fitted model, so only the exponent "
              "differs")
    else:
        print(f"  intercept anchored to a reach of "
              f"{provenance['anchor_range_m']:.0f} m at "
              f"SF{provenance['anchor_sf']}")
    print(f"  {provenance['source']}")
    print()

    def progress(done, total, label_, scen, n, der):
        print(f"  [{done}/{total}] {label_:<18} {scen:<6} n={n:<5} "
              f"DER={der:.4f}")

    result = cmp_mod.compare_models(
        s, [("fitted (field)", {}), (label, overrides)],
        n_runs=args.runs, n_boot=args.bootstrap, progress=progress)
    verdict = cmp_mod.assess(result)
    print()
    print(cmp_mod.format_comparison(result, verdict))
    print(f"\nWrote {cmp_mod.write_comparison(s.name, result, verdict, provenance=_adhoc(s))}")
    return 0


def cmd_reproduce(args):
    """Run a study's experiments.py and print every table it backs.

    The manifest is the record: each experiment states its repetitions, node
    grid, simulated time and seed, and writes into its own outputs/<name>/
    directory, which nothing run by hand ever touches. `--tables` re-renders
    from the saved files without simulating. `reference` prints the tables
    that come from presets and need no simulation at all.
    """
    from loracap import reproduce

    if args.name == "reference":
        print(reproduce.reference_tables())
        return 0

    names = ([n for n in study_mod.list_studies()
              if n != TEMPLATE and reproduce.has_manifest(n)]
             if args.name == "all" else [args.name])
    status = 0
    for name in names:
        try:
            exps = reproduce.load_manifest(name)
        except (FileNotFoundError, reproduce.ManifestError) as e:
            print(f"ERROR: {e}")
            return 1
        if args.only:
            known = {e.name for e in exps}
            unknown = set(args.only) - known
            if unknown:
                print(f"ERROR: {name} has no experiment {sorted(unknown)}. "
                      f"It has: {', '.join(sorted(known))}")
                return 1
            exps = [e for e in exps if e.name in args.only]

        if args.list:
            print(f"{name}:")
            for e in exps:
                print(f"  {e.name:<22} {e.kind:<10} {e.n_runs} runs, "
                      f"{e.sim_time_s:g} s  {e.description}")
            continue

        if not args.tables:
            print(f"Reproducing {name}: {len(exps)} experiment(s)")
            for e in exps:
                try:
                    summary = reproduce.run_experiment(name, e, plot=not args.no_plot)
                except reproduce.ManifestError as err:
                    print(f"ERROR: {err}")
                    return 1
                if not summary["passes"]:
                    print(f"  {e.name}: VALIDATION FAILED. Investigate before "
                          f"quoting anything from it.")
                    status = 2
            print()
        for e in exps:
            try:
                print(reproduce.render_tables(name, e))
                reproduce.write_tables(name, e)
            except FileNotFoundError as err:
                print(f"### {name} / {e.name}\n\nNot run yet ({err.filename}).\n")
    return status


def cmd_test(args):
    """Run the test suite.

    Standard library only, like the package, so this needs nothing installed.
    It is here rather than left to `python3 -m unittest` so that there is one
    obvious way to check an installation, and so that a change to the engine
    has a check that takes seconds rather than the minutes `validate` and the
    reproduction studies take.
    """
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=os.path.join(ROOT, "tests"),
                            top_level_dir=ROOT)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    if result.wasSuccessful():
        print("\nThe fast checks pass. They do not replace:")
        print("  python3 run.py validate <study>    degeneracy onto ALOHA theory")
        print("  python3 run.py run bor2016_sn3     agreement with LoRaSim")
        return 0
    return 1


def cmd_serve(args):
    """Launch the local setup page.

    The page is a way of writing a study.py, never an alternative to it: it
    produces the same file the template produces, and every later step goes
    through the commands above. Nothing it does bypasses this script.
    """
    from webui import server            # noqa: E402  (deferred on purpose)
    server.serve(port=args.port, open_browser=not args.no_browser)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="LoRaWAN network-capacity simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list available studies").set_defaults(func=cmd_list)

    p = sub.add_parser("new", help="scaffold a new study")
    p.add_argument("name")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("check", help="validate a study without running it")
    p.add_argument("name")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("run", help="simulate, analyse and plot")
    p.add_argument("name")
    p.add_argument("--bootstrap", type=int, default=2000,
                   help="bootstrap replicates for the capacity CI (default 2000)")
    p.add_argument("--no-plot", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("plot", help="re-plot from saved results")
    p.add_argument("name")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("capacity", help="re-derive capacity from saved results")
    p.add_argument("name")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.set_defaults(func=cmd_capacity)

    p = sub.add_parser(
        "sweep",
        help="how much does the assumed propagation model change the answer?")
    p.add_argument("name")
    p.add_argument("--low", type=float, default=2.0,
                   help="lowest path-loss exponent (default 2.0, free space)")
    p.add_argument("--high", type=float, default=3.5,
                   help="highest path-loss exponent (default 3.5)")
    p.add_argument("--steps", type=int, default=7,
                   help="how many exponents to try (default 7)")
    p.add_argument("--terrain", default=None,
                   help="take the range from published LoRa measurements for an "
                        "environment (rural, suburban, urban, forest, campus) "
                        "instead of --low/--high")
    p.add_argument("--scenario", default=None,
                   help="which scenario to sweep (default: the highlighted one)")
    p.add_argument("--runs", type=int, default=None,
                   help="runs per point (default: the study's n_runs; lower is "
                        "much faster for a first look)")
    p.add_argument("--check-intercept", action="store_true",
                   help="instead of sweeping, verify that the model's intercept "
                        "does not affect capacity")
    p.set_defaults(func=cmd_sweep)

    p = sub.add_parser(
        "validate",
        help="check the engine against the analytical pure-ALOHA bound")
    p.add_argument("name")
    p.add_argument("--scenario", default=None,
                   help="which fixed-SF scenario to validate (default: the "
                        "highlighted one). Adaptive scenarios cannot be used, "
                        "since the bound needs a single time on air.")
    p.add_argument("--nodes", default=None,
                   help="comma-separated node counts (default: 10,30,60,100,200)")
    p.add_argument("--runs", type=int, default=None,
                   help="runs per point (default: the study's n_runs, capped at 10)")
    p.add_argument("--sim-time", type=float, default=None, dest="sim_time",
                   help="seconds simulated per run (default: the study's)")
    p.add_argument("--no-plot", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser(
        "compare",
        help="what does not measuring cost? fitted model against an assumed one")
    p.add_argument("name")
    p.add_argument("--terrain", default="rural",
                   help="environment whose published exponent to assume "
                        "(rural, suburban, urban, forest, campus)")
    p.add_argument("--range", dest="range_m", type=float, default=None,
                   help="reach the link is expected to have [m]; default is "
                        "the site's own radius")
    p.add_argument("--anchor-sf", dest="anchor_sf", type=int, default=None,
                   help="spreading factor the expected reach refers to "
                        "(default: the slowest in play)")
    p.add_argument("--exponent", type=float, default=None,
                   help="use this exponent instead of the terrain's median")
    p.add_argument("--keep-intercept", dest="keep_intercept",
                   action="store_true",
                   help="change only the exponent, keeping the fitted "
                        "intercept, which separates the exponent's effect "
                        "from the anchor's")
    p.add_argument("--runs", type=int, default=None,
                   help="runs per point (default: the study's n_runs)")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser(
        "reproduce",
        help="regenerate every result a document cites, from experiments.py")
    p.add_argument("name", help="a study, 'all', or 'reference' for the "
                                "tables that need no simulation")
    p.add_argument("--only", nargs="+", default=None,
                   help="run only these experiments")
    p.add_argument("--tables", action="store_true",
                   help="print the tables from saved results, simulate nothing")
    p.add_argument("--list", action="store_true",
                   help="list the experiments and exit")
    p.add_argument("--no-plot", action="store_true")
    p.set_defaults(func=cmd_reproduce)

    p = sub.add_parser(
        "test", help="run the fast checks on the engine itself")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser(
        "serve",
        help="open a local web page for setting a study up")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true",
                   help="do not open a browser window; print the address instead")
    p.set_defaults(func=cmd_serve)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
