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

## Example 6-3 from JSON

```bash
python -m cli run \
  --infile example_6_3_surface_factor.json \
  --outfile example_6_3_surface_factor_out.json \
  --pretty \
  --show
```

## Example 6-3 from CLI flags

```bash
python -m cli surface_factor \
  --surface-finish "Machined or cold-drawn" \
  --sut-mpa 520 \
  --strength-unit MPa \
  --pretty \
  --show
```

## Example 6-4 from JSON

```bash
python -m cli run \
  --infile example_6_4_size_factor.json \
  --outfile example_6_4_size_factor_out.json \
  --pretty \
  --show
```

```bash
python -m cli size_factor \
  --loading-type bending \
  --mode rotating \
  --diameter-mm 32 \
  --sut-mpa 690 \
  --expected-kb 0.858 \
  --pretty \
  --show
```

```bash
python -m cli size_factor \
  --loading-type bending \
  --mode nonrotating \
  --shape solid_round \
  --diameter-mm 32 \
  --sut-mpa 690 \
  --expected-kb 0.954 \
  --pretty \
  --show
```

## Example 6-5 from JSON

```bash
python -m cli run \
  --infile example_6_5_temperature_factor.json \
  --outfile example_6_5_temperature_factor_out.json \
  --pretty \
  --show
```

```bash
python -m cli temperature_factor \
  --service-temperature-f 450 \
  --sut-room-temperature-kpsi 70 \
  --se-prime-room-temperature-kpsi 39 \
  --temperature-factor-method polynomial \
  --pretty \
  --show
```

## Example 6-6 from JSON

```bash
python -m cli run \
  --infile example_6_6_stress_concentration_notch_sensitivity.json \
  --outfile example_6_6_stress_concentration_notch_sensitivity_out.json \
  --pretty \
  --show
```

```bash
python -m cli stress_concentration_notch_sensitivity \
  --sut-mpa 690 \
  --small-diameter-mm 32 \
  --large-diameter-mm 38 \
  --fillet-radius-mm 3 \
  --pretty \
  --show
```

```bash
python -m cli stress_concentration_notch_sensitivity \
  --sut-mpa 690 \
  --small-diameter-mm 32 \
  --large-diameter-mm 38 \
  --fillet-radius-mm 3 \
  --outfile example_6_6_stress_concentration_notch_sensitivity_out.json \
  --pretty \
  --show
```