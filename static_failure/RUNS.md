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

## Example 5-2 direct CLI

```bash
python -m cli run \
  --infile example_5_2_coulomb_mohr.json \
  --outfile example_5_2_coulomb_mohr_out.json \
  --pretty \
  --show
```

```bash
python -m cli coulomb_mohr_fos \
  --material-lookup cast_195_t6_aluminum \
  --stress-input-mode torsion_shaft \
  --diameter-mm 25 \
  --torque-N-m 230 \
  --outfile example_5_2_coulomb_mohr_out.json \
  --pretty \
  --show
```

## Example 5-3 from input JSON

```bash
python -m cli run \
  --infile example_5_3_failure_theory_strength.json \
  --outfile example_5_3_failure_theory_strength_out.json \
  --pretty \
  --show
```

## Direct CLI - Example 5-3 style

```bash
python -m cli failure_theory_strength \
  --material-lookup aisi_1035_steel_forged_heat_treated \
  --strength-unit kpsi \
  --diameter-in 1.0 \
  --bending-moment-arm-in 14.0 \
  --torsion-arm-in 15.0 \
  --design-factor 1.0 \
  --force-unit lbf \
  --moment-unit 'lbf·in' \
  --outfile example_5_3_failure_theory_strength_out.json \
  --pretty \
  --show
```

## Example 5-4 from input JSON

```bash
python -m cli run \
  --infile example_5_4_realized_factor_of_safety.json \
  --outfile example_5_4_realized_factor_of_safety_out.json \
  --pretty \
  --show
```

## Direct CLI - Example 5-4 style

```bash
python -m cli realized_fos_stock_tube \
  --material-lookup al_2014_specified_min_yield_276_mpa \
  --strength-unit MPa \
  --required-design-factor 4 \
  --axial-force-N 9000 \
  --bending-load-N 1750 \
  --bending-moment-arm-mm 120 \
  --torsion-N-m 72 \
  --size-system mm \
  --outfile example_5_4_realized_factor_of_safety_out.json \
  --pretty \
  --show
```

## Example 5-5

```bash
python -m cli run \
  --infile example_5_5_brittle_materials.json \
  --outfile example_5_5_brittle_materials_out.json \
  --pretty \
  --show
```

## Direct CLI Example 5-5 using normalized stresses

```bash
python -m cli brittle_failure_strength \
  --gray-cast-iron-astm-grade 30 \
  --stress-input-mode linear_plane_stress_per_force \
  --sigma-x-per-force 0.1426 \
  --tau-xy-per-force 0.0764 \
  --strength-unit kpsi \
  --force-unit lbf \
  --outfile example_5_5_direct_out.json \
  --pretty \
  --show
```

## Example 5-6 from input JSON

```bash
python -m cli run \
  --infile example_5_6_transverse_crack.json \
  --outfile example_5_6_transverse_crack_out.json \
  --pretty \
  --show
```

## Direct CLI solve for Example 5-6 style problem

```bash
python -m cli transverse_crack_fracture \
  --K-Ic 28.3 \
  --Syt 240 \
  --strength-unit MPa \
  --nominal-stress 50 \
  --length-unit mm \
  --geometry-mode figure_5_25_off_center_crack_longitudinal_tension \
  --two-a 65 \
  --d 6000 \
  --b 6000 \
  --crack-tip A \
  --outfile example_5_6_transverse_crack_out.json \
  --pretty \
  --show
```

## Example 5-7 from input JSON

```bash
python -m cli run \
  --infile example_5_7_edge_crack_alloy_selection.json \
  --outfile example_5_7_edge_crack_alloy_selection_out.json \
  --pretty \
  --show
```

## Direct CLI solve

```bash
python -m cli edge_crack_alloy_selection \
  --force-N 4000000 \
  --plate-width-m 1.4 \
  --plate-length-m 2.8 \
  --edge-crack-a-mm 2.7 \
  --required-safety-factor 1.3 \
  --material-family Titanium \
  --material-grade Ti-6AL-4V \
  --beta-figure-id figure_5_26 \
  --figure-5-26-family solid_no_bending_constraints \
  --outfile example_5_7_edge_crack_alloy_selection_out.json \
  --pretty \
  --show
```
