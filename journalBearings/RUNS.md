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

## Temperature rise — Khonsari Example 8.2 style

```bash
python -m cli temperature_rise \
  --mu 1.3e-6 \
  --N 30 \
  --W 1600 \
  --r 2.0 \
  --c 0.002 \
  --l 4.0 \
  --oil-grade 10 \
  --inlet-temp-f 166 \
  --rho 0.0315 \
  --cp 0.48 \
  --J 9336 \
  --temp-tol-f 2.0 \
  --max-iter 50 \
  --outfile out/ex_8_2_temperature_rise.json
```

This route:

- computes `S`
- solves for `epsilon`
- interpolates `Qbar_L`, `Qbar_i`, `(R/C)f`, `Pbar_max`, and angles
- computes `E_p` from Khonsari Eq. (8.43)
- computes `delta_T` from Khonsari Eq. (8.44)
- updates viscosity using the SAE oil correlation
- repeats until successive effective temperatures differ by at most `temp_tol_F`

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

## Example 8.2 minimum film thickness

```bash
python -m cli run \
  --infile in/ex_8_2_h.json \
  --outfile out/ex_8_2_h_out.json
```

## Example 8.2 coefficient of friction

```bash
python -m cli run \
  --infile in/ex_8_2_f.json \
  --outfile out/ex_8_2_f_out.json
```

## Example 8.2 volumetric flow rate

```bash
python -m cli run \
  --infile in/ex_8_2_q.json \
  --outfile out/ex_8_2_q_out.json
```

## Example 8.2 maximum film pressure

```bash
python -m cli run \
  --infile in/ex_8_2_p.json \
  --outfile out/ex_8_2_p_out.json
```
