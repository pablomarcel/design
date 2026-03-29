# journalBearings RUNS

Run these commands from inside the `journalBearings` package directory.

## The intended lazy-student workflow: let the app stop at charts

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

The app will compute `P`, `S`, `l/d`, and `r/c`, then pause and ask for:

- `h0/c`
- `epsilon`
- `phi`

## Coefficient of friction with hold-at-chart behavior

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

The app will pause and ask for `(r/c)f` from Figure 12-18.

## Volumetric flow rate with hold-at-chart behavior

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

The app will pause and ask for:

- `Q/(rcNl)`
- `Qs/Q`

## Maximum film pressure with hold-at-chart behavior

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

The app will pause and ask for:

- `P/pmax`
- `theta_pmax`
- `theta_p0`

## Menu mode

```bash
python -m cli menu
```

This launches a simple menu, asks for the givens, then pauses whenever a chart read is needed.

## JSON workflow with missing chart values on purpose

```bash
python -m cli run \
  --infile in/minimum_film_thickness_prompt.json \
  --outfile out/minimum_film_thickness_prompt_result.json
```

The JSON supplies the known givens only. The app will prompt for missing chart values.

## Strict mode without prompting

```bash
python -m cli run \
  --infile in/minimum_film_thickness_prefilled.json \
  --outfile out/minimum_film_thickness_prefilled_result.json \
  --no-prompt
```

Use `--no-prompt` only when all required chart values are already known.
