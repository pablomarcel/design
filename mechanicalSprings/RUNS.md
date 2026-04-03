# mechanicalSprings RUNS

Run commands from inside the `mechanicalSprings` package directory.

## Show available solve paths

```bash
python -m cli show-solve-paths
```

## Example 10-1 style: compression spring analysis

```bash
python -m cli run \
  --infile example_10_1_analysis.json \
  --outfile example_10_1_analysis_out.json
```

## Example 10-2 style: static spring selection table

```bash
python -m cli run \
  --infile example_10_2_static_select.json \
  --outfile example_10_2_static_select_out.json
```

## Example 10-3 style: iterative C-based static design

```bash
python -m cli run \
  --infile example_10_3_static_iter_c.json \
  --outfile example_10_3_static_iter_c_out.json
```

## Example 10-4 style: fatigue check using Gerber, Sines, and Goodman

```bash
python -m cli run \
  --infile example_10_4_fatigue_check.json \
  --outfile example_10_4_fatigue_check_out.json
```

## Example 10-5 style: fatigue design table

```bash
python -m cli run \
  --infile example_10_5_fatigue_design.json \
  --outfile example_10_5_fatigue_design_out.json
```

## Inline payload route

```bash
python -m cli solve \
  --payload '{"solve_path":"compression_analysis","material":"music wire","d_in":0.105,"OD_in":0.945,"end_type":"squared_and_ground","Nt":14}'
```

## Example 10-6 Extension Spring Static Service

```bash
python -m cli run \
  --infile example_10_6_extension_static.json \
  --outfile example_10_6_extension_static_out.json
```

## Example 10-7 Extension Spring Dynamic Loading

```bash
python -m cli run \
  --infile example_10_7_extension_dynamic.json \
  --outfile example_10_7_extension_dynamic_out.json
```

## Example 10-8 Torsion Spring

```bash
python -m cli run \
  --infile example_10_8_torsion_spring.json \
  --outfile example_10_9_torsion_spring_out.json
```

## RipGrep

rg "music wire" mechanicalSprings