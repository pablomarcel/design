# journalBearings RUNS

Run these commands from inside the `journalBearings` package directory.

## Minimum film thickness

```bash
python -m cli minimum_film_thickness \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/minimum_film_thickness.json
```

This route now computes the Sommerfeld number, solves for `epsilon` from the table automatically, then reports:

- `h_min = C(1 - epsilon)`
- `e = epsilon C`
- `phi`

## Coefficient of friction

```bash
python -m cli coefficient_of_friction \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/coefficient_of_friction.json
```

This route now uses `RC_over_C_times_f` from the dataset automatically.

## Volumetric flow rate

```bash
python -m cli volumetric_flow_rate \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/volumetric_flow_rate.json
```

This route reports:

- `Q_leakage` from `Qbar_L`
- `Q_inlet` from `Qbar_i`
- `Q_total_shigley_equivalent = Q_inlet`
- `Q_side_shigley_equivalent = Q_leakage`

## Maximum film pressure

```bash
python -m cli maximum_film_pressure \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/maximum_film_pressure.json
```

This route reports `pmax` from `Pbar_max` and the Khonsari angle outputs available in the dataset.

## Menu mode

```bash
python -m cli menu
```

This launches a simple menu, asks for the givens, and solves automatically with interpolation.

## JSON workflow

```bash
python -m cli run \
  --infile in/minimum_film_thickness.json \
  --outfile out/minimum_film_thickness_from_file.json
```

The JSON supplies only the real bearing givens. No manual chart-entry block remains in this version.
