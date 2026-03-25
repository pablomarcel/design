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

#### Example 7-1

### Endurance

```bash
python -m cli endurance \
  --se-prime 52.5 \
  --ka 0.787 \
  --kb 0.87 \
  --kc 1.0 \
  --kd 1.0 \
  --ke 0.814 \
  --kf-misc 1.0
```

### DE-Goodman

```bash
python -m cli fatigue \
  --criterion de_goodman \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Se 29.3 \
  --Sut 105 \
  --Sy 82 \
  --strength-unit ksi \
  --Ma 1260 \
  --Mm 0 \
  --Ta 0 \
  --Tm 1100 \
  --d 1.1
```

### DE-Gerber

```bash
python -m cli fatigue \
  --criterion de_gerber \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Se 29.3 \
  --Sut 105 \
  --Sy 82 \
  --strength-unit ksi \
  --Ma 1260 \
  --Mm 0 \
  --Ta 0 \
  --Tm 1100 \
  --d 1.1
```

### DE-ASME-Elliptic

```bash
python -m cli fatigue \
  --criterion de_asme_elliptic \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Se 29.3 \
  --Sut 105 \
  --Sy 82 \
  --strength-unit ksi \
  --Ma 1260 \
  --Mm 0 \
  --Ta 0 \
  --Tm 1100 \
  --d 1.1
```

### DE-Soderberg

```bash
python -m cli fatigue \
  --criterion de_soderberg \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Se 29.3 \
  --Sut 105 \
  --Sy 82 \
  --strength-unit ksi \
  --Ma 1260 \
  --Mm 0 \
  --Ta 0 \
  --Tm 1100 \
  --d 1.1
```

### Yield Factor of Safety

```bash
python -m cli yield \
  --Kf 1.58 \
  --Kfs 1.37 \
  --Sy 82 \
  --strength-unit ksi \
  --Ma 1260 \
  --Tm 1100 \
  --d 1.1
```

#### Example 7-3

### Vector Sums

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

#### Example 7-4

### Diameter Resize

```bash
python -m cli diameter-resize \
  --d-old 1.0 \
  --response-old 0.001095 \
  --response-allow 0.0005 \
  --mode slope
```

### Torsion Angle

```bash
python -m cli torsion-angle \
  --G 11500000 \
  --T 1200 \
  --length 8 \
  --J 0.30 \
  --length 10 \
  --J 0.45
```

### Torsional Stiffness

```bash
python -m cli torsional-stiffness \
  --G 11500000 \
  --length 8 \
  --J 0.30 \
  --length 10 \
  --J 0.45
```

#### Example 7-1 - Solve from File

### Solve Fatigue Problem From File - DE-Goodman

```bash
python -m cli run \
  --infile fatigue_goodman.json \
  --outfile example_7_1_goodman.json
```

### Solve Fatigue Problem From File - DE-Gerber

```bash
python -m cli run \
  --infile fatigue_gerber.json \
  --outfile example_7_1_gerber.json
```

### Solve Fatigue Problem From File - DE-ASME-Elliptic

```bash
python -m cli run \
  --infile fatigue_asme_elliptic.json \
  --outfile example_7_1_asme_elliptic.json
```

### Solve Fatigue Problem From File - DE-Soderberg

```bash
python -m cli run \
  --infile fatigue_soderberg.json \
  --outfile example_7_1_soderberg.json
```

### Solve Diameter Resize Problem From File

```bash
python -m cli run \
  --infile resize_slope.json \
  --outfile example_7_4.json
```

### Solve Vector Sum Problem From File

```bash
python -m cli run \
  --infile vector_sum.json \
  --outfile example_7_3.json
```

#### Example 7-2 - Solve from File

### DE-Goodman

```bash
python -m cli run \
  --infile example_7_2_initial_goodman.json \
  --outfile example_7_2_initial_goodman_out.json
```

## Notes

- Enter all chart-based factors manually.
- External beam-analysis outputs are expected to be entered manually.
- Units are user-responsibility; keep them consistent.
- JSON input files are searched in this order: current working directory, `shafts/in`, then the raw path.
