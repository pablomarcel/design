# journalBearings RUNS

Run these commands from inside the `journalBearings` package directory.

## The intended lazy-student workflow: let the app stop at charts

```bash
python -m cli ex12_1 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/example_12_1.json
```

The app will compute `P`, `S`, `l/d`, and `r/c`, then pause and ask for:

- `h0/c`
- `epsilon`
- `phi`

## Example 12-2 with hold-at-chart behavior

```bash
python -m cli ex12_2 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/example_12_2.json
```

The app will pause and ask for `(r/c)f` from Figure 12-18.

## Example 12-3 with hold-at-chart behavior

```bash
python -m cli ex12_3 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/example_12_3.json
```

The app will pause and ask for:

- `Q/(rcNl)`
- `Qs/Q`

## Example 12-4 with hold-at-chart behavior

```bash
python -m cli ex12_4 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --outfile out/example_12_4.json
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
  --infile in/example_12_1_prompt.json \
  --outfile out/example_12_1_prompt_result.json
```

The JSON supplies the known givens only. The app will prompt for missing chart values.

## Strict mode without prompting

```bash
python -m cli run \
  --infile in/example_12_1_prefilled.json \
  --outfile out/example_12_1_prefilled_result.json \
  --no-prompt
```

Use `--no-prompt` only when all required chart values are already known.
