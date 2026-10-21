# LoRaCAP

**A field-calibrated LoRaWAN uplink capacity simulator.**

Estimates how many nodes a LoRaWAN deployment can carry before packet loss
passes an operational threshold, for a specific site, gateway and radio
configuration.

(The name is LoRa **CAP**acity. "LoRa" here is the radio modulation, not
low-rank adaptation.)

The engine is site-independent. A deployment is described in one file, a
*study*, and everything else is automatic. Adding a second site means adding a
second study, not editing the simulator.

## What it does

For a range of node counts it simulates the network and reports the Data
Extraction Rate (DER): the fraction of transmitted packets the gateway
actually receives. Packets are lost to collisions, to insufficient signal, and
to the receiver running out of demodulation paths. The node count at which the
mean DER crosses the threshold is reported as the capacity, with a bootstrap
confidence interval.

The collision model is a Python 3 re-implementation of LoRaSim (Bor, Roedig,
Voigt and Alonso, MSWiM 2016), extended in three ways that matter for
defending a result:

- **Multiple uplink channels are simulated directly.** Capacity is obtained
  for the whole network rather than measured on one channel and multiplied.
- **The receiver's simultaneous-demodulation limit is enforced.** It exists in
  the original as a counter that never affects the reported DER.
- **Nodes can be placed inside a real site boundary**, not only inside the
  theoretical coverage circle implied by the link budget.

## Install

Python 3.8 or newer. The simulation itself uses only the standard library.
`matplotlib` is needed for the figure, and nothing else is.

```bash
pip install -r requirements.txt
```

## Quick start

```bash
python3 run.py list                 # what studies exist
python3 run.py check iot4cows       # validate a study without running it
python3 run.py run iot4cows         # simulate, analyse, plot
```

`run` writes everything into that study's `outputs/` directory: `results.csv`,
`results.json` (which carries the full configuration alongside the numbers, so
a result file is never orphaned from the settings that produced it),
`capacity.json`, and the figure in PDF, SVG and PNG.

## Setting up a new site

```bash
python3 run.py new mysite
```

That copies the commented template into `studies/mysite/`. Then, in order:

**1. Convert the site boundary.** Draw it in Google Earth, export as KML, and
run:

```bash
python3 tools/kml_to_polygon.py mysite.kml \
    --lat <gateway_lat> --lon <gateway_lon> \
    -o studies/mysite/site_polygon.py
```

It prints the area of each polygon, whether the gateway falls inside the
boundary, and whether any polygons overlap. Check all three before moving on:
overlapping polygons inflate the area and concentrate nodes in the overlap,
and neither failure announces itself later.

Use `--list` first to see what is in the file, and `--include` to keep only
some polygons if the KML also contains roads, markers or neighbouring plots.

**2. Fit the propagation model.** This is the one thing that cannot be copied
from another site. Path loss depends on terrain, vegetation, antenna height
and where the gateway sits within the site, so a model fitted elsewhere does
not transfer however similar the two places look.

The input is a CSV of field measurements, one row per received message, with
columns for RSSI, latitude and longitude:

```
rssi,latitude,longitude
-83,3.917401,-73.820015
-91,3.918220,-73.821540
-124,3.919180,-73.803000
```

RSSI in dBm as the gateway reports it, coordinates in decimal degrees. Any
other columns are ignored, so an unmodified gateway or network-server export
usually works as is. Column names are auto-detected from common spellings and
can be overridden with `--rssi-col`, `--latitude-col` and `--longitude-col`.
Run with `--columns` to see what your file contains.

**Filter the file to one spreading factor and one gateway before fitting**, and
drop anything recorded somewhere other than the site, such as bench tests
before deployment. Each of those changes the RSSI for reasons unrelated to
distance, so mixing them yields a fit that looks perfectly healthy and is
wrong. The script warns when it detects any of the three, but it cannot know
which subset you meant to keep.

```bash
python3 tools/fit_path_loss.py field.csv \
    --lat <gateway_lat> --lon <gateway_lon> \
    --tx-power 22 --net-gain 9
```

It reports the distance distribution, runs those sanity checks, then prints two
fits, binned and unbinned, with the block to paste for each. They can differ by
enough to matter, so choose deliberately and record which one you used.

Points closer than 30 m are excluded by default, because the receiver front end
compresses at very short range and the reported RSSI understates the true
level. Move that floor with `--min-distance`. The same floor is recorded in the
study, so the model is never evaluated below the range it was fitted over.

If you have no field data for the site, say so in `path_loss_source` and use a
published model for comparable terrain. That is a defensible choice when it is
stated. Silently reusing another site's fitted coefficients is not.

**3. Fill in `studies/mysite/study.py`.** Every field is commented and the
ones with no sensible default are marked TODO.

**4. Check, then run.**

```bash
python3 run.py check mysite
python3 run.py run mysite
```

`check` reports the coverage each spreading factor reaches, the deployment
area, and anything inconsistent. Run it every time. A bad parameter does not
make the simulation fail, it makes it quietly return a wrong answer.

## What `check` catches

- Spreading factors the band does not offer on uplink. Simulating SF11 or SF12
  in a band whose 125 kHz uplink stops at SF10 misrepresents the system, and
  it is the single most common error in this kind of study.
- A sensitivity table that is not monotonic in SF.
- A reference distance outside the range the propagation model was fitted
  over. The same line expressed at d0 = 1 m is algebraically identical but
  gives a reference value far below free-space loss, which is an
  extrapolation that should not appear in a parameter table.
- A site that extends beyond the reach of a scenario's spreading factor, so
  some nodes are out of range.
- A gateway that falls outside the boundary, which usually means the wrong
  coordinates were used when converting the KML.
- Too few repetitions, or a simulated duration too short to expose collisions.

## Layout

```
run.py                      command line entry point
loracap/
    core.py                 the engine: airtime, propagation, collisions, placement
    study.py                the Study definition, loading and validation
    presets.py              regional SF ranges and datasheet sensitivity tables
    experiment.py           runs the grid, writes results
    analysis.py             capacity and bootstrap confidence interval
    plotting.py             the two-panel figure
tools/
    kml_to_polygon.py       KML boundary  ->  site_polygon.py
    fit_path_loss.py        field RSSI    ->  propagation model
studies/
    _template/              commented starting point, copied by `run.py new`
    iot4cows/               worked example, see below
```

## The worked example

`studies/iot4cows` is the configuration behind a published scalability
analysis of a cattle-monitoring deployment in Guamal, Meta, Colombia. It is
kept here because it shows every field filled with a real, sourced value, and
because it lets anyone confirm the engine still reproduces the published
figures:

| Scenario | Capacity at DER = 0.9 | 95% CI |
|---|---|---|
| SF10, conservative bound | 17.6 nodes | [16.9, 18.1] |
| SF8, deployed configuration | 61.8 nodes | [61.1, 62.7] |
| SF7, optimistic bound | 114.9 nodes | [113.9, 115.9] |

Remember which bound is which: a *lower* spreading factor has *shorter*
time-on-air and therefore *higher* capacity. The low SF is the optimistic
bound, not the conservative one. Getting this backwards is an easy mistake and
an embarrassing one to have pointed out.

## Reproducibility

Given the same study, results are bit-identical on every run: each repetition's
seed is derived deterministically from `base_seed` and the repetition index.
Change `base_seed` to confirm a reported capacity is not an artefact of one
random stream.

## Known limitations

- The propagation model is deterministic. There is no stochastic shadowing
  term, so node-to-node variation comes only from placement, channel choice
  and traffic timing, not from per-link fading.
- Nodes are placed uniformly over the site. Real deployments are rarely
  uniform: livestock congregate near water and shade, sensors follow
  infrastructure. If you have position data good enough to characterise the
  real distribution, it will be better than this assumption. Check that the
  data describes where the devices *were*, not where they were parked.
- Traffic is Poisson with the configured mean interval, inherited from
  LoRaSim, whereas most firmware transmits on a periodic timer.
- A single gateway is modelled. Multi-gateway reception would require
  extending `core.py`.
- Downlink, acknowledgements, retransmissions and join procedures are not
  modelled. This is an uplink capacity model.

## Citing

If LoRaCAP contributes to published work, please cite it. `CITATION.cff` lets
GitHub and Zenodo generate the citation for you. If you are reporting a
specific deployment, cite the paper describing that deployment as well.

A permissive licence cannot require citation, and this one does not try to.
Citing is an academic norm, not a legal one.

## Licence

Code is licensed under the MIT Licence (see `LICENSE`).

Data files, simulation outputs and figures, including the site boundary in
`studies/*/site_polygon.py` and everything under `studies/*/outputs/`, are
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Creative Commons licences are not suited to software, and MIT is not suited to
data, so the two are kept separate.

## Attribution

The collision model re-implements LoRaSim 0.2.1 (Bor, Roedig, Voigt, Alonso,
*"Do LoRa Low-Power Wide-Area Networks Scale?"*, MSWiM 2016,
<https://doi.org/10.1145/2988287.2989163>), which is licensed CC BY 4.0. No
LoRaSim source code is copied here. See `LICENSE` for the full notice.

Sensitivity values in `presets.py` are reproduced from manufacturer datasheets
and each carries its source. Only chips actually verified against a datasheet
appear there. For any other hardware, read the datasheet and put the values in
your study.
