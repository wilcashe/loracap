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
Voigt and Alonso, MSWiM 2016), extended in five ways that matter for
defending a result:

- **Multiple uplink channels are simulated directly.** Capacity is obtained
  for the whole network rather than measured on one channel and multiplied.
- **The receiver's simultaneous-demodulation limit is enforced.** It exists in
  the original as a counter that never affects the reported DER.
- **Nodes can be placed inside a real site boundary**, not only inside the
  theoretical coverage circle implied by the link budget.
- **A second receiver rule can replace LoRaSim's.** In it the receiver stays
  on the packet it synchronised to first, which is what two measurements on
  real chips show and LoRaSim's own code does not. LoRaSim's rule remains the
  default. See "The receiver rule" below.
- **Spreading factors can stop being orthogonal.** A study that names a
  measured rejection table lets a packet on one spreading factor destroy a
  much weaker one on another in the same channel. Orthogonal spreading
  factors remain the default. See "Spreading factors that are not
  orthogonal" below.

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
python3 run.py sweep iot4cows       # how much does the propagation model matter?
python3 run.py validate iot4cows    # does the engine reduce to ALOHA theory?
python3 run.py reproduce iot4cows   # regenerate every result quoted below
python3 run.py test                 # fast checks on the engine itself
python3 run.py serve                # set a new study up through a local web page
```

`run` writes everything into that study's `outputs/` directory: `results.csv`,
`results.json` (which carries the full configuration alongside the numbers, so
a result file is never orphaned from the settings that produced it),
`capacity.json`, and the figure in PDF, SVG and PNG.

## Setting up a new site

Two routes lead to the same place. The form is easier the first time; the
command line is easier once you know the fields.

```bash
python3 run.py serve                # a local page for setting a study up
```

That opens `http://127.0.0.1:8765/` in a browser. It binds to the loopback
interface only, so nothing outside your machine can reach it, and it needs no
packages beyond the ones already listed above.

The page does one thing: it **writes a `study.py`**. It is never an
alternative to that file, and nothing it offers bypasses the commands below.
Upload the KML and it shows you the area, whether the gateway falls inside the
boundary, whether polygons overlap and an outline of the result. Upload a
measurement CSV and it shows both fits side by side so you can adopt either
one. Every field is validated as you type, including the question that decides
whether the answer means anything: does each spreading factor reach the far
edge of the site. The receiver model is chosen there too: the receiver
rule, the capture threshold, whether spreading factors are orthogonal and,
under the lock rule, its two refinements, each offered with what it rests on, and the page says when the combination
has left LoRaSim's, since every result then depends on it. When you press the
button it writes
`studies/<name>/study.py` and `site_polygon.py`, shows you the file it wrote,
and from that point the study is an ordinary one, editable by hand and
identical to a study set up the long way.

Pass `--port` to move it, or `--no-browser` to print the address instead of
opening a window.

The rest of this section is that same setup, done by hand.

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
stated, and `run.py sweep` will tell you how much it actually costs you. See
"Simulating without field measurements" below. Silently reusing another site's
fitted coefficients is not defensible.

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

## Simulating without field measurements

Fitting the propagation model needs a field campaign, which not everyone has.
That looks like a blocker. Usually it is not, and `run.py sweep` shows why.

**First, where the intercept comes from.** A published exponent gives the
slope of `L(d)` and says nothing about `L(d0)`. Free-space loss is not a
usable substitute: on the one deployment here with field data it sits about
59 dB optimistic at 100 m, because a node on an animal radiates through a
body, close to wet ground and often through vegetation. Adopt it and the nodes
appear to reach enormously far, coverage never binds, and the capacity figure
is wrong in the flattering direction.

So the intercept is anchored instead to the one quantity a deployer can state
without a campaign: roughly how far the link is expected to work, at a stated
spreading factor. A single walk-out test establishes it. The anchor is an
assumption and has to be reported as one. What makes it tolerable is that
capacity does not depend on the intercept while the site stays covered, which
`--check-intercept` demonstrates below. The intercept's real job is to set
coverage, and the anchor states coverage directly.

`run.py serve` does this for you: pick the environment, say how far the link
should reach, and it fills in the exponent and derives the intercept, labels
the model as assumed rather than fitted, and holds you to the sweep afterwards.
By hand, `core.ref_loss_for_range` is the same arithmetic.

```bash
python3 run.py sweep mysite
python3 run.py sweep mysite --low 2.0 --high 3.0 --runs 10
```

It varies the path-loss exponent across a range, finds the capacity at each
value, and reports which regime the site is in. On the worked example, with
no arguments:

| Exponent | Reach | Covers site | Capacity |
|---|---|---|---|
| 2.00 | 3055 m | yes | 60.3 |
| 2.16 (this study) | 2371 m | yes | 62.0 |
| 2.25 | 2089 m | yes | 62.6 |
| 2.50 | 1542 m | yes | 64.2 |
| 2.75 | 1202 m | yes | 65.7 |
| 3.00 | 977 m | yes | 67.4 |
| 3.25 | 820 m | NO | 35.8 |
| 3.50 | 706 m | NO | no crossing |

While the site is covered, capacity spans 60.3 to 67.4, 12% of the lower value. Site radius 958 m, scenario SF8.

*Source: experiment `sweep` of `studies/iot4cows/experiments.py`, 30 runs per point, capacity by bisection on node count, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/sweep/`. Regenerate with `python3 run.py reproduce iot4cows --only sweep`.*

Capacity here is found by bisection on node count rather than on the
study's grid, which is why the fitted exponent's 62.0 is not the 61.8
quoted for SF8 elsewhere. Both are correct for their method.

The reason this works is that capacity is set by collisions, and collisions
depend on how many nodes transmit and on how different their received powers
are, since the capture effect lets a strong packet survive a weak one. The
propagation model enters only through that spread, and only while every node
stays in range.

So while the site is covered, the answer barely moves: 12% across the
range above, up to an exponent of 3.00. Between 3.00 and 3.25 the site
stops being covered and capacity falls by half. The model's intercept does
not move it at all, which you can verify rather than take on trust:

```bash
python3 run.py sweep mysite --check-intercept
```

Shifting the intercept moves every node's RSSI equally and leaves the spread
untouched, so the DER comes out identical, not merely close:

| Intercept shift | L(d0) | DER | Weak-signal losses |
|---|---|---|---|
| -10 dB | 120.30 dB | 0.935174 | 0 |
| -5 dB | 125.30 dB | 0.935174 | 0 |
| +0 dB | 130.30 dB | 0.935174 | 0 |
| +5 dB | 135.30 dB | 0.935174 | 0 |

Largest DER difference 0.00e+00, SF8 at N = 39. Invariant: yes.

*Source: experiment `intercept` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 39, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/intercept/`. Regenerate with `python3 run.py reproduce iot4cows --only intercept`.*


What does matter is binary: does the assumed model leave the whole site in
range? While it does, an assumed model is defensible provided you declare it as
assumed and report the coverage check. Once it does not, the deployment is
coverage-limited, the model decides the result, and no assumed exponent can
settle it. The sweep says so explicitly when that happens, and then you need
measurements.

**On choosing the range.** The default span of 2.0 to 3.5 is a bracket wide
enough to contain most terrestrial environments, not a recommendation for your
site.

`--terrain` takes the range from published LoRa measurement campaigns instead:

```bash
python3 run.py sweep mysite --terrain rural
```

| Environment | Observed range | Median | Studies | Frequencies |
|---|---|---|---|---|
| rural | 1.87 – 3.39 | 2.94 | 3 | 868 MHz |
| suburban | 1.47 – 4.67 | 3.54 | 10 | 868, 915 MHz |
| urban | 1.45 – 3.24 | 2.34 | 7 | 868 MHz |
| forest | 2.53 – 5.97 | 3.17 | 6 | 433, 868, 915, 920 MHz |
| campus | 2.25 – 5.30 | 3.07 | 4 | 868, 915 MHz |

*Source: `presets.TERRAIN_EXPONENTS`. Print with `python3 run.py reproduce
reference`.*

All from Table 12 of González-Palacio et al., *A Critical Review of the
Propagation Models Employed in LoRa Systems*, Sensors 24(12):3877, 2024,
[doi:10.3390/s24123877](https://doi.org/10.3390/s24123877). That review fits
`PL(d) = α + 10·β·log10(d)`, so its β is this tool's `path_loss_exponent`.

Read these as the spread actually observed under an environment label, not as
a value to adopt. The labels are the original authors', and "rural" covers
everything from open pasture to scattered woodland, which is why the ranges
are so wide. They are pooled across frequency and across distance ranges from
tens of metres to tens of kilometres. Exponents below 2 appear, so `sweep`
warns about them rather than refusing. And the review's own central argument is
that single-slope fits are often inadequate, which this simulator nonetheless
uses: a swept range is a coarser description of reality than the best available
models.

## What `check` catches

- Spreading factors the band does not offer on uplink. Simulating SF11 or SF12
  in a band whose 125 kHz uplink stops at SF10 misrepresents the system, and
  it is the single most common error in this kind of study. The check uses the
  spreading factor *and* the bandwidth, so SF7 at 500 kHz is rejected in US915
  while SF8 at 500 kHz is accepted as DR4.
- A payload larger than the data rate can carry. US915 DR0, which is SF10 at
  125 kHz, allows eleven bytes of application payload. Pair it with a 32-byte
  reading and every airtime and capacity figure that follows describes a
  transmission the band would refuse. This one was found in this repository's
  own worked example, after publication.
- A data rate that carries no application payload at all, which is CN470 DR0,
  and SF12 and SF11 anywhere a 400 ms dwell limit applies, since neither can
  complete a transmission inside it.
- A study in AU915 or AS923 that has not said which uplink dwell-time setting
  it is under. Those plans publish both, and at DR2 the ceiling is 115 bytes
  or 11, so `check` asks rather than assuming.
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

### Where the regional tables come from

`presets.DATA_RATES` and `presets.MAX_APP_PAYLOAD_BYTES` cover all eight
plans: EU868, US915, AU915, AS923, IN865, KR920, RU864 and CN470. Each data
rate carries its spreading factor, its bandwidth and the maximum application
payload from the repeater-compatible table of the LoRa Alliance's Regional
Parameters, RP002-1.0.5.

They were extracted from the [ChirpStack `lorawan`
library](https://github.com/brocaar/lorawan)'s `band` package, by parsing it
with Go's own AST rather than reading it, so the control flow that selects
each table was followed as the compiler would follow it.

US915 and EU868 were then checked line by line against the [LoRaWAN Regional
Parameters tables](https://www.thethingsnetwork.org/docs/lorawan/regional-parameters/)
and agree exactly. That second source earned its keep immediately: the first
extraction put EU868 DR4 to DR6 at 242 bytes instead of 222, because that one
file in the library spells the parameter `repeatedCompatible` and the
extractor was matching `repeaterCompatible`, so it silently read the
non-repeater table. Without an independent check it would have shipped.

All eight plans, with their transmit power tables, were then checked line by
line against RP002-1.0.5 itself, and the document's values are kept in the
test suite as an independent copy. Every data rate and payload ceiling
agreed. The IN865 power ladder did not: the library stopped at −20 dB where
the document goes to −28, and it was corrected.

US915 needed a decision rather than a correction. Its power table lists
absolute conducted levels, 30 dBm down to 2 dBm, while the text calls them
relative to the device maximum. They are read here as absolute, so a node
reduces power in 2 dB steps from its own level down to 2 dBm and no further.
For the worked example's 22 dBm collar that is the same −20 dB as before.

The optional SF6 and SF5 data rates RP002-1.0.5 added at 125 kHz are not
supported, for the reason given under "Known limitations".

## Reproducing the ancestor

The degeneracy ladder checks the engine against theory. `studies/bor2016_sn1`
and `studies/bor2016_sn3` check it against an independent published
simulation, which is a different question, and they are the thing to re-run
after any substantial change to the engine.

Both reproduce Experiment Set 1 of Bor, Roedig, Voigt and Alonso, *Do LoRa
Low-Power Wide-Area Networks Scale?*, MSWiM 2016. Every parameter comes from
the paper: Table 2 for the transmitter settings, Section 3.2 for the
propagation model, Table 1 for the measured receiver sensitivity. SN1 and SN3
differ only in the coding rate, so the pair is also a control.

Three settings are deliberately not this tool's defaults, and leaving them
alone would quietly produce a different number: one channel, because SN3
fixes the carrier frequency; no demodulator limit, because LoRaSim models no
concentrator; and their sensitivity figures, measured on an XRange SX1272,
which is a node radio rather than a gateway.

```bash
python3 run.py run bor2016_sn3
```

**The engine agrees with LoRaSim. Neither agrees with the paper.**

| | SN1 (CR 4/8) | SN3 (CR 4/5) |
|---|---|---|
| This engine | 39.0, CI [38.1, 40.1] | 51.4, CI [49.8, 52.4] |
| LoRaSim itself, run here | 38.7 | 52.3 |
| Paper, abstract, body and findings | — | 64 |
| Paper, Figure 4 caption | — | 120 |

*Source: the LoRaCAP row is experiment `headline` of
`studies/bor2016_sn1/experiments.py` and of
`studies/bor2016_sn3/experiments.py`, 15 runs per point, 17 node counts from
10 to 300, 200000 s simulated, seed 99, 2000 bootstrap replicates.
Regenerate with `python3 run.py reproduce bor2016_sn1` and `bor2016_sn3`.
The LoRaSim row comes from a run of LoRaSim outside this repository. The
Python 3 port and the script that produced it are not included yet, so that
row cannot be regenerated from here. The paper rows are quoted from the
paper.*

The SN3 figure marks the three numbers the curve is read against as
labelled vertical lines: LoRaSim's 52.3, and the paper's 64 and 120. None of
them is produced here, which is why they are marks and not curves, and
their sources are written beside them in `studies/bor2016_sn3/experiments.py`.
LoRaSim's own curve is not drawn, because the run that produced it is not
in this repository.

LoRaSim was taken from [mcbor/lorasim](https://github.com/mcbor/lorasim),
converted to Python 3 and run at the same settings. Across N = 20 to 100 the
two simulators agree within 0.009 DER at every point, this engine sitting
about 0.005 lower throughout. Airtime matches the published 1712.13 ms for
SN1 exactly.

The paper's own figure does not follow from the published code at the stated
parameters, and the paper disagrees with itself about it: 64 appears in the
abstract, the body and the findings, while Figure 4's caption says 120 for
the same configuration. That is what text and figures drifting apart looks
like, and it fits the footnote recording that every figure was regenerated
after Mariusz Slabicki found a bug that overestimated goodput.

Two things this cannot settle. The repository is a single 2021 commit with no
history, so whether it is the corrected code cannot be established from it.
And since the bug overestimated goodput, if that code is still the buggy
version then the corrected answer would be at or below 52.3, which moves it
further from 64 rather than closer.

A detail worth knowing if you ever compare against LoRaSim yourself: its
`maxDist` inverts the path-loss model in base *e* while computing the loss
itself in base 10. At these parameters that returns 99 m where the model
gives 360 m, and the paper's "the modelled communication range here is around
100 m" is that figure. It changes the placement radius, not the shape of the
received-power distribution, so it does not affect DER. This tool inverts in
base 10, and says so in `core.max_distance_m`.

One more thing the paper states plainly and is easy to miss: it fits
σ = 3.57 dB for shadowing and then sets it to zero, "since otherwise some
transmissions might not be able to reach the sink rendering our results
inconclusive". The variability was removed because it broke the result. The
section above shows what happens when you leave it in.

## Energy

Name a radio and `run` reports transmit energy and energy per extracted
message, which is Bor et al.'s network energy consumption:

```python
radio="SX1272",              # or tx_current_ma={14: 44, ...} from your datasheet
supply_voltage_v=3.0,
sleep_current_ua=2.0,        # optional, and needed for a service life
battery_capacity_mah=2400.0,
```

There is no default. Current draw belongs to the node's radio, differs by
more than a factor of two between radios at the same output power, and a
guessed one produces a battery figure that reads as authoritative and is
fiction. `check` also refuses a transmit power outside the table rather than
extrapolating, because the power amplifier stages switch inside it: in the
SX1272 figures the step from 14 to 15 dBm nearly doubles the draw. The worked
example trips exactly this, transmitting at 22 dBm with a radio that is not
an SX1272 at all.

Only transmission is counted. Receive windows need downlink timing this
engine does not model, and sleep draw belongs to the firmware rather than to
the network, so a service life needs `sleep_current_ua` and is declined
without it. Which of the two terms dominates is reported rather than assumed,
because it is not the same for every deployment. In the SN3 reproduction, at
a 1000 s interval with 1.3 s of SF12 airtime and an assumed 2 uA of sleep
draw, transmitting is 96.7% of the average current, and sleep overtakes it
past an interval of 8.1 hours. On a node whose idle draw is milliamps rather
than microamps, a GNSS receiver kept tracking for example, the balance is
reversed, so recompute it for your own hardware rather than borrowing either
figure.

**Checked against LoRaSim**, which computes energy for the same configuration
with the same current table. At N = 64 LoRaSim reported 2215.4 J, and this
engine now gives 2228.8 J, 0.6% apart. The LoRaSim figure comes from a run
outside this repository, so the comparison will be regenerable once the
LoRaSim port is added.

**What it says about ADR**, on the SN3 reproduction in EU868, as energy per
extracted message against fixed SF12:

| N | MULTI vs SF12 | ADR vs SF12 |
|---|---|---|
| 40 | -75% | -25% |
| 64 | -76% | -25% |
| 100 | -77% | -27% |
| 200 | -81% | -34% |

- Mean transmit-power reduction under MULTI: 0.0 dB, averaged over those N.
- Mean transmit-power reduction under ADR: 0.1 dB, averaged over those N.
- Transmit energy per run under SF12: N = 40: 1391.5 J, N = 64: 2228.8 J, N = 100: 3486.7 J, N = 200: 6967.4 J.
- At a 1000 s interval with 2 uA of sleep draw, transmitting is 96.7% of the average current under SF12. Sleep overtakes it past 8.1 h.

*Source: experiment `energy` of `studies/bor2016_sn3/experiments.py`, 15 runs per point, N = 40, 64, 100, 200, 200000 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/bor2016_sn3/outputs/energy/`. Regenerate with `python3 run.py reproduce bor2016_sn3 --only energy`.*

Ideal assignment is in the same range as Bor et al.'s reported 90% saving at
N = 200. Realistic ADR saves about a third as much, and the reason is the
same margin that helps its capacity in the worked example: keeping 10 dB in
hand pushes nodes to slower data rates, airtime dominates energy, and the
power reduction is too small to compensate, 0.1 dB on average here.

So the margin buys capacity and costs energy, but read where each half was
measured. The capacity gain is on the worked example, US915 at a 15 s
interval, in "Scenarios, and what ADR costs" below. The energy cost is on
the SN3 reproduction, EU868 at 1000 s. It is one mechanism with opposite
signs, shown on two different studies, and the two figures should not be
combined into one trade-off for a single site until one study measures
both.

**Under the lock receiver rule** the energy comparison barely moves. Energy
per extracted message depends on how many packets get through, so it depends
on the rule, but here the rule shifts both scenarios and the reference
together:

| N | MULTI vs SF12 | ADR vs SF12 |
|---|---|---|
| 40 | -75% | -24% |
| 64 | -75% | -24% |
| 100 | -76% | -26% |
| 200 | -79% | -31% |

*Source: experiment `energy_lock` of `studies/bor2016_sn3/experiments.py`, 15 runs per point, N = 40, 64, 100, 200, 200000 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/bor2016_sn3/outputs/energy_lock/`. Regenerate with `python3 run.py reproduce bor2016_sn3 --only energy_lock`.*

ADR still saves about a third of what ideal assignment saves, so the
margin's energy cost holds under both rules. The rule changes no airtime and
no transmit power, which is why transmit energy per run is the same under
both. Only the number of messages it buys differs.

## What does not measuring cost?

```bash
python3 run.py compare iot4cows                    # terrain exponent, anchored intercept
python3 run.py compare iot4cows --keep-intercept   # exponent alone
```

This resolves one study twice, once under its fitted model and once under an
assumed one, and puts the capacities and their intervals side by side. It is
only meaningful at a site that **has** measurements, because the fitted model
is the ground truth the assumed one is checked against, which is the opposite
of who it serves. A site without a campaign is served by `sweep`. This exists
to validate that route, not to replace it.

On the worked example, at DER = 0.9, first changing the exponent alone:

| Model | SF7 | SF8 | SF9 |
|---|---|---|---|
| fitted (field) | 114.9 [113.9, 115.9] | 61.8 [61.1, 62.6] | 33.9 [33.0, 34.7] |
| exponent only (rural) | 89.4 [83.7, 94.9] | 67.1 [66.3, 67.9] | 36.8 [36.2, 37.4] |

Reach as a multiple of the site radius:

- fitted (field): SF7 1.90, SF8 2.48, SF9 3.23
- exponent only (rural): SF7 0.88, SF8 1.07, SF9 1.30

*Source: experiment `compare_exponent` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/compare_exponent/`. Regenerate with `python3 run.py reproduce iot4cows --only compare_exponent`.*

then assuming the whole model, as a deployer with no measurements must:

| Model | SF7 | SF8 | SF9 |
|---|---|---|---|
| fitted (field) | 114.9 [113.9, 115.9] | 61.8 [61.1, 62.6] | 33.9 [33.0, 34.7] |
| assumed (rural) | no crossing - | 20.4 [3.4, 23.9] | 36.8 [36.2, 37.4] |

Reach as a multiple of the site radius:

- fitted (field): SF7 1.90, SF8 2.48, SF9 3.23
- assumed (rural): SF7 0.68, SF8 0.82, SF9 1.00

*Source: experiment `compare_anchored` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/compare_anchored/`. Regenerate with `python3 run.py reproduce iot4cows --only compare_anchored`.*

**The exponent is worth about 8% while coverage holds.** Change it from the
fitted 2.16 to rural's published median of 2.94 and keep the measured
intercept, and SF8 moves from 61.8 to 67.1, SF9 from 33.9 to 36.8. That
agrees with what `sweep` reports over the same range, and it moves *upward*:
a steeper exponent widens the spread of received powers, which feeds the
capture effect. SF7 is the exception, and it is not an exponent effect: at
2.94 its reach falls to 0.88 of the site radius, the site is no longer
covered, and capacity drops 22% to 89.4 with a much wider interval.

**The anchor is worth everything else.** Add the realistic part, that a
deployer with no measurements must also guess the intercept, and SF8 falls to
20.4 and SF7 stops crossing at all. The reason is visible in the reach
ratios: the fitted model turns out to have 1.9 to 3.2 times the reach the
site needs, and an expected-reach statement cannot know that margin is
there. Anchoring to "the link reaches the far edge" treats a lower bound
as an equality and throws the margin away.

So the cost of not measuring, at this site, is almost entirely **the cost of
not knowing your margin**, not the cost of getting the exponent wrong. That
is worth saying because the exponent is what the literature argues about.

One site establishes nothing a reviewer will accept. Run it wherever you have
measurements: two, with different geometry and terrain, make it evidence.

## Shadowing, and why it is not a small correction

Set `shadowing_sigma_db` and two nodes the same distance from the gateway stop
receiving identical power. The draw is Gaussian in dB, made once per node and
kept: this is obstruction belonging to where the node is, a hollow, a stand of
trees, a collar facing the wrong way. A node behind a hill stays behind it.

`fading_sigma_db` is the other thing, drawn per packet, for a channel that
changes between transmissions. It averages out across many packets, so it
moves DER far less than its size suggests. A residual sigma fitted from field
data mixes the two and cannot tell them apart, so putting all of it into
shadowing is the conservative reading for a static deployment.

`fit_path_loss` reports the sigma to use. Take the **unbinned** one: binning
averages away the very scatter sigma is meant to measure. On the worked
example the unbinned fit gives 7.41 dB and the binned one 3.47, and using the
second would understate shadowing by half.

What it does, at DER = 0.9 on the worked example, with the fitted 7.41 dB
among the values tried:

| Configuration | SF8 | MULTI | ADR | Excluded, worst case |
|---|---|---|---|---|
| σ = 0 dB | 61.8 [61.1, 62.6] | 114.9 [113.9, 115.9] | 145.1 [143.1, 147.4] | 0.0% |
| σ = 4 dB | 66.3 [65.0, 67.3] | 124.7 [123.4, 126.2] | 149.5 [146.3, 153.3] | 0.2% |
| σ = 7.41 dB | 53.4 [49.0, 57.5] | 145.5 [144.0, 147.4] | 148.2 [146.3, 150.6] | 4.0% |
| σ = 10 dB | 4.9 [3.6, 25.9] | 162.6 [160.5, 164.5] | 150.7 [148.2, 153.9] | 6.7% |

*Source: experiment `shadowing` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/shadowing/`. Regenerate with `python3 run.py reproduce iot4cows --only shadowing`.*

**On a fixed data rate it is punishing.** Capacity rises a little to σ = 4,
because a wider spread of received powers feeds the capture effect, then
turns and collapses: 66.3, then 53.4 at the measured 7.41 dB. At 10 dB the
fixed rate is no longer collision-limited at all. About 9% of its packets
are lost to weak signal before congestion begins, DER sits at the threshold
from the first few nodes, and the crossing at 4.9 with an interval reaching
26 says only that SF8 cannot serve this site under that much shadowing.
Weak-signal losses near capacity go from none to 2.9% at 7.41 dB, and the
interval widens from 1.6 nodes to 8.6, which is its own finding: with
realistic shadowing, whether a few unlucky nodes land below sensitivity
starts to dominate the answer, and a single capacity figure means much less
than the deterministic model suggests. The losses behind these statements
are in `studies/iot4cows/outputs/shadowing/tables.md`.

**Adaptive scenarios degrade far more gracefully**, because a shadowed node
is moved to a slower data rate instead of being left to fail. Read the next
paragraph before quoting their rising figures, though.

**But read the right number.** A node with no usable data rate never
transmits, so it cannot lower the DER of the nodes that did. Left alone, a
scenario can post a rising capacity while quietly excluding part of the
deployment. `run` detects this and reports both readings:

```
  Up to 4.0% of nodes have no usable data rate at some node count.
  Those nodes never transmit, so they cannot lower the DER above.
  Counting them as lost traffic instead:
    SF8              53.4  ->          53.4
    MULTI           145.5  ->         128.3
    ADR             148.2  ->         129.9
```

That is the 7.41 dB row. Across the whole sweep:

| Configuration | Scenario | Capacity, `der` | Capacity, `der_fleet` | Excluded, worst case |
|---|---|---|---|---|
| σ = 0 dB | SF8 | 61.8 | 61.8 | 0.0% |
| σ = 0 dB | MULTI | 114.9 | 114.9 | 0.0% |
| σ = 0 dB | ADR | 145.1 | 145.1 | 0.0% |
| σ = 4 dB | SF8 | 66.3 | 66.3 | 0.0% |
| σ = 4 dB | MULTI | 124.7 | 124.7 | 0.2% |
| σ = 4 dB | ADR | 149.5 | 148.7 | 0.2% |
| σ = 7.41 dB | SF8 | 53.4 | 53.4 | 0.0% |
| σ = 7.41 dB | MULTI | 145.5 | 128.3 | 4.0% |
| σ = 7.41 dB | ADR | 148.2 | 129.9 | 4.0% |
| σ = 10 dB | SF8 | 4.9 | 4.9 | 0.0% |
| σ = 10 dB | MULTI | 162.6 | 96.2 | 6.7% |
| σ = 10 dB | ADR | 150.7 | 88.8 | 6.7% |

*Source: experiment `shadowing` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/shadowing/`. Regenerate with `python3 run.py reproduce iot4cows --only shadowing`.*

Counted over the intended fleet, ADR falls steadily with shadowing, from
145.1 to 129.9 to 88.8, while the fixed rate collapses. Both readings are
in `results.csv` for every run, and `capacity.json` stores both
capacities.

## Scenarios, and what ADR costs

A scenario is one configuration of the whole network, and it is the axis a
figure compares along. Three kinds exist.

`SF8`, or any `SF<n>`, is a fixed data rate. Every node uses it, at full
power.

`MULTI` gives every node the lowest-airtime spreading factor its link
reaches, decided from its distance. That is ideal, instantly converged
assignment, with no margin and no power control. It is a bound, not a
network.

`ADR` is what a converged real network settles into. It picks the fastest
data rate whose sensitivity is met with `adr_margin_db` to spare, 10 dB by
default, then spends whatever margin is left reducing transmit power down the
regional offset ladder, in the 2 dB steps every plan uses.

The loop itself is out of scope. There is no convergence time, no
instability, and no downlink cost for the `LinkADRReq` that would carry the
decision, because this engine has no downlink at all. Capacity is a
steady-state property, so the state ADR settles into is what matters here.
For the dynamics, use FLoRa or the ns-3 `lorawan` module.

On the worked example, at DER = 0.9:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| base | SF8 | 61.8 | [61.1, 62.6] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| base | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| base | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| ADR, margin only | ADR | 170.8 | [168.9, 172.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `adr` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/adr/`. Regenerate with `python3 run.py reproduce iot4cows --only adr`.*

Two opposing effects, and neither is the obvious one.

**The margin is not a cost, it is a gain, and a large one.** Ideal assignment
puts all 300 nodes on SF7, because every point of this site is inside SF7's
reach, which is also why MULTI's capacity is SF7's to the last digit. One
spreading factor means every node colliding with every other. Insisting on
10 dB of margin moves about 66 of the 300 nodes to SF8 and 15 to SF9, and
the engine treats spreading factors as orthogonal, so those stop colliding
with the SF7 traffic altogether. Capacity goes from 114.9 to 170.8. Within
the model, the idealisation was costing capacity by throwing orthogonality
away.

That gain is only as good as the orthogonality it rests on, and real
spreading factors are not perfectly orthogonal. Croce et al. measured an
SX1272 losing an SF7 packet to an interferer on another spreading factor
received 8 to 9 dB stronger, and an SF8 packet at 11 to 13 dB (Table I of
the paper cited under "Known limitations"). With orthogonal spreading
factors, the default, 170.8 is therefore an upper bound on what the margin
buys here. With Croce et al.'s table the margin alone gives 153.2, still a
gain over MULTI, and power control then costs 5% rather than 15%. "Spreading
factors that are not orthogonal" has the table and its limits.

**Under LoRaSim's receiver rule, power control is a cost, and it is the
capture effect being spent.** The capture effect resolves a collision only
when the two signals differ by more than `capture_threshold_db`, 6 dB by
default. Power control exists to bring every node to the same level at the
gateway, and it does: the largest range
of received power within a spreading factor falls from 26.9 dB to 6.4 dB.
No two nodes on one spreading factor then differ by more than 6.4 dB, so
capture can resolve only the few most extreme pairs. Capacity drops from
170.8 to 145.1, 15%.

That conclusion belongs to the receiver rule, not to the network. Under the
lock rule described in the next section, power control is a gain at this
site instead, unless that rule decides the locked packet's survival with
Eigner's per-SF table, in which case it is neither. Neither rule has been
checked against the capacity of a real network. Read "The receiver rule"
before quoting either sign.

Net, realistic ADR beats ideal assignment here, 145.1 against 114.9, at the
default 6 dB threshold. At 1 dB under LoRaSim's rule the two cannot be told
apart, 167.1 [164.9, 169.2] against 165.5 [164.6, 166.4], so this is a
result of the threshold as well as of the site (see "Spreading factors that
are not orthogonal"). It is not a general law, which is the point: a reporting
interval, a site radius or a payload that changes where nodes land on the
ladder will change the balance, and the two mechanisms pull in opposite
directions. It is worth simulating rather than reasoning about.

An adaptive scenario will not assign a data rate that cannot carry the study's
payload, because a network server would not either. In US915 with 32 bytes
that silently removes SF10, whose DR0 ceiling is eleven bytes, and `check`
says so.

## The receiver rule

When two packets on the same channel and spreading factor overlap, something
has to decide which one the gateway keeps. That decision is the receiver
rule, and it is the one part of the engine that summarises the chip rather
than the radio link.

`receiver_model="lorasim"`, the default, is LoRaSim's equation 11. If the
later packet's critical preamble section is overlapped, power decides at any
offset: within `capture_threshold_db` of each other both are lost, and beyond
it the stronger survives, whichever arrived first.

`receiver_model="lock"` keeps that rule only for a packet arriving within the
first three preamble symbols of another. Past that point the receiver has
synchronised to the first packet and stays on it. The later packet is lost
whatever its power, and if it is stronger by the capture threshold it
corrupts the first one too. Two measurements on two chips show this, and
LoRaSim's own code does not:

- Bor et al., MSWiM 2016, Figure 3, on an SX1272: a strong packet is decoded
  arriving early or up to three symbols late, and with a larger offset "no
  transmission gets through".
- Haxhibeqiri et al., Sensors 17(6):1193, 2017, Tables 2 to 6, on an SX1301:
  at equal power the second packet is lost and the first received in about
  90% of cases, and a packet 12 dB stronger arriving after the header is lost
  while the first comes through with a bad CRC.

```python
receiver_model="lock",
```

On the worked example, at DER = 0.9:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule | SF8 | 61.8 | [61.1, 62.6] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| LoRaSim rule | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule | SF8 | 81.7 | [81.1, 82.2] | 26.8 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule | MULTI | 151.1 | [150.0, 152.3] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only | ADR | 170.8 | [168.9, 172.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only | ADR | 246.2 | [243.1, 249.9] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 1 dB threshold | ADR | 167.1 | [164.9, 169.2] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 1 dB threshold, ADR margin only | ADR | 236.6 | [235.1, 238.1] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 3 dB threshold | ADR | 145.5 | [143.5, 147.9] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 3 dB threshold, ADR margin only | ADR | 195.9 | [194.4, 197.3] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 1 dB threshold | ADR | 249.4 | [246.4, 252.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 1 dB threshold, ADR margin only | ADR | 210.8 | [207.6, 214.4] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 3 dB threshold | ADR | 274.2 | [271.7, 276.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 3 dB threshold, ADR margin only | ADR | 228.7 | [225.4, 231.7] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `receiver` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/receiver/`. Regenerate with `python3 run.py reproduce iot4cows --only receiver`.*

The experiment also draws the two rules side by side,
`outputs/receiver/iot4cows_capacity_receiver.{pdf,svg,png}`: DER against
node count for SF8, MULTI and ADR, one panel per rule on a shared DER axis.
The number printed at each crossing, with its 95% interval as a bar along
the threshold, is read from the panel's `capacity.json`, so it is the
table's number, not one the plotting code recomputed. Each panel's title
names the rule and the capture threshold, since every capacity on it is
conditional on both. The threshold and power-control variants stay in the
table only.

**The rule moves capacity more than the propagation exponent does** while
the site is covered: SF8 goes from 61.8 to 81.7, 32%, where the exponent
moved it by 12% at most for as long as the site stayed covered. Neither
rule has been checked against the measured capacity of a network, so this
is a sensitivity
to a modelling assumption, not a known error in either direction.

**The sign of power control's effect depends on the rule.** Under LoRaSim's
rule, power control costs capacity at every threshold tried: 170.8 to 145.1
at 6 dB, 195.9 to 145.5 at 3 dB, 236.6 to 167.1 at 1 dB. Under the lock rule
it gains at every threshold: 246.2 to 275.1, 228.7 to 274.2 and 210.8 to
249.4. The mechanism is the same pair of packets read two ways. Power control
brings received powers within a few dB of each other. Under LoRaSim's rule
such a pair loses both packets. Under the lock rule the first one survives,
and what power control removes is the stronger late arrival that would have
destroyed both. The margin's own gain, MULTI against ADR without power
control, holds under both rules at 6 dB. The lock rule's half of this rests
on the locked packet surviving a later one up to the capture threshold
stronger. Decided instead by Eigner's per-SF table, below, the gain
disappears.

**The threshold is the other large assumption.** Haxhibeqiri et al. measured
pairs within about 2 dB of each other and pairs 6 to 14 dB apart, and nothing
in between. Other measurements cover the gap, and all of them point below
6 dB. Fernandes et al. (SX1272, packets starting together) received the
stronger packet 82% of the time at 2 dB and 97% at 3 dB. Croce et al.
(SX1272, random offsets) put the threshold at 1 dB on every spreading factor.
Eigner (SX1301) found the first packet surviving a later one of equal power
or less at SF7 and SF8, and needing up to 2 dB at SF11 and SF12. None of the
three declares the coding rate of its collision tests, and two used a node
radio rather than a gateway concentrator, so 6 dB stays a choice, inherited
from LoRaSim, and on this evidence a pessimistic one. Lowering it from 6 to 1 dB moves ADR without
power control from 170.8 to 236.6 under LoRaSim's rule, and from 246.2 to
210.8 under the lock rule, in opposite directions. At 1 dB that ordering
reverses, 236.6 under LoRaSim's rule against 210.8 under the lock rule, so
"the lock rule gives more capacity" holds at the default threshold and not
in general.

**What the measurements do not cover**, and how the rule fills each gap:

- Both used two transmitters. With three or more overlapping packets the rule
  is applied pair by pair, as both papers' own models do, and how much of a
  result rests on that extrapolation has not been measured here.
- The first of two equal-power packets counts as received every time, where
  the measurement gives about 90%. That overstates DER under the lock rule.
- Haxhibeqiri et al. saw the SX1301 resynchronise to a stronger packet
  arriving during the header, in a window too narrow to place. That recapture
  is left out, which understates DER.
- The measurements used SF7 and SF12 at 868 MHz. The worked example runs SF7
  to SF9 in US915 on an SX1308.

**Validated the same way as the rest of the engine.** A lock study's
degeneracy ladder gains one rung, "lorasim rule", which swaps the rule back
and is checked for no direction, since the lock rule helps one kind of pair
and hurts another. Below it the ladder is the LoRaSim ladder. The lock rule
also has an analytical case of its own: on one channel with no capture and no
preamble allowance, a packet survives exactly when nothing is already in the
air as it starts, which is exp(-G), half ALOHA's vulnerable period.

| N | G | full model | lorasim rule | no demod limit | single channel | no capture | no preamble | ALOHA |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.089 | 0.9879 | 0.9825 | 0.9825 | 0.8692 | 0.8454 | 0.8386 | 0.8368 |
| 30 | 0.267 | 0.9618 | 0.9497 | 0.9497 | 0.6682 | 0.6014 | 0.5867 | 0.5859 |
| 60 | 0.535 | 0.9249 | 0.9022 | 0.9022 | 0.4603 | 0.3609 | 0.3438 | 0.3433 |
| 100 | 0.891 | 0.8791 | 0.8446 | 0.8446 | 0.2925 | 0.1831 | 0.1688 | 0.1683 |
| 200 | 1.782 | 0.7717 | 0.7170 | 0.7172 | 0.1214 | 0.0331 | 0.0282 | 0.0283 |

What each mechanism is worth at N = 200, as the DER it adds:

- receiver lock: +0.0547 (0.7717 with it, 0.7170 without)
- demodulator limit: -0.0002 (0.7170 with it, 0.7172 without)
- multiple channels: +0.5958 (0.7172 with it, 0.1214 without)
- capture effect: +0.0883 (0.1214 with it, 0.0331 without)
- preamble allowance: +0.0049 (0.0331 with it, 0.0282 without)
- residual against ALOHA: -0.0002

The receiver lock is checked for no direction: it saves the first of two equal-power packets and loses both when the later one is stronger, so its sign depends on the site.

The lock rule's own bound, on one channel with no capture and no preamble allowance:

| N | first-come | exp(-G) |
|---|---|---|
| 10 | 0.9156 | 0.9148 |
| 30 | 0.7661 | 0.7655 |
| 60 | 0.5861 | 0.5859 |
| 100 | 0.4110 | 0.4103 |
| 200 | 0.1684 | 0.1683 |

Verdict: directions hold, 5 of 5 points within 3 standard errors of the bound. 5 of 5 first-come points within 3 standard errors of exp(-G). PASS.

*Source: experiment `validation_lock` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 10, 30, 60, 100, 200, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/validation_lock/`. Regenerate with `python3 run.py reproduce iot4cows --only validation_lock`.*

The figure `validate` writes for a lock study draws the first-come runs and
exp(-G) beside the ALOHA bound.

### Two refinements of the lock rule

The lock rule as described above uses the capture threshold for every
decision, and leaves out the header recapture both measurements saw. Two
options, valid only with `receiver_model="lock"` and off by default, refine
it:

```python
lock_survival="EIGNER2021_SX1301",   # per-SF survival of the locked packet
header_recapture=True,               # a stronger arrival in the header takes over
```

- **`lock_survival`** decides, past the lock window, whether the locked
  packet survives a later one. Eigner (diploma thesis, TU Wien, 2021,
  Table 5.1, SX1301) gives the SIR the first packet needs for more than 99%
  delivery: 0 dB at SF7 and SF8, 0.4 dB at SF9, 1.3 dB at SF10, 2 dB at SF11
  and SF12. So at SF7 an equal later packet no longer harms the locked one,
  while any stronger one does, and at SF12 even an equal one does. Being 99%
  points used as a step, the values are pessimistic where the transition is
  wide: at SF12 and equal power the step loses every locked packet, where the
  same thesis measured 68%.
- **`header_recapture`**: a later packet stronger by the capture threshold
  that arrives during the locked packet's header, taken as the eight
  symbols after its preamble, makes the receiver drop the locked packet on
  its header CRC and receive the newcomer. Haxhibeqiri et al. saw it at SF7
  up to 20 ms, inside those eight symbols, and saw none at SF12 at 600 ms,
  also inside them, so no window measured in symbols fits both.

`check` refuses either option under LoRaSim's rule, where the engine would
ignore it, and the web form offers them only while the lock rule is chosen.

Each is checked against a closed form in `tests/test_lock_refinements.py`.
With the survival table, equal power and the receiver locking on arrival,
SF7 lands on the first-come bound exp(-G) and SF12 on pure ALOHA's exp(-2G).
With recapture and two power classes 10 dB apart, each class lands on its
own formula, the strong one gaining exactly the header's length of
protection from weak packets ahead of it.

**What they change at the worked example**, against the unrefined lock rule
in experiment `receiver` (SF8 81.7, MULTI 151.1, ADR 275.1, ADR margin only
246.2), at the default 6 dB threshold:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| lock rule, Eigner survival | SF8 | 65.9 | [65.1, 66.7] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, Eigner survival | MULTI | 122.6 | [121.9, 123.3] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Eigner survival | ADR | 190.8 | [188.5, 192.8] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival, ADR margin only | ADR | 192.2 | [190.1, 194.1] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, header recapture | SF8 | 83.4 | [82.9, 83.8] | 26.8 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, header recapture | MULTI | 154.1 | [153.0, 155.2] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, header recapture | ADR | 275.2 | [272.8, 277.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, header recapture, ADR margin only | ADR | 250.0 | [246.8, 253.8] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival and header recapture | SF8 | 67.1 | [66.4, 67.8] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, Eigner survival and header recapture | MULTI | 124.7 | [123.9, 125.5] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Eigner survival and header recapture | ADR | 190.8 | [188.5, 192.9] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival and header recapture, ADR margin only | ADR | 194.5 | [192.6, 196.4] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `lock_refined` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/lock_refined/`. Regenerate with `python3 run.py reproduce iot4cows --only lock_refined`.*

- **Recapture barely matters here**: 2% or less in every scenario. It needs
  a much stronger packet to land in an eight-symbol window, and that is
  rare.
- **The survival table matters a great deal**: about 19% off SF8 and MULTI,
  31% off ADR and 22% off ADR without power control. At SF7 and SF8 it
  makes a later packet stronger by any margin fatal to the locked one,
  where the unrefined rule needed 6 dB.
- **Under it, power control stops being a gain.** ADR with power control
  gives 190.8 [188.5, 192.8] and without it 192.2 [190.1, 194.1]: no
  distinguishable difference, where the unrefined lock rule found a 12%
  gain. With recapture as well, 190.8 against 194.5, a 2% cost with
  intervals that barely separate. So the reversal of power control's sign
  between the two rules depends on how the lock rule decides the locked
  packet's survival, and on a table measured at its 99% point.
- **The margin's gain over MULTI survives**: 57% with the survival table,
  62% with recapture, 56% with both.

## Spreading factors that are not orthogonal

LoRaSim, and this engine by default, let packets collide only when they share
a channel and a spreading factor. Spreading factors are quasi-orthogonal, not
orthogonal: a packet on one can destroy a much weaker packet on another. A
study opts in with one line:

```python
inter_sf_rejection="EIGNER2021_SX1301",   # or "CROCE2020_SX1272"
```

or with a table of its own, `{reference SF: {interfering SF: minimum SIR in
dB}}`. `check` says which is in force, and refuses a table that leaves out a
pair of spreading factors the study uses.

**The tables.** Two are shipped, one per chip family, and they agree within
1.5 dB everywhere. Table I of Croce, Gucciardo, Mangione, Santaromita and
Tinnirello, *"LoRa Technology Demystified: From Link Behavior to Cell-Level
Performance"*, IEEE Trans. Wireless Commun. 19(2):822-834, 2020,
<https://doi.org/10.1109/TWC.2019.2948872>, was measured on an SX1272 node
radio. Table 5.2 of Eigner, *"Interference Analysis of LoRaWAN Systems"*,
diploma thesis, TU Wien, 2021, was measured on an SX1301 concentrator at
125 kHz, the gateway chip family the shipped studies use (design item 19).
In both, an SF7 packet is lost to an interferer on another spreading factor
8 to 9.5 dB stronger than it, an SF12 packet only at 22.5 to 25 dB. The
sources sit beside the values in `presets.INTER_SF_REJECTION_DB`.

**The rule** (`core.inter_sf_losses`). Two packets on one channel and
different spreading factors are each judged against the other on their own
row of the table: a packet is lost when its SIR falls below the entry and the
overlap covers at least one of its symbols. The floor of one symbol is the
measurement's own protocol, which guaranteed at least that much overlap.
Neither the receiver rule nor the preamble allowance enters, because both
were measured within one spreading factor. All the measured entries are
negative, so two packets of equal power never harm each other across
spreading factors.

**How it was checked.** All in the fast suite, `tests/test_inter_sf.py`.

- The golden engine output is unchanged with the option off.
- With every packet at one power the table must change nothing, and it
  changes nothing exactly, while same-SF collisions are plentiful.
- With a table that makes every overlap destructive, on one channel with no
  capture and no preamble allowance, two Poisson streams on SF7 and SF9 must
  land on their closed-form bound,
  `DER_i = exp(-2·λ_i·T_i) · exp(-λ_k·(T_i + T_k - 2·t_sym,i))`, and both do.
- Every boundary is pinned: a threshold reached exactly is survived, an
  overlap of exactly one symbol counts, each packet uses its own row and its
  own symbol length.

**What it changes at the worked example**, at DER = 0.9:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, orthogonal SFs | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, orthogonal SFs | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only, orthogonal SFs | ADR | 170.8 | [168.9, 172.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, Croce rejection | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only, Croce rejection | ADR | 153.2 | [151.4, 155.0] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, orthogonal SFs | MULTI | 151.1 | [150.0, 152.3] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, orthogonal SFs | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only, orthogonal SFs | ADR | 246.2 | [243.1, 249.9] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection | MULTI | 151.1 | [150.0, 152.3] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Croce rejection | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only, Croce rejection | ADR | 211.6 | [208.6, 215.1] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `inter_sf` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf`.*

Read with the losses table that `reproduce` prints beside it, these rows say
four things, each conditional on the table and on the 6 dB same-SF threshold:

- **With power control nothing moves.** ADR comes out identical under both
  rules, and no packet is lost to another spreading factor. Power control
  turns each node down until it arrives a fixed margin above its own data
  rate's sensitivity, so a near SF7 node no longer arrives far above a far
  SF8 or SF9 one, and at this site the table found no packet to take. MULTI
  does not move either, trivially: at this site it puts every node on SF7.
- **Without power control the margin's gain shrinks.** Near nodes on SF7 now
  bury far ones on SF8 and SF9. ADR with the margin alone falls from 170.8
  to 153.2 under LoRaSim's rule and from 246.2 to 211.6 under the lock rule,
  with about 1.0% and 1.4% of transmitted packets lost to another spreading
  factor at those points.
- **The margin's gain survives.** Against MULTI it is 114.9 to 153.2 under
  LoRaSim's rule and 151.1 to 211.6 under the lock rule, a third and two
  fifths more, where with orthogonal spreading factors it was about a half
  and two thirds.
- **Power control's sign survives, and its size changes.** Under LoRaSim's
  rule it still costs capacity, 153.2 to 145.1 instead of 170.8 to 145.1.
  Under the lock rule it still gains, 211.6 to 275.1 instead of 246.2 to
  275.1. What power control gives up in capture it now partly buys back in
  protection from the other spreading factors, which an orthogonal model
  cannot see.

**At the lower same-SF thresholds** the table was run again at 1 and 3 dB,
for ADR with and without power control under both rules. The orthogonal
counterpart of every row is in experiment `receiver`:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, Croce rejection, 1 dB threshold | ADR | 167.1 | [164.9, 169.2] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 204.7 | [203.2, 206.4] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 3 dB threshold | ADR | 145.5 | [143.5, 147.9] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 173.3 | [172.0, 174.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 1 dB threshold | ADR | 249.4 | [246.4, 252.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 184.8 | [182.1, 187.2] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 3 dB threshold | ADR | 274.2 | [271.7, 276.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 198.5 | [196.1, 201.0] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `inter_sf_threshold` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf_threshold/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf_threshold`.*

The pattern of 6 dB holds at both thresholds. With power control the table
changes nothing. Without it, capacity falls by 11 to 14% under either rule.
And the sign of power control survives every combination tried: a cost
under LoRaSim's rule (18%, 16% and 5% at 1, 3 and 6 dB), a gain under the
lock rule (35%, 38% and 30%).

MULTI was run at the same thresholds to read the margin's gain there. At
this site MULTI puts every node on SF7, so the rejection table has nothing
to act on and the rows hold with or without it:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, 1 dB threshold | MULTI | 165.5 | [164.6, 166.4] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, 3 dB threshold | MULTI | 137.8 | [136.8, 138.8] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, 1 dB threshold | MULTI | 129.4 | [128.6, 130.3] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, 3 dB threshold | MULTI | 138.5 | [137.8, 139.3] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `multi_threshold` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/multi_threshold/`. Regenerate with `python3 run.py reproduce iot4cows --only multi_threshold`.*

The margin's gain over MULTI survives every combination: 42 to 49% under
LoRaSim's rule and 63 to 65% under the lock rule with orthogonal spreading
factors, 24 to 33% and 40 to 43% with the table. What does not survive is
realistic ADR beating ideal assignment under LoRaSim's rule. Its lead over
MULTI is 26% at 6 dB, 6% at 3 dB and nothing distinguishable at 1 dB, where
the intervals overlap. Under the lock rule it leads by 82 to 98% at all
three. MULTI under the lock rule also falls as the threshold drops, 151.1,
138.5 and 129.4 at 6, 3 and 1 dB, because a later packet stronger by the
threshold destroys the one the receiver locked onto, and a lower threshold
makes that more common.

**With the concentrator's table** (Eigner, SX1301), ADR with and without
power control under both rules, beside the Croce rows above:

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, Eigner rejection | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Eigner rejection, ADR margin only | ADR | 153.0 | [151.1, 154.7] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner rejection | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner rejection, ADR margin only | ADR | 211.1 | [208.1, 214.6] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `inter_sf_eigner` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf_eigner/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf_eigner`.*

The two tables give the same answer at this site. ADR without power control
falls to 153.0 under LoRaSim's rule and 211.1 under the lock rule, against
153.2 and 211.6 with Croce et al.'s, inside each other's intervals, and ADR
with power control is untouched by either. So item 14's findings do not
rest on the table having been measured on a node radio.

**What it does not cover.** Croce et al.'s table was measured on an SX1272
node radio, not on a gateway concentrator such as the SX1308 of the worked
example, and the paper does not state the bandwidth or coding rate of the
test. Eigner's was measured on an SX1301 at 125 kHz, which closes the first
gap but not the second: its coding rate is not stated either.
Interference from several packets on other spreading factors is judged one
packet at a time rather than summed. The threshold is a step. Shorter
overlaps than one symbol are left harmless because they were not measured.
And all of it is at one site.

## Tests

```bash
python3 run.py test            # or: python3 -m unittest discover -s tests
```

336 checks, about ten seconds, standard library only like the rest of the
package, so nothing needs installing. They exist because a change to the
engine needs a check that takes seconds: `validate` and the reproduction
studies take minutes each and nobody runs those on every edit.

Most of them are there because something was once wrong, and those say so in
the test's own docstring. A test whose purpose is forgotten is a test someone
eventually deletes.

One of them guards everything else. `tests/test_engine_golden.py` holds the
exact output of the collision loop, for configurations chosen to reach every
branch of it, as the loop stood before design item 13 restructured it. Under
LoRaSim's receiver rule the output must come back identical, not merely
close, so a refactoring of the engine cannot move a published number without
failing here first. It held through item 14 too, which split the loop into a
phase that draws every random number and one that resolves collisions and
draws none, so that synthetic traffic can be fed to the second and checked
against closed-form results. It has been changed once on purpose, by item
16, which stopped the loop counting a packet dropped for want of a
demodulator a second time as a collision. Only the configuration where the
limit binds hard moved.

When the suite had 120 checks, at the close of design item 10, it was
checked by putting six real past bugs back in one at a time and confirming it
failed. This is a record of that verification, not a figure that
`reproduce` regenerates, and the checks added since are covered only where
their own design item says so:

| Bug reintroduced | Caught by |
|---|---|
| ADR's link margin treated as an admission test | 2 tests |
| `max_distance_m` inverting in base *e* | 5 tests |
| EU868 reading the non-repeater payload ceilings | 1 test |
| `der_fleet` no longer counting excluded nodes | 1 test |
| Shadowing drawn per packet instead of per node | 1 test |
| The payload ceiling no longer checked | 2 tests |

The fifth went undetected at first. The test compared the reported
received-power spread, which is computed from the per-node figure and so
never noticed a draw moved into the packet loop. It was replaced with an
exact assertion instead of a statistical one: an adaptive scenario assigns
each node a data rate its own shadowed link already clears, so if shadowing
is fixed per node then no packet can be lost to weak signal, and the count
must be exactly zero. Reintroducing the bug now turns that zero into
thousands.

## Validating the engine

`check` asks whether a study is configured sensibly. `validate` asks something
else entirely, which is whether the engine itself is right.

```bash
python3 run.py validate iot4cows
python3 run.py validate iot4cows --scenario SF8 --nodes 10,30,60,100,200 --runs 10
```

The reference is pure ALOHA, `DER = exp(-2G)` with `G = N·T·λ`. It is a lower
bound, not a target. A simulator that matched it exactly would be one that had
thrown away everything LoRa does beyond ALOHA.

So the test is degeneracy rather than agreement. Each rung switches off one
mechanism the analytical model does not have, and the engine should walk down
onto the bound. On the worked example at SF8:

| N | G | full model | no demod limit | single channel | no capture | no preamble | ALOHA |
|---|---|---|---|---|---|---|---|
| 10 | 0.089 | 0.9825 | 0.9825 | 0.8692 | 0.8454 | 0.8386 | 0.8368 |
| 30 | 0.267 | 0.9497 | 0.9497 | 0.6682 | 0.6014 | 0.5867 | 0.5859 |
| 60 | 0.535 | 0.9022 | 0.9022 | 0.4603 | 0.3609 | 0.3438 | 0.3433 |
| 100 | 0.891 | 0.8446 | 0.8446 | 0.2925 | 0.1831 | 0.1688 | 0.1683 |
| 200 | 1.782 | 0.7170 | 0.7172 | 0.1214 | 0.0331 | 0.0282 | 0.0283 |

What each mechanism is worth at N = 200, as the DER it adds:

- demodulator limit: -0.0002 (0.7170 with it, 0.7172 without)
- multiple channels: +0.5958 (0.7172 with it, 0.1214 without)
- capture effect: +0.0883 (0.1214 with it, 0.0331 without)
- preamble allowance: +0.0049 (0.0331 with it, 0.0282 without)
- residual against ALOHA: -0.0002

Verdict: directions hold, 5 of 5 points within 3 standard errors of the bound. PASS.

*Source: experiment `validation` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 10, 30, 60, 100, 200, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/validation/`. Regenerate with `python3 run.py reproduce iot4cows --only validation`.*

Two things are checked, neither of them by eye. Every step must move the way
it should, and the final rung must agree with `exp(-2G)` within the
simulation's own standard error rather than within an arbitrary percentage.
`validate` exits non-zero when either fails, so it can go in CI.

Note that three of the four mechanisms help, so removing them lowers DER,
while the demodulator limit is a constraint and removing it raises DER.
Treating the ladder as uniformly decreasing would be wrong, and would only
look right in configurations where that limit never binds. It is removed
first, while the full channel set is still active, because that is the only
arrangement in which its real cost is visible. On the worked example it turns
out to cost almost nothing, which is itself worth knowing: at this scale the
SX1301's eight demodulators are not the constraint. The gap between
neighbouring rungs, listed under the table, is what each mechanism is worth
here.

The figure it writes has two panels: DER against node count for every rung
with the bound dashed, and the same runs as normalised throughput against
offered load over the canonical `S = G·exp(-2G)`. The degenerate rung lands on
that curve and peaks where theory says it must, at `S ≈ 0.184` for `G = 0.5`.
The full model runs well above it, and that distance is what LoRa buys over
ALOHA.

The bound needs one time on air, so an adaptive (`MULTI`) scenario cannot be
validated this way. `validate` says so rather than producing a number.

A study on the lock receiver rule gets one more rung and a second bound,
exp(-G). "The receiver rule" above shows both.

## Layout

```
run.py                      command line entry point
loracap/
    core.py                 the engine: airtime, propagation, collisions, placement
    study.py                the Study definition, loading and validation
    presets.py              regional SF ranges and datasheet sensitivity tables
    experiment.py           runs the grid, writes results
    analysis.py             capacity and bootstrap confidence interval
    sweep.py                propagation sensitivity sweep
    validation.py           the ALOHA bound and the degeneracy ladder
    compare.py              one study under two propagation models
    reproduce.py            experiments.py manifests behind `run.py reproduce`
    plotting.py             the figures: one run, the ladder, panels side by side
    geo.py                  KML parsing, projection, area and overlap checks
    pathloss.py             log-distance fit and its sanity checks
tools/
    kml_to_polygon.py       KML boundary  ->  site_polygon.py
    fit_path_loss.py        field RSSI    ->  propagation model
webui/
    server.py               loopback server behind `run.py serve`
    index.html              the setup form
tests/                      336 fast checks, `run.py test`
studies/
    _template/              commented starting point, copied by `run.py new`
    iot4cows/               worked example, see below
    bor2016_sn1/            Bor et al.'s Experiment Set 1, SN1, coding rate 4/8
    bor2016_sn3/            the same, SN3, coding rate 4/5
    <study>/experiments.py  every result quoted for that study, see
                            "Reproducing every number" below
    <study>/outputs/<name>/ what each experiment wrote, with its provenance
```

## The worked example

`studies/iot4cows` is the configuration behind a published scalability
analysis of a cattle-monitoring deployment in Guamal, Meta, Colombia. It is
kept here because it shows every field filled with a real, sourced value, and
because it lets anyone confirm the engine still reproduces the published
figures:

| Scenario | Capacity at DER = 0.9 | 95% CI |
|---|---|---|
| SF7 | 114.9 | [113.9, 115.9] |
| SF8 | 61.8 | [61.1, 62.6] |
| SF9 | 33.9 | [33.0, 34.7] |

*Source: experiment `headline` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/headline/`. Regenerate with `python3 run.py reproduce iot4cows --only headline`.*

SF7 is the optimistic bound, SF8 the deployed configuration, SF9 the
conservative bound.

The published analysis is *IoT4Cows: A LoRaWAN system for
cattle monitoring in extensive grazing with network performance evaluation*,
Smart Agricultural Technology,
[doi:10.1016/j.atech.2026.102644](https://doi.org/10.1016/j.atech.2026.102644).

**The conservative bound here is SF9, where the published figure used SF10.**
The data-rate check added later caught the reason: SF10 is US915 DR0, which
carries at most 11 bytes of application payload, so a 32-byte reading cannot
be sent at that rate at all. The published error is conservative, since the
airtime computed for 32 bytes at SF10 is longer than any legal SF10 uplink,
and it moved only that one curve: the article reports about 18 nodes for
SF10, [16.9, 18.1], against SF9's 33.9 here, because airtime nearly halves
from 453 ms to 247 ms. The code behind the article is commit `8779a30` of
[github.com/wilcashe/loracap](https://github.com/wilcashe/loracap). SF8, the
headline figure, is untouched. Interval bounds here can differ from the
article's by 0.1 node, because of a bootstrap fix described in design item
11. Point estimates are unchanged.

This is the kind of thing the tool exists to catch, and it is worth saying
plainly that it caught it here, in its own worked example, after the fact.

The article also defines DER as collision and weak-signal losses only, with
packets dropped for lack of a free demodulator tracked separately. That is
`der_classic` here. Capacity in this repository is computed on `der`, which
counts those drops as losses too. On this site the two coincide, since the
demodulator limit costs 0.0002 DER at 200 nodes (see "Validating the
engine"), but a study where the limit binds will see them differ.

Remember which bound is which: a *lower* spreading factor has *shorter*
time-on-air and therefore *higher* capacity. The low SF is the optimistic
bound, not the conservative one. Getting this backwards is an easy mistake and
an embarrassing one to have pointed out.

## Reproducibility

Given the same study, results are bit-identical on every run: each repetition's
seed is derived deterministically from `base_seed` and the repetition index,
and the bootstrap has a fixed seed of its own. Change `base_seed` to confirm a
reported capacity is not an artefact of one random stream.

### Reproducing every number

Every table above that comes from a simulation ends with a line saying which
experiment produced it. The experiments live in `experiments.py` next to each
study's `study.py`, and each one states its repetitions, node grid, simulated
time, seed and bootstrap count explicitly rather than inheriting them.

```bash
python3 run.py reproduce iot4cows --list       # what it holds
python3 run.py reproduce iot4cows              # run all of it, print every table
python3 run.py reproduce iot4cows --only adr   # one experiment
python3 run.py reproduce iot4cows --tables     # reprint from saved files, no simulation
python3 run.py reproduce all                   # every study with a manifest
python3 run.py reproduce reference             # tables computed from presets
```

Each experiment writes into `outputs/<experiment>/`, and every JSON file
written, there or by a command typed by hand, carries a `provenance` record:
the experiment or command line, the fully resolved study, a SHA-256 of the
package source, and the date. Commands typed by hand write into `outputs/`
itself, so a quick check can never overwrite a result a document quotes.
`run.py plot` redraws every manifest figure from its JSON.

An experiment with several variants draws one figure for all of them when it
names its `figure_panels`, one panel per named variant, written into the
experiment's own directory. `figure_marks` adds reference node counts as
labelled vertical lines, for numbers a figure must be read against that the
experiment does not produce. Each is a `(node_count, label)` pair, and its
source belongs in a comment beside it. A mark outside an axis is left out
rather than drawn at the edge.

All the worked example's experiments share one configuration, the study's
own: 30 runs per point, the 27-point grid from 3 to 300 nodes, 3600 s and
seed 99. So SF8 with no shadowing is 61.8 wherever it appears, and a
difference between two rows of a table comes from what the rows change.
Regenerating every study, `python3 run.py reproduce all`, takes a little
over an hour on one core.

## Known limitations

- The propagation model is deterministic unless `shadowing_sigma_db` or
  `fading_sigma_db` is set, and both default to 0. The worked example leaves
  them there on purpose, to reproduce a published analysis, and `check` warns
  that it is discarding the residual.
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
- Sensitivity is tabulated at 125 kHz for the gateway chips, and at 125, 250
  and 500 kHz for the one node radio whose measured table is published here.
  At any other bandwidth the figure is derived from the nearest tabulated one
  by `10·log10(BW₂/BW₁)`, and `check` says so. The derivation is conservative:
  measured against the table that does cover three bandwidths, it understates
  sensitivity by 1.2 dB on average at 250 kHz and 2.1 dB at 500 kHz, and by
  up to 5.0 dB, never the other way (`python3 run.py reproduce reference`).
  That understates range, which is the safe direction for a coverage claim,
  but 5 dB is about 70% of range at a typical exponent, so read a derived
  figure as a bound rather than a value.
- Plain LoRa outside LoRaWAN is not supported. Spreading factors and
  bandwidths are checked against the regional data-rate tables, so a
  proprietary link such as SF6 at 500 kHz is rejected by design.
- The OPTIONAL SF6 and SF5 uplink data rates at 125 kHz that RP002-1.0.5
  added are not supported either. They are LoRaWAN, but the gateway chips
  tabulated here cannot demodulate them, so there is no sourced sensitivity,
  and neither their airtime nor the capture model has been checked at those
  spreading factors. A study naming them is refused.
- Nothing decodes. A packet counts as received when it clears the sensitivity
  threshold, survives the capture and preamble-timing rules, and finds a free
  demodulator. The receiver's behaviour is summarised by those thresholds,
  which come from datasheets and from Bor et al.'s and Haxhibeqiri et al.'s
  measurements, rather than being simulated.
- Both receiver rules rest on measurements with two transmitters. With three
  or more overlapping packets the rule is applied pair by pair. Fernandes et
  al. found three simultaneous packets close to that pairwise product, which
  supports it for packets that start together and says nothing about
  staggered ones. The capture threshold, 6 dB by default, is an assumption
  inherited from LoRaSim. The measurements the rules were built from left a
  gap between about 2 and 6 dB, and the ones that fill it (Fernandes et al.,
  Croce et al., Eigner) put the threshold at 3 dB or less, though none
  declares its coding rate. The lock rule counts the first of two
  equal-power packets as always received, where the measurement gives about
  90%, unless `lock_survival` is set, in which case the locked packet's fate
  follows Eigner's per-SF table, used as a step at its 99% point. Header
  recapture is off unless `header_recapture` is set. "The receiver rule"
  says how much the rule, the threshold and the refinements move the
  result.
- By default spreading factors are treated as perfectly orthogonal: packets
  on different spreading factors never collide. They are not, and a study
  can name `inter_sf_rejection` to say so, with the limits set out in
  "Spreading factors that are not orthogonal". Croce et al.
  measured an SX1272 losing a packet to an interferer on another spreading
  factor once it arrived 8 to 9 dB stronger at SF7 and 23 to 25 dB stronger
  at SF12, and showed that this hurts high spreading factors assigned to
  distant nodes most. Under the default, every result that spreads nodes
  across spreading factors is an upper bound for that reason. At the worked
  example the table moved only ADR without power control, by 10 to 14%.
  Croce et al. measured a node radio, at a bandwidth the paper does not
  state for that test. Eigner measured an SX1301 concentrator at 125 kHz
  and found values within 1.5 dB of theirs. Neither states the coding
  rate.
  Sources: Croce, Gucciardo, Mangione, Santaromita and Tinnirello, *"LoRa
  Technology Demystified: From Link Behavior to Cell-Level Performance"*,
  IEEE Trans. Wireless Commun. 19(2):822-834, 2020,
  <https://doi.org/10.1109/TWC.2019.2948872>, Table I. Fernandes, Oliveira,
  Luís and Sargento, *"On the Real Capacity of LoRa Networks: The Impact of
  Non-Destructive Communications"*, IEEE Commun. Lett. 23(12):2437-2441,
  2019, <https://doi.org/10.1109/LCOMM.2019.2941476>, Tables I and II.
  Eigner, *"Interference Analysis of LoRaWAN Systems"*, diploma thesis, TU
  Wien, 2021, Tables 5.1 and 5.2.

The design log, kept outside this repository, records what each of these
would take to lift and which are deliberately out of scope.

## Design log

Every design decision is recorded, with its reasoning and the alternatives
discarded, in a design log kept outside this repository. Its items are
numbered, and the references to "design item N" or "item N" in the code, the
tests, the experiment descriptions and this README point to them.

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

The lock receiver rule follows the collision measurements of Bor et al.
(Figure 3 of the paper above, SX1272) and of Haxhibeqiri, Van den Abeele,
Moerman and Hoebeke, *"LoRa Scalability: A Simulation Model Based on
Interference Measurements"*, Sensors 17(6):1193, 2017,
<https://doi.org/10.3390/s17061193> (Tables 2 to 6, SX1301).

Sensitivity values in `presets.py` are reproduced from manufacturer datasheets
and each carries its source. Only chips actually verified against a datasheet
appear there. For any other hardware, read the datasheet and put the values in
your study.
