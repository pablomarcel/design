# RUNS.md

Run these commands from inside the `spur_helical_gears` package directory.

## Spur gearset analysis — Example 14-4 style

```bash
python -m cli run \
  --infile example_14_4_spur_analysis.json \
  --outfile example_14_4_spur_analysis_out.json
```

## Helical gearset analysis — Example 14-5 style

```bash
python -m cli run \
  --infile example_14_5_helical_analysis.json \
  --outfile example_14_5_helical_analysis_out.json
```

## Spur gear design sweep — Example 14-8 style

```bash
python -m cli run \
  --infile example_14_8_spur_design.json \
  --outfile example_14_8_spur_design_out.json
```

## Pretty-print JSON as well

```bash
python -m cli run \
  --infile example_14_8_spur_design.json \
  --outfile example_14_8_spur_design_out.json \
  --pretty
```
