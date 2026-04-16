# static_failure RUNS

Run these commands from inside the `static_failure` package directory.

## Solve the Example 5-1 style problem from JSON

```bash
python -m cli run \
  --infile example_5_1_factor_of_safety.json \
  --outfile example_5_1_factor_of_safety_out.json \
  --pretty \
  --show
```

## Direct CLI solve for plane-stress cases

```bash
python -m cli ductile_failure_fos \
  --Syt 100 \
  --Syc 100 \
  --ef 0.55 \
  --strength-unit kpsi \
  --case a 70 70 0 \
  --case b 60 40 -15 \
  --case c 0 40 45 \
  --case d -40 -60 15 \
  --outfile direct_example_5_1_out.json \
  --pretty \
  --show
```
