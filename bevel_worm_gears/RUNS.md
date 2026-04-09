# bevel_worm_gears run commands

Run these commands from inside the `bevel_worm_gears` package directory.

## List sample inputs

```bash
python -m cli list-inputs
```

## Example 15-1 style straight bevel gear analysis

```bash
python -m cli run \
  --infile ex_15_1_straight_bevel_analysis.json \
  --outfile ex_15_1_straight_bevel_analysis_out.json
```

## Example 15-2 style straight bevel gear mesh design

```bash
python -m cli run \
  --infile ex_15_2_straight_bevel_mesh_design.json \
  --outfile ex_15_2_straight_bevel_mesh_design_out.json
```
