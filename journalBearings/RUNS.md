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

## Self-contained bearing steady state — Shigley Example 12-5 style

```bash
python -m cli self_contained_steady_state \
  --N 15 \
  --W 100 \
  --r 1.0 \
  --c 0.001 \
  --l 2.0 \
  --oil-grade 20 \
  --ambient-temp-f 70 \
  --alpha 1 \
  --area-in2 40 \
  --h-cr 2.7 \
  --temp-tol-f 2.0 \
  --max-iter 60 \
  --outfile out/ex_12_5_self_contained.json
```

This route:

- assumes a trial average film temperature
- computes oil viscosity from the SAE correlation
- computes Sommerfeld number and interpolates the finite-bearing table
- computes friction heat generation from the converged `f`
- computes heat loss with Shigley Eq. (12-19a)
- uses Fig. 12-24 polynomial correlations to estimate `delta_T_F`
- iterates on average film temperature until the heat-balance bracket is within `temp_tol_F`
- reports steady-state temperatures, friction, and minimum film thickness

## Pressure-fed circumferential-groove bearing — Shigley Example 12-6 style

Clearance `c` and ratio `l'/d` are treated as direct givens.

```bash
python -m cli pressure_fed_circumferential \
  --oil-grade 20 \
  --Ps 30 \
  --dj 1.750 \
  --c 0.0015 \
  --l-prime 0.875 \
  --l-prime-over-d 0.5 \
  --N 50 \
  --W 900 \
  --sump-temp-f 120 \
  --rho 0.0311 \
  --cp 0.42 \
  --J 9336 \
  --heat-loss-limit-btu-h 800 \
  --temp-tol-f 0.5 \
  --max-iter 60 \
  --outfile out/ex_12_6_pressure_fed.json
```

This route:

- uses the direct-given clearance `c`
- uses the direct-given ratio `l'/d` for table lookup
- uses Shigley Eq. (12-23) for `P_st = W / (4 r l')`
- iterates on trial average film temperature until `T_trial ≈ T_av`
- computes `mu` from the SAE correlation at each trial temperature
- computes `S`, `epsilon`, and `(fr/c)` from the finite-bearing dataset using the given `l'/d`
- computes `DeltaT_F` with Shigley Eq. (12-24)
- computes `h_min`, `T_max`, `P_st`, `Q_s`, `H_loss`, and friction torque after convergence

## Boundary Lubricated Bearings — Shigley Example 12-7 style

```bash
python -m cli boundary_lubricated_bearing \
  --bearing-model oiles_500_sp \
  --length 1.0 \
  --bore 1.0 \
  --ambient-temp-f 70 \
  --allowable-wear-in 0.005 \
  --radial-load-lbf 700 \
  --velocity-fpm 33 \
  --motion-type rotary \
  --outfile out/ex_12_7_boundary.json
```

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

## Example 12-5 from JSON

```bash
python -m cli run \
  --infile in/ex_12_5.json \
  --outfile out/ex_12_5_out.json
```

## Example 12-6 from JSON

```bash
python -m cli run \
  --infile in/ex_12_6.json \
  --outfile out/ex_12_6_out.json
```

## Example 12-7 from JSON

```bash
python -m cli run \
  --infile in/ex_12_7.json \
  --outfile out/ex_12_7_out.json
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
