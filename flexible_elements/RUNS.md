# flexibleElements RUNS

Run these commands from inside the `flexible_elements` folder.

## List solve paths

```bash
python -m cli list
```

## Solve from input JSON files

### Example 17-1 style: flat-belt analysis

```bash
python -m cli run \
  --infile ex_17_1_flat_analysis.json \
  --outfile ex_17_1_flat_analysis_out.json
```

### Example 17-2 style: flat-belt drive design

```bash
python -m cli run \
  --infile ex_17_2_flat_design.json \
  --outfile ex_17_2_flat_design_out.json
```

### Example 17-3 style: flat metal belt selection

```bash
python -m cli run \
  --infile ex_17_3_metal_flat_selection.json \
  --outfile ex_17_3_metal_flat_selection_out.json
```

## CLI-flag runs

### Flat-belt analysis

```bash
python -m cli flat_analysis \
  --material Polyamide \
  --specification A-3 \
  --belt-width-in 6 \
  --driver-pulley-diameter-in 6 \
  --driven-pulley-diameter-in 18 \
  --center-distance-ft 8 \
  --driver-rpm 1750 \
  --nominal-power-hp 15 \
  --service-factor 1.25 \
  --design-factor 1.1 \
  --velocity-correction-factor 1 \
  --required-factor-of-safety 1.1
```

### Flat-belt design

```bash
python -m cli flat_design \
  --material Polyamide \
  --specification A-3 \
  --small-pulley-diameter-in 16 \
  --large-pulley-diameter-in 36 \
  --center-distance-ft 16 \
  --small-pulley-rpm 860 \
  --nominal-power-hp 60 \
  --service-factor 1.15 \
  --design-factor 1.05 \
  --velocity-correction-factor 1 \
  --initial-tension-maintenance catenary
```

### Flat metal belt selection

```bash
python -m cli metal_flat_selection \
  --alloy "301 or 302 stainless steel" \
  --thickness-in 0.003 \
  --pulley-diameter-in 4 \
  --friction-coefficient 0.35 \
  --torque-lbf-in 30 \
  --required-belt-passes 1000000 \
  --available-widths-in 0.25 0.375 0.5 0.75 1.0
```

### RipGrep

rg "flexibleElements" flexibleElements