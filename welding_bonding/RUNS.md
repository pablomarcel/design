# welding_bonding RUNS

Run these commands **from inside the `welding_bonding` package directory**.

## List solve paths

```bash
python -m cli list
```

## Solve Example 9-1 from input JSON

```bash
python -m cli run \
  --infile example_9_1_weld_group_torsion.json \
  --outfile example_9_1_weld_group_torsion_out.json \
  --pretty \
  --show
```

## Solve the same Example 9-1 using CLI flags only

```bash
python -m cli torsion \
  --title "Example 9-1 welded fitting into channel" \
  --weld-type 4 \
  --weld-size-mm 6 \
  --b-mm 56 \
  --d-mm 190 \
  --total-force-N 50000 \
  --group-share-count 2 \
  --moment-arm-mm 110.4 \
  --combination-model shigley_radial \
  --primary-shear-direction negative_x \
  --torsion-sign ccw \
  --outfile example_9_1_weld_group_torsion_flags_out.json \
  --pretty \
  --show
```

## Example 9-2

```bash
python -m cli run \
  --infile example_9_2_parallel_weld_static_loading.json \
  --outfile example_9_2_parallel_weld_static_loading_out.json \
  --pretty \
  --show
```

## Example 9-3

```bash
python -m cli run \
  --infile example_9_3_design_weld_static_loading.json \
  --outfile example_9_3_design_weld_static_loading_out.json \
  --pretty \
  --show
```

## Example 9-4

```bash
python -m cli run \
  --infile example_9_4_welded_joint_bending_static_loading.json \
  --outfile example_9_4_welded_joint_bending_static_loading_out.json \
  --pretty \
  --show
```

## Example 9-5

```bash
python -m cli run \
  --infile example_9_5_weld_fatigue_factor_of_safety.json \
  --outfile example_9_5_weld_fatigue_factor_of_safety_out.json \
  --pretty \
  --show
```

## Example 9-6

```bash
python -m cli run \
  --infile example_9_6_weld_fatigue_strength.json \
  --outfile example_9_6_weld_fatigue_strength_out.json \
  --pretty \
  --show
```

## Example 9-7

```bash
python -m cli run \
  --infile example_9_7_adhesive_double_lap_joint.json \
  --outfile example_9_7_adhesive_double_lap_joint_out.json \
  --pretty \
  --show
```