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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    csv_path, json_path = experiment.write_results(s, rows)
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")

    cap = analysis.capacity_with_ci(rows, threshold=s.der_threshold,
                                    n_boot=args.bootstrap)
    print()
    print(analysis.format_capacity(cap, s.der_threshold))
    print(f"\nWrote {analysis.write_capacity(s.name, cap, s.der_threshold)}")

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
    s = _load(args.name)
    rows = experiment.load_results(s.name)
    from loracap import plotting
    for p in plotting.plot_study(s, rows):
        print(f"Wrote {p}")
    return 0


def cmd_capacity(args):
    s = _load(args.name)
    rows = experiment.load_results(s.name)
    cap = analysis.capacity_with_ci(rows, threshold=s.der_threshold,
                                    n_boot=args.bootstrap)
    print(analysis.format_capacity(cap, s.der_threshold))
    analysis.write_capacity(s.name, cap, s.der_threshold)
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

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
