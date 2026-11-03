#!/usr/bin/env python3
"""
loracap web interface
=====================

A local form for setting a study up, so the fiddly parts (converting a
boundary, fitting a propagation model, getting the regional spreading factors
right) are done with immediate feedback instead of by editing a file and
re-running a command.

Two design rules shape it.

It WRITES A study.py AND NOTHING ELSE. The interface is a way of producing
that file, never an alternative to it. Everything afterwards (run, sweep,
plot) goes through exactly the same code the command line uses, so a result
produced here is reproducible, inspectable and diffable in the same way. A
tool whose output goes into papers cannot afford a second path where numbers
appear without a record of how.

It VALIDATES AS YOU TYPE. `loracap.study.validate` already knows which
spreading factors a band permits, whether the site fits inside the modelled
coverage, and whether the reference distance sits inside the fitted range.
Surfacing that while a field is being chosen catches the mistake at the point
it is made, which is the one thing a form can do that a command cannot.

Standard library only. Uploaded files are read in the browser and posted as
text, so there is no multipart parsing and no new dependency.

The server binds to the loopback interface and is not intended to be exposed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from loracap import analysis, experiment, geo, pathloss, presets, study as study_mod
from loracap.core import RECEIVER_MODELS, max_distance_m, parse_scenario
from loracap.core import ref_loss_for_range as core_ref_loss

MAX_BODY_BYTES = 64 * 1024 * 1024        # a long measurement CSV is legitimately big
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# One run at a time, tracked here so the page can poll for progress.
_job = {"state": "idle", "done": 0, "total": 0, "study": None,
        "error": None, "capacity": None, "figure": None, "log": []}
_job_lock = threading.Lock()


def safe_study_dir(name: str) -> str:
    """Resolve a study directory, refusing anything that escapes studies/.

    The name arrives from a form field, so it is checked against a whitelist
    and the resolved path is confirmed to sit under studies/ before any write.
    """
    if not SAFE_NAME.match(name or ""):
        raise ValueError(
            "Use a short name of letters, digits, hyphen or underscore, "
            "starting with a letter or digit."
        )
    root = os.path.realpath(study_mod.studies_root())
    target = os.path.realpath(os.path.join(root, name))
    if os.path.dirname(target) != root:
        raise ValueError("Invalid study name.")
    return target


# What the page says about each receiver rule. Keyed by the engine's own list,
# and a test checks the two match, so a rule added to the engine cannot reach
# the form without a description of what choosing it means.
RECEIVER_MODEL_NOTES = {
    "lorasim": (
        "LoRaSim's rule, the default. Power decides between two overlapping "
        "packets whichever arrived first. Every published result here and the "
        "reproduction of Bor et al. use it."),
    "lock": (
        "The receiver stays on the packet it synchronised to first, as Bor et "
        "al. (SX1272) and Haxhibeqiri et al. (SX1301) measured. Results are "
        "conditional on this rule: neither rule has been checked against the "
        "capacity of a real network. See \"The receiver rule\" in the README."),
}

CAPTURE_THRESHOLD_NOTE = (
    "LoRaSim's value is 6 dB. Measurements that place the threshold put it at "
    "3 dB or less (Fernandes et al. 2019, Croce et al. 2020, Eigner 2021), but "
    "none states its coding rate and two used a node radio rather than a "
    "gateway. It moves capacity about as much as the receiver rule does, so a "
    "value other than 6 dB is an assumption to report.")

LOCK_SURVIVAL_DEFAULT_NOTE = (
    "Past the lock window the locked packet is lost to a later one stronger "
    "by the capture threshold, as item 13 built the rule.")

HEADER_RECAPTURE_NOTE = (
    "A later packet stronger by the capture threshold that arrives during "
    "the locked packet's header takes the receiver over, as Haxhibeqiri et "
    "al. and Eigner observed. The header is taken as eight symbols. "
    "Haxhibeqiri et al. saw no recapture at SF12 at 600 ms, inside those "
    "eight symbols, so the window is an assumption at high spreading factors.")

ORTHOGONAL_NOTE = (
    "Packets on different spreading factors never collide. LoRaSim's "
    "assumption and the default, which makes every result that spreads nodes "
    "over several spreading factors an upper bound.")


def _study_default(name: str):
    import dataclasses as _dc
    return next(f.default for f in _dc.fields(study_mod.Study) if f.name == name)


# ---------------------------------------------------------------------------
# Endpoint handlers. Each takes the decoded JSON body and returns a dict.
# ---------------------------------------------------------------------------

def api_bootstrap(_):
    """Everything the page needs to populate its menus."""
    return {
        "regions": {r: list(sfs) for r, sfs in presets.REGION_UPLINK_SF_125KHZ.items()},
        "region_notes": presets.REGION_NOTES,
        "chips": sorted(presets.SENSITIVITY_DBM),
        "chip_detail": {
            c: {
                "sensitivity": presets.SENSITIVITY_DBM[c].get(
                    125, next(iter(presets.SENSITIVITY_DBM[c].values()))),
                "bandwidths": sorted(presets.SENSITIVITY_DBM[c]),
                "source": presets.SENSITIVITY_SOURCE.get(c, ""),
                "channels": presets.N_UPLINK_CHANNELS.get(c),
                "max_demod": presets.MAX_SIMULTANEOUS_DEMODULATIONS.get(c),
            } for c in presets.SENSITIVITY_DBM
        },
        "dwell_time_regions": list(presets.DWELL_TIME_REGIONS),
        "dwell_time_options": {
            r: sorted(presets.MAX_APP_PAYLOAD_BYTES[r])
            for r in presets.DWELL_TIME_REGIONS
        },
        "terrains": {k: {"low": v[0], "high": v[1], "median": v[2],
                         "n_studies": v[3], "freqs": list(v[4])}
                     for k, v in presets.TERRAIN_EXPONENTS.items()},
        "terrain_source": presets.TERRAIN_SOURCE,
        "existing_studies": [s for s in study_mod.list_studies() if s != "_template"],
        "default_node_counts": study_mod.node_counts_logspace(3, 300),
        # Receiver model. The defaults come from Study itself rather than
        # being repeated here, so the form cannot drift from what a study
        # written by hand would get.
        "receiver_models": [{"value": m, "note": RECEIVER_MODEL_NOTES[m]}
                            for m in RECEIVER_MODELS],
        "default_receiver_model": _study_default("receiver_model"),
        "default_capture_threshold_db": _study_default("capture_threshold_db"),
        "capture_threshold_note": CAPTURE_THRESHOLD_NOTE,
        "inter_sf_tables": [{"value": name,
                             "source": presets.INTER_SF_REJECTION_SOURCE[name]}
                            for name in sorted(presets.INTER_SF_REJECTION_DB)],
        "orthogonal_note": ORTHOGONAL_NOTE,
        # Refinements of the lock rule. The page offers them only while the
        # lock rule is chosen, since `check` refuses them under any other.
        "lock_survival_tables": [{"value": name,
                                  "source": presets.LOCK_SURVIVAL_SOURCE[name]}
                                 for name in sorted(presets.LOCK_SURVIVAL_DB)],
        "lock_survival_default_note": LOCK_SURVIVAL_DEFAULT_NOTE,
        "header_recapture_note": HEADER_RECAPTURE_NOTE,
        "default_header_recapture": _study_default("header_recapture"),
    }


def api_kml(body):
    """KML text plus a gateway position, in. Projected polygons and the three
    checks that matter, out."""
    placemarks = geo.parse_kml(body["kml"], is_text=True)
    if not placemarks:
        raise ValueError("No polygons found in that file. If it is a KMZ, unzip "
                         "it first: the KML is inside.")
    include = [s.strip().lower() for s in body.get("include", []) if s.strip()]
    if include:
        placemarks = [(n, p) for n, p in placemarks
                      if any(i in n.lower() for i in include)]
        if not placemarks:
            raise ValueError("No polygon name matched that filter.")
    rings = geo.project_rings(placemarks, float(body["lat"]), float(body["lon"]))
    info = geo.inspect(rings)
    info["names"] = [n for n, _ in placemarks]
    # The page draws the outline, so send the vertices too. Two decimals is
    # the precision site_polygon.py is written at, so a boundary that makes the
    # round trip through the browser produces the same file as the command line.
    info["rings"] = [[[round(x, 2), round(y, 2)] for x, y in r] for _, r in rings]
    return info


def api_fit(body):
    """Measurement CSV in, both fits plus the sanity checks out."""
    header, rows = pathloss.read_csv(body["csv"], is_text=True)
    if not rows:
        raise ValueError("That file has no data rows.")
    tx = body.get("tx_power_dbm")
    return pathloss.analyse(
        header, rows, float(body["lat"]), float(body["lon"]),
        tx_power_dbm=float(tx) if tx not in (None, "") else None,
        net_gain_db=float(body.get("net_gain_db") or 0.0),
        d0_m=float(body.get("d0_m") or 100.0),
        min_distance_m=float(body.get("min_distance_m") or 30.0),
        bin_width_m=float(body.get("bin_width_m") or 10.0),
    )


def api_anchor(body):
    """Turn a terrain choice plus an expected range into a usable model.

    A published exponent gives the slope and says nothing about the intercept,
    so something has to supply it. This takes the one quantity a deployer can
    state without a measurement campaign: roughly how far the link is expected
    to work, at a stated spreading factor.

    The result is an assumption, and the page labels it as one. What keeps it
    defensible is that capacity does not depend on the intercept while the
    site stays covered, so the anchor's real job is to set coverage, which is
    exactly what it states.
    """
    terrain = body.get("terrain")
    if terrain:
        low, high, median, n_studies, freqs = presets.terrain_range(terrain)
        exponent = float(body.get("exponent") or median)
    else:
        low = high = median = n_studies = None
        freqs = ()
        exponent = float(body["exponent"])

    chip = body.get("chip")
    sf = int(body["sf"])
    sens = body.get("sensitivity_dbm")
    if sens is None:
        if not chip:
            raise ValueError("Choose a gateway chip, or give a sensitivity value.")
        try:
            table, _derived = presets.sensitivity_for(
                chip, (sf,), int(body.get("bw_khz") or 125))
        except KeyError as e:
            raise ValueError(str(e))
        sens = table[sf]
    sens = float(sens)

    net_gain = (float(body.get("rx_antenna_gain_db") or 0)
                + float(body.get("tx_antenna_gain_db") or 0)
                - float(body.get("cable_loss_db") or 0))
    tx = float(body.get("tx_power_dbm") or 14)
    d0 = float(body.get("d0_m") or 100.0)
    rng = float(body["range_m"])

    out = {
        "exponent": exponent, "sf": sf, "sensitivity_dbm": sens,
        "range_m": rng, "d0_m": d0,
        "terrain": terrain, "low": low, "high": high, "median": median,
        "n_studies": n_studies, "study_frequencies_mhz": list(freqs),
        "source": presets.TERRAIN_SOURCE if terrain else "",
        "warnings": [],
    }
    # one reference loss per exponent, so the page can show what the published
    # spread does to the model before anything is run
    for key, e in (("ref_db", exponent), ("ref_db_low", low), ("ref_db_high", high)):
        if e is None:
            continue
        out[key] = core_ref_loss(tx, net_gain, sens, float(e), rng, d0)

    region = body.get("region")
    f_region = presets.REGION_UPLINK_MHZ.get(region)
    if terrain and f_region and freqs:
        nearest = min(freqs, key=lambda f: abs(f - f_region))
        if abs(nearest - f_region) > 100:
            out["warnings"].append(
                f"The published exponents for '{terrain}' were measured at "
                f"{', '.join(str(f) for f in freqs)} MHz, while {region} uplinks "
                f"near {f_region:.0f} MHz. Path loss depends on frequency, so "
                f"carrying the exponent across that gap needs saying out loud."
            )
    if terrain and n_studies is not None and n_studies < 4:
        out["warnings"].append(
            f"The range for '{terrain}' pools only {n_studies} studies, so it "
            f"describes the few sites that were measured rather than the "
            f"environment as a class."
        )
    return out


def api_sweep(body):
    """Capacity across a range of exponents, for a study whose model is assumed
    rather than fitted. A single capacity figure would misrepresent it."""
    import warnings as _warnings
    from loracap import sweep as sweep_mod
    name = body["name"]
    safe_study_dir(name)
    st = study_mod.load_study(name)
    # The engine warns rather than refuses on an unusual exponent, which is
    # right for a library. On the command line that lands in the terminal; here
    # it would be lost, so it is collected and sent to the page.
    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        exps = sweep_mod.exponent_range(
            float(body.get("low") or 2.0), float(body.get("high") or 3.5),
            int(body.get("steps") or 5))
        sw = sweep_mod.sweep_propagation(
            st, exponents=exps, scenario=body.get("scenario"),
            n_runs=int(body["runs"]) if body.get("runs") else None)
    sweep_mod.write_sweep(st.name, sw)
    return {"sweep": sw, "text": sweep_mod.format_sweep(sw),
            "warnings": [str(w.message) for w in caught]}


def _study_from_values(values: dict) -> study_mod.Study:
    """Build a Study from form values, ignoring keys it does not define."""
    import dataclasses as _dc
    fields = {f.name for f in _dc.fields(study_mod.Study)}
    kwargs = {k: v for k, v in values.items() if k in fields and v is not None}
    for seq in ("spreading_factors", "scenarios", "node_counts", "adaptive_sf_options"):
        if seq in kwargs and kwargs[seq] is not None:
            kwargs[seq] = tuple(kwargs[seq])
    if "sensitivity_dbm" in kwargs and kwargs["sensitivity_dbm"]:
        kwargs["sensitivity_dbm"] = {int(k): float(v)
                                     for k, v in kwargs["sensitivity_dbm"].items()}
    return study_mod.Study(**kwargs)


def api_validate(body):
    """Live validation. Also reports each scenario's reach against the site, so
    the coverage question is visible while the model is being chosen."""
    values = dict(body.get("values") or {})
    values.setdefault("name", "draft")
    rings = body.get("rings")
    if rings:
        values["polygons_m"] = [[(float(x), float(y)) for x, y in r] for r in rings]
    try:
        st = _study_from_values(values)
    except TypeError as e:
        return {"errors": [f"Configuration is incomplete: {e}"],
                "warnings": [], "info": [], "reach": []}

    errors, warnings, info = study_mod.validate(st)

    reach = []
    if not errors and st.path_loss_ref_db > 0:
        try:
            cfg = st.to_sim_config()
            site_r = (geo.inspect([("s", r) for r in st.polygons_m])["max_radius_m"]
                      if st.placement == "polygon" and st.polygons_m else None)
            for scen in st.scenarios:
                try:
                    _, opts = parse_scenario(scen, cfg)
                except ValueError:
                    continue
                d = max_distance_m(cfg, min(cfg.sensitivity_dbm[sf] for sf in opts))
                reach.append({"scenario": scen, "reach_m": d,
                              "site_radius_m": site_r,
                              "covers": None if site_r is None else d >= site_r})
        except Exception:
            pass
    return {"errors": errors, "warnings": warnings, "info": info, "reach": reach}


def api_create(body):
    """Write studies/<name>/study.py and site_polygon.py."""
    values = dict(body.get("values") or {})
    name = values.get("name", "")
    target = safe_study_dir(name)
    if os.path.exists(target) and not body.get("overwrite"):
        raise ValueError(f"A study called {name!r} already exists. "
                         f"Choose another name, or confirm overwriting it.")
    os.makedirs(target, exist_ok=True)

    written = []
    rings = body.get("rings")
    use_poly = bool(rings) and values.get("placement", "polygon") == "polygon"
    if use_poly:
        projected = [(n, [(float(x), float(y)) for x, y in r])
                     for n, r in zip(body.get("ring_names") or
                                     [f"polygon {i+1}" for i in range(len(rings))],
                                     rings)]
        text = geo.render_site_polygon(
            projected, float(body["lat"]), float(body["lon"]),
            values.get("site") or name,
            source_note=body.get("source_note", ""))
        path = os.path.join(target, "site_polygon.py")
        with open(path, "w") as f:
            f.write(text)
        written.append(os.path.relpath(path, ROOT))

    values.pop("polygons_m", None)
    text = study_mod.render_study_module(
        values, use_site_polygon=use_poly,
        generated_note="Created with the loracap web interface.")
    path = os.path.join(target, "study.py")
    with open(path, "w") as f:
        f.write(text)
    written.append(os.path.relpath(path, ROOT))

    # reload from disk, so what is reported back is what the file actually says
    reloaded = study_mod.load_study(name)
    errors, warnings, info = study_mod.validate(reloaded)
    return {"written": written, "study_py": text, "name": name,
            "errors": errors, "warnings": warnings, "info": info}


def _run_worker(name: str, bootstrap: int):
    try:
        st = study_mod.load_study(name)
        errors, _, _ = study_mod.validate(st)
        if errors:
            with _job_lock:
                _job.update(state="error", error="; ".join(errors))
            return

        def cb(done, total, row):
            with _job_lock:
                _job.update(done=done, total=total)
                _job["log"].append(
                    f"{row['scenario']} n={row['n_nodes']} "
                    f"DER={row['der_mean']:.4f} +/- {row['der_std']:.4f}")
                del _job["log"][:-200]

        rows = experiment.run_study(st, progress=False, callback=cb)
        experiment.write_results(st, rows)
        cap = analysis.capacity_with_ci(rows, threshold=st.der_threshold,
                                        n_boot=bootstrap)
        analysis.write_capacity(st.name, cap, st.der_threshold)
        figure = None
        try:
            from loracap import plotting
            paths = plotting.plot_study(st, rows)
            png = [p for p in paths if p.endswith(".png")]
            figure = os.path.relpath(png[0], ROOT) if png else None
        except ImportError:
            with _job_lock:
                _job["log"].append("matplotlib not installed, so no figure was drawn")
        with _job_lock:
            _job.update(state="done", capacity=cap, figure=figure)
    except Exception as e:
        with _job_lock:
            _job.update(state="error", error=f"{e}\n{traceback.format_exc()}")


def api_run(body):
    name = body["name"]
    safe_study_dir(name)        # validates the name
    with _job_lock:
        if _job["state"] == "running":
            raise ValueError("A run is already in progress.")
        _job.update(state="running", done=0, total=0, study=name,
                    error=None, capacity=None, figure=None, log=[])
    threading.Thread(target=_run_worker, daemon=True,
                     args=(name, int(body.get("bootstrap") or 2000))).start()
    return {"started": True}


def api_status(_):
    with _job_lock:
        return dict(_job)


def api_figure(body):
    """Serve a produced figure back as a data URL, so the page can show it
    without the server needing a static file route into studies/."""
    import base64
    rel = body.get("path") or ""
    full = os.path.realpath(os.path.join(ROOT, rel))
    if not full.startswith(os.path.realpath(study_mod.studies_root())):
        raise ValueError("Not a study output.")
    if not os.path.isfile(full):
        raise ValueError("No such figure.")
    with open(full, "rb") as f:
        return {"data_url": "data:image/png;base64," +
                            base64.b64encode(f.read()).decode()}


ROUTES = {
    "/api/bootstrap": api_bootstrap,
    "/api/kml": api_kml,
    "/api/fit": api_fit,
    "/api/anchor": api_anchor,
    "/api/sweep": api_sweep,
    "/api/validate": api_validate,
    "/api/create": api_create,
    "/api/run": api_run,
    "/api/status": api_status,
    "/api/figure": api_figure,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "loracap"

    def log_message(self, fmt, *args):
        pass        # the page is the interface, the console is for the user

    def _send(self, code, payload, ctype="application/json"):
        body = (json.dumps(payload).encode() if ctype == "application/json"
                else payload.encode())
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html")) as f:
                    self._send(200, f.read(), "text/html")
            except OSError:
                self._send(500, "index.html is missing from webui/", "text/plain")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        handler = ROUTES.get(self.path)
        if handler is None:
            self._send(404, {"error": "no such endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                raise ValueError("That file is too large to upload here.")
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send(400, {"error": f"Could not read the request: {e}"})
            return
        try:
            self._send(200, {"ok": True, "result": handler(body)})
        except (ValueError, KeyError) as e:
            self._send(200, {"ok": False, "error": str(e)})
        except Exception as e:
            self._send(200, {"ok": False,
                             "error": f"{type(e).__name__}: {e}",
                             "trace": traceback.format_exc()})


def serve(port: int = 8765, open_browser: bool = True):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"loracap web interface on {url}")
    print("It writes a study.py and runs it through the same code as the command")
    print("line, so anything produced here stays reproducible.")
    print("\nPress Ctrl+C to stop.\n")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="loracap web interface")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    serve(a.port, not a.no_browser)
