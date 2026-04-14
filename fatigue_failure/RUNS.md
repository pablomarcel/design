# fatigue_failure RUNS

Run these commands from inside the `fatigue_failure` package directory.

## List available solve paths

```bash
python -m cli list-solve-paths
```

## Solve Example 6-2 from input JSON

```bash
python -m cli run \
  --infile example_6_2_fatigue_strength.json \
  --outfile example_6_2_fatigue_strength_out.json \
  --pretty \
  --show
```

## Direct CLI solve using Table A-20 lookup

```bash
python -m cli fatigue_strength \
  --sae-aisi-no 1050 \
  --processing HR \
  --strength-at-cycles 10000 \
  --life-at-stress-kpsi 55 \
  --outfile example_6_2_cli_out.json \
  --pretty \
  --show
```

## Direct CLI solve with explicit strengths

```bash
python -m cli fatigue_strength \
  --sut-kpsi 90 \
  --se-prime-kpsi 45 \
  --strength-at-cycles 10000 \
  --life-at-stress-kpsi 55 \
  --show \
  --pretty
```
