# shafts

CLI-based shaft design app for Shigley Chapter 7 style calculations.

## Package layout

```text
shafts/
  in/
  out/
  apis.py
  app.py
  cli.py
  core.py
  io.py
  utils.py
  RUNS.md
  __init__.py
  __main__.py
```

## Important run modes

This package supports **both** workflows:

### Run from the parent directory

```bash
python -m shafts.cli \
  --help
```

### Run from inside the `shafts` package directory

```bash
python -m cli --help
```

That second mode is the reason the import shim exists.

## Example commands

From **inside** the `shafts` directory:

```bash
python -m cli endurance \
  --se-prime 52.5 \
  --ka 0.787 \
  --kb 0.87 \
  --ke 0.99
```

```bash
python -m cli fatigue \
  --criterion de_goodman \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Se 35.44 \
  --Sut 105 \
  --Sy 82 \
  --Ma 1260 \
  --Tm 1100 \
  --d 1.1
```

```bash
python -m cli yield \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Sy 82 \
  --Ma 1260 \
  --Tm 1100 \
  --d 1.1
```

```bash
python -m cli vector-sum \
  --label left_bearing_slope \
  --xz 0.02263 \
  --xy 0.01770 \
  --label right_bearing_slope \
  --xz 0.05711 \
  --xy 0.02599 \
  --units deg
```

```bash
python -m cli diameter-resize \
  --d-old 1.0 \
  --response-old 0.001095 \
  --response-allow 0.0005 \
  --mode slope
```

```bash
python -m cli torsion-angle \
  --G 11500000 \
  --T 1200 \
  --length 8 \
  --J 0.30 \
  --length 10 \
  --J 0.45
```

```bash
python -m cli torsional-stiffness \
  --G 11500000 \
  --length 8 \
  --J 0.30 \
  --length 10 \
  --J 0.45
```

```bash
python -m cli run \
  --infile fatigue_goodman.json
```

## Notes

- Enter all chart-based factors manually.
- External beam-analysis outputs are expected to be entered manually.
- Units are user-responsibility; keep them consistent.
- JSON input files are searched in this order: current working directory, `shafts/in`, then the raw path.
