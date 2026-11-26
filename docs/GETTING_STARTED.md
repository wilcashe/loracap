# Getting started with LoRaCAP

This guide takes you from a computer without LoRaCAP to the capacity of your
own site. It assumes you know LoRaWAN (spreading factors, data rates, RSSI,
ADR) and have never used Python. Every command is given in full, and you
type it as it is written.

There are two parts. First you install LoRaCAP and run the example study
that comes with it, so you can see what a finished result looks like and
confirm that your installation gives the same numbers as everyone else's.
Then you build a study of your own site on LoRaCAP's web page, from a
boundary drawn in Google Earth and the RSSI you measured in the field.

The [README](../README.md) explains every option in depth. This guide covers
only what a first study needs and points to the README for the rest. A
Spanish version of this guide is in [GUIA_DE_INICIO.md](GUIA_DE_INICIO.md).

## 1. Install

### Python

LoRaCAP needs Python 3.8 or newer. Open a terminal and check what you have:

- Windows: open PowerShell and type `py --version`.
- macOS or Linux: open Terminal and type `python3 --version`.

If the command is not found, or the version is older than 3.8, install
Python from [python.org](https://www.python.org/downloads/). On Windows,
tick "Add python.exe to PATH" on the first screen of the installer.

This guide writes every command as `python3 ...`. On Windows type `py ...`
instead, with the rest of the line unchanged.

### LoRaCAP

On [github.com/wilcashe/loracap](https://github.com/wilcashe/loracap), the
green "Code" button offers "Download ZIP". Unzip it wherever you like. The
latest numbered version is also on the Releases page of the same site.

In the terminal, move into the unzipped folder. The folder that contains
`run.py` is the right one:

```bash
cd path/to/loracap
```

Every command in this guide is typed from that folder.

### The figure library

The simulation itself needs nothing beyond Python. Drawing figures needs one
library, matplotlib:

```bash
python3 -m pip install -r requirements.txt
```

Some Linux distributions refuse this with a message about an "externally
managed environment". In that case create a private environment for
LoRaCAP inside its folder and install into it:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run `source .venv/bin/activate` again each time you open a new terminal.
Without matplotlib every number is still computed and saved, and the
commands say that no figure was drawn.

### Check the installation

```bash
python3 run.py test
```

This runs 682 checks on the simulator in about twenty seconds. The last
lines should read `OK` and "The fast checks pass". If any check fails, stop
there: a result from a broken installation cannot be trusted.

## 2. Run the example

LoRaCAP ships with three studies. List them:

```bash
python3 run.py list
```

`iot4cows` is a cattle-monitoring deployment in Guamal, Meta, Colombia: one
gateway, an 88.5 ha site, US915 and nodes on SF7, SF8 or SF9. Before running
any study, check it:

```bash
python3 run.py check iot4cows
```

`check` runs nothing. It reads the study and says what it found: the band,
the data rate of each spreading factor, the frame length on air, the site
area and how far each spreading factor reaches. For this study it says,
among other things:

```
SF9 reaches 3096 m (an extrapolation: the measurements stop at 2210 m),
well beyond the site's 958 m. Range is not the binding constraint here.
```

It also prints a warning: the propagation model of this study has no
shadowing. That is how the study was published, and the README discusses
what shadowing changes. On your own study, read every warning `check`
gives. A wrong parameter does not make the simulation fail, and instead
makes it return a wrong answer without complaint.

Now run it:

```bash
python3 run.py run iot4cows
```

It simulates 81 points (3 scenarios times 27 node counts), 30 runs each, and
prints one line per point. On the computer this guide was checked on it
took under two minutes. At the end it prints:

```
Capacity at DER = 0.9

  Scenario      Nodes            95% CI
  SF7            88.0      [87.1, 89.1]
  SF8            49.9      [49.3, 50.5]
  SF9            26.3      [25.6, 27.1]
```

You should get exactly these numbers. The study fixes its random seed, so
any computer with a working installation reproduces them. If yours differ,
something is wrong with the installation, and `python3 run.py test` is the
place to start.

Read the table this way. With every node on SF8, a 32-byte payload and a
report every 15 seconds, the gateway receives at least 90% of the packets
sent up to about 50 nodes. The interval in brackets is the 95% bootstrap
confidence interval of that crossing over the 30 runs. It measures the
simulation's own uncertainty and not the uncertainty of the model behind it.

The run wrote its files into `studies/iot4cows/outputs/`:

| File | What it holds |
|---|---|
| `results.json` | every point and run, with the whole configuration of the study |
| `capacity.json` | the capacities in the table above |
| `results.csv` | the same points, for a spreadsheet |
| `iot4cows_capacity.png` (also `.pdf`, `.svg`) | DER against node count, one curve per scenario |
| `iot4cows_capacity_site_map.png` | where the nodes of one run sit, coloured by spreading factor |
| `site_map.json` | the placement the map is drawn from |

The numbers quoted in the README come from the experiments in
`studies/iot4cows/experiments.py`, whose outputs live in subfolders of
`outputs/`. A plain `run` never overwrites them.

## 3. Prepare your own data

A study of your site needs three things: the gateway's position, the
boundary of the area the nodes cover, and a propagation model. You get the
first two from a map. The third is the one thing that cannot be borrowed
from another site, and it comes from your RSSI measurements.

### The site boundary (KML)

Draw the area the nodes will occupy as a polygon in Google Earth and save it
as a `.kml` file. A `.kmz` file is a compressed KML and the page does not
read it, so choose KML when saving. A file with several polygons is
accepted. The page shows the area of each one and whether any overlap,
because overlapping polygons inflate the area and pile nodes up where they
overlap.

### The gateway's position

Write it as decimal degrees (`5.501139`, `-73.492939`) or as a GPS unit or a
survey sheet writes it (`5°30′04.10″ N`, `73°29′34.58″ W`). The page also
accepts `O` for west and a comma as the decimal mark. Under a position in
degrees, minutes and seconds it shows the decimal degrees it read. Check
that number: it is the only value the simulation uses.

### The RSSI measurements (CSV)

The file has one row per message the gateway received, with the RSSI in dBm
as the gateway reported it and the node's latitude and longitude in decimal
degrees:

```
rssi,latitude,longitude
-83,3.917401,-73.820015
-91,3.918220,-73.821540
```

Other columns are ignored, so an export from the network server usually
works as it is. The column names are recognised in their usual spellings
(`rssi`, `rssi_dbm`, `lat`, `latitude`, `lon`, `lng`, `longitude` and a few
more). Three things to do before loading it:

1. Keep only one spreading factor and one gateway. RSSI also changes with
   the spreading factor and with the gateway, for reasons that have nothing
   to do with distance, and a fit of a mixed file looks healthy and is
   wrong. LoRaCAP warns when it sees more than one of either, but it cannot
   know which part you meant to keep.
2. Remove rows recorded somewhere other than the site, such as a bench test
   before going to the field.
3. Make sure numbers use a point as the decimal mark. The columns may be
   separated by commas, semicolons or tabs, and the file may be saved as
   "CSV UTF-8" or as plain "CSV", which is how Excel writes it. A
   spreadsheet set to Spanish writes decimal commas, though, and LoRaCAP
   reads only the point. In Excel, File > Options > Advanced, clear "Use
   system separators" and type a point as the decimal separator before
   saving. A file with decimal commas stops with a message that names one
   of its values and says "use a comma as the decimal mark".

Points closer than 30 m to the gateway are left out by default, because the
receiver saturates at very short range and understates the RSSI.

Write down the equipment you measured with: the node's transmit power, the
gains of the node's and the gateway's antennas, and the losses of the node
and the cable. The page needs them to turn each RSSI into a loss of the
terrain. They can differ from the radio the study will simulate.

If you have no measurements at all, the page can still build a model from
the type of environment and the range you expect. The model is then an
assumption, the page labels it as such, and section 7 of this guide says
what to do about it.

## 4. Build the study on the web page

```bash
python3 run.py serve
```

This opens `http://127.0.0.1:8765/` in your browser. The page runs on your
computer only, and nothing outside it can reach it. Leave the terminal open
while you use the page, and press Ctrl+C in it when you are done.

The page reads in English or in Spanish, with the "English | Español" switch
in its top corner. It opens in "Basic" mode, which shows only what has no
default or is usually changed. A field marked with an asterisk must be
filled in. "Advanced" shows the rest, grouped in blocks. A closed block
lists every value in it that differs from its default, so nothing changes
behind your back.

The "Checks" panel on the right is updated as you type. Each message names
the field it is about, and a click takes you there. The messages come from
the simulator and are in English on both versions of the page.

### 1. Site

Give the study a short name (letters, digits, hyphen or underscore), the
gateway's latitude and longitude, and load the KML with "Choose KML…". The
page shows the area, whether the gateway is inside the boundary, how far the
farthest point is and an outline of the site.

### 2. Radio

Choose the region and the node's transmit power. AU915 and AS923 also ask
for the uplink dwell time. Each setting has its own payload ceiling, and at
the slow data rates they differ by more than tenfold, so there is nothing
safe to assume on your behalf. The gateway chip, the antennas, the cable
losses and the bandwidth are under "advanced radio settings". Under the
chip, a note gives the sensitivity, the channels and the demodulation limit
the simulation will use.

### 3. Propagation

With measurements, stay on the "I have field measurements" tab. Fill in the
four fields of the equipment you measured with, then load the CSV with
"Choose measurements CSV…". The page fits the model and shows up to three
fits side by side:

| Fit | When it appears | What it does |
|---|---|---|
| unbinned | always | every row counts once |
| binned (10 m) | always | each 10 m distance band counts once, so a spot measured many times does not dominate |
| per position | when some coordinates repeat exactly | each position counts once, and the spread is split into shadowing and fading |

The first lines under the button say how the file was read: the separator
it found and the text encoding. If any row was skipped because a value could
not be read as a number, another line gives how many. Check them before the
numbers.

Each row gives the exponent n, R², σ, the loss at d₀ and the number of
points, with a "Use" button. A fit marked "doubtful" has an exponent outside
1.45 to 5.97 (the span published measurements cover) or explains less than
15% of the spread in RSSI. The warnings above the table say which. Choose a
fit deliberately and record which one you chose. When the per position fit
appears, it is the one that tells apart the spread that belongs to where a
node is (shadowing) from the spread that changes packet by packet (fading).

"Use" copies the fit into the fields under "advanced propagation settings":
the exponent, the loss at d₀, the shadowing σ, the farthest distance you
measured and a line saying where the model came from, which goes into
`study.py`. The per position fit fills the fading σ as well. If the
equipment fields are empty the fit still gives the exponent and σ, but no
loss at d₀, since a default there would be a number with nothing behind it.

The farthest measurement matters later. Past it every received power is the
fitted line extrapolated, and the checks say so wherever the site or a reach
lies beyond it.

### 4. Traffic and experiment

Enter the application payload in bytes (the payload your application sends,
without the LoRaWAN header, which the simulator adds for the time on air),
the send interval in seconds and the DER threshold. Use the shortest
interval the deployment can produce. A capacity found at the worst case is a
bound you can defend.

Tick at least one scenario:

- A single spreading factor puts every node on it.
- MULTI puts each node on the fastest spreading factor its link reaches,
  with no margin and at full power, so it is a bound and not a network.
- ADR is what a converged network settles into, with a link margin and
  reduced transmit power.

Running MULTI and ADR together shows what the idealisation is worth. The
coding rate, the simulated time, the runs per point, the random seed and the
receiver model are under the advanced blocks of this section. For a first
study, leave them at their defaults.

### 5. Create and run

"Write study.py" writes `studies/<name>/study.py` and `site_polygon.py` and
shows you the file. From then on it is an ordinary study, which you can edit
by hand and run from the terminal. "Run simulation" runs it and shows its
progress. The page simulates with the same code as the command line.

Before running, open the "6. Output" tab if you want more figures: messages
delivered per hour, energy per delivered message, where packets are lost
and the site map. The choice is saved in `study.py` and changes no number.

## 5. Read the results

When the run ends, the page shows a table with the capacity of each scenario
and its 95% interval, the DER figure, and a button on the Output tab that
downloads the study and its files as one zip. The files themselves stay in
`studies/<name>/outputs/`.

"no crossing" means the DER never fell below the threshold within the node
counts simulated, 3 to 300 on a study written by the page, so the capacity
lies above the last count. To look further, open `study.py`, add larger
counts to the `node_counts` list, then check and run the study from the
terminal (section 6).

A capacity is a simulation estimate, conditional on the model it ran with.
Report it with those conditions:

- the receiver rule, LoRaSim's by default
- the capture threshold, 6 dB by default
- whether spreading factors were treated as orthogonal, which is the
  default, or which rejection table was used
- the propagation model and where it came from
- the DER threshold, the payload and the send interval

The capacity table, written as Markdown or LaTeX if you choose it on the
Output tab, states the first three under the numbers. The field campaign
validates coverage and link quality. It does not validate capacity, and no
receiver rule in LoRaCAP has been checked against the capacity of a real
network.

## 6. From the terminal afterwards

Once the page has written the study, these work on it like on any other:

```bash
python3 run.py check <name>     # validate it again after editing study.py
python3 run.py run <name>       # run it again: same seed, same numbers
python3 run.py plot <name>      # redraw the figures without simulating
```

`study.py` is a commented text file. Any editor opens it, and every field
in it is explained in the README.

## 7. If you had no measurements

A model built from the environment and an expected range is an assumption.
As long as every spreading factor reaches the whole site, capacity barely
depends on it, because collisions depend on how many nodes transmit and on
how different their received powers are. Once the site stops being covered,
the model decides the result. After the run the page offers a sweep that
measures exactly this, and the terminal does the same:

```bash
python3 run.py sweep <name>
```

It varies the path-loss exponent and reports, for each value, the reach,
whether the site is covered and the capacity. If capacity stays nearly flat
across the range, the assumed model is defensible as long as you report it
as assumed. If it does not, you need measurements. The README section
"Simulating without field measurements" goes through the reasoning with the
example study's numbers.

## Common problems

| What you see | What it means |
|---|---|
| `python3` or `py` is not found | Python is not installed, or on Windows it was installed without "Add python.exe to PATH". |
| `can't open file 'run.py'` | The terminal is not in the LoRaCAP folder. Move into the folder that contains `run.py`. |
| "externally managed environment" when installing | Use the private environment described in section 1. |
| "matplotlib is not installed, so no figure was drawn." | The numbers are fine. Install matplotlib to get the figures. |
| "use a comma as the decimal mark" | The numbers have decimal commas. Save them with a point (section 3). |
| "Could not find a column for rssi, latitude, longitude" | The column names are not among the usual spellings. The message lists the names it found. |
| A fit marked "doubtful" | Read the warning above the table. A wrong coordinate or a mixed file are the usual causes. |
| The page does not open | Open `http://127.0.0.1:8765/` by hand. If the port is busy, start it with `python3 run.py serve --port 8800`. |
| Your example numbers differ from section 2 | Run `python3 run.py test` and do not trust any result until it passes. |
