# Changelog

What changed in each version of LoRaCAP. "Design item N" refers to the
project's design log, where each change is recorded with its reasons and the
alternatives it ruled out. The numbers each version reports come from its
own `run.py reproduce all`, and its README quotes them.

## 2.4.0 (2026-11-27)

Design items 48 and 49, since 2.3.0.

### Documentation
- A first-use guide for a reader who knows LoRaWAN and not Python, in
  English (`docs/GETTING_STARTED.md`) and Spanish
  (`docs/GUIA_DE_INICIO.md`): installing, running the example study and
  setting up a site on the web page (design item 48).
- The README's layout gave the old test count, 528. It is 644.

### Measurement files
- A measurement CSV may separate its columns with commas, semicolons or tabs,
  found from the header line, and may be UTF-8 (with or without a byte-order
  mark) or Windows-1252, the code page Excel saves a plain "CSV" in. The page
  and `tools/fit_path_loss.py` both say how the file was read and how many
  rows were skipped for unreadable values (design item 49).
- A decimal comma is still not read. A file that has them is refused with one
  of its values quoted, or, when only some rows have them, fitted on the rest
  with a warning that gives the count.
- `tools/fit_path_loss.py` stopped with a Python traceback on a Windows-1252
  file. It now reads it, and a file in neither encoding stops with a message.

Every experiment was regenerated for 2.4.0 (code digest `21fbf20148ac`),
with every number, table and figure identical to 2.3.0's.

## 2.3.0 (2026-11-25)

Design items 34 to 47, since 2.2.0.

### Version
- The version lives in `loracap/VERSION`, outside the code digest every
  saved result records, so raising it no longer forces every experiment to
  be run again (design item 46).

### Field fits
- Each fit is checked on its own. An exponent outside 1.45 to 5.97, the
  span measured for LoRa across environments, or an R² below 0.15 marks the
  fit doubtful, and `check` now looks at the exponent of any study and errs
  at 0 or below (design item 38).
- `max_measured_distance_m` records how far a model was measured. It changes
  no result. `check`, the web page and the site map say when the site, a
  disc or a reach lies past it. iot4cows records the 2.21 km its source
  states (design item 39).
- When some positions were measured more than once, a third fit, per
  position, separates fading from shadowing (design item 40).

### Web page
- A field for the fading σ, and a block filled by a fit still lists every
  value the fit did not set (design item 35).
- The gateway position can be written in degrees, minutes and seconds
  (design item 36).
- Templates the page fills itself no longer hide a missing translation
  (design item 37).
- A boundary is projected again whenever the gateway position changes
  (design item 41).
- A failure to compute the reach table is reported instead of leaving the
  table empty without a word (design item 44).

### Figures
- The site map draws the gateway as a star, a shape no node has (design
  item 34).

### Checks
- `check` is split into one function per group of checks, with the same
  messages in the same order over 3004 generated studies. A spreading factor
  missing from an explicit sensitivity table, and a send interval of 0, are
  now errors instead of stopping `check` with a traceback (design item 47).

### Tests
- The suite passes on Python 3.8 as well as 3.13. The golden engine test
  compares counts exactly and floats to one part in 10^12. Without
  matplotlib the modules that test figures are skipped instead of failing
  (design item 44).
- `requirements.txt` bounds matplotlib below 4.
- GitHub Actions runs the suite on every push, on Python 3.8 and 3.13, on
  Linux, Windows and macOS, and on Python 3.8 without matplotlib (design
  item 45).

Every experiment was regenerated at `925adaa`, with every number identical
to 2.2.0's and only the iot4cows site map changed, and again for 2.3.0 (code
digest `42480f413231`), with every number and figure identical to those of
`925adaa`.

## 2.2.0 (2026-11-23)

- The airtime counts the LoRaWAN header: `payload_bytes` is the
  application payload the regional tables limit, and the frame on air adds
  `lorawan_overhead_bytes`, 13 by default. The Bor studies use 0, as their
  published airtime does. iot4cows's capacities fall by 16 to 23%, SF8 from
  61.8 to 49.9 nodes. Setting the header to 0 gives back 2.1.0's runs
  (design item 33).
- Field measurements are fitted with the equipment that took them, which
  may differ from the radio the study simulates (design item 32).
- On the Spanish page, payload, frame and header stay in English, and ToA
  is among the page's abbreviations.

## 2.1.0 (2026-11-20)

- The site map: the placement of one run at the capacity, saved to
  `site_map.json` and redrawn from it (design item 31).
- The web form is readable, with notes, ranges and checks named as the form
  names them (design item 24), and has basic and advanced settings and a
  tab that chooses what a run draws and writes (design item 25).
- The saturation experiment carries iot4cows on to 3000 nodes (design
  item 26).
- The web form reads in English or Spanish (design item 27).
- The SX1301 above 125 kHz uses its own tables and one channel on IF8
  (design item 28), and the page notes what the chosen chip gives at every
  bandwidth, offering only concentrators (design item 29).
- The LoRaSim run made outside the repository is no longer quoted with
  figures (design item 30).
- Every text file is read and written as UTF-8 on every platform.

## 2.0.0 (2026-11-02)

Design items 1 to 21: regional tables, bandwidth-dependent sensitivity,
log-normal shadowing, the pure-ALOHA degeneracy harness, network energy,
the reproduction of Bor et al.'s Experiment Set 1, the two-model
comparison, steady-state ADR, the test suite, experiment manifests behind
`run.py reproduce`, the lock receiver rule and its two refinements,
rejection between spreading factors, the web interface, and figures that
compare configurations.

A major version because results moved to `outputs/<experiment>/`, the
worked example's slowest scenario became SF9 instead of the SF10 that US915
does not allow at 32 bytes, and design item 16 corrected the loss
accounting where the demodulator limit binds.

## 1.0.0 (2026-10-20)

The first public version.
