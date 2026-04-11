# gears package run commands

Run these commands from inside the `gears` package directory.

## Example 13-7 style spur gear force analysis

```bash
python -m cli run \
  --infile ex_13_7_spur_force.json \
  --outfile ex_13_7_spur_force_out.json
```

## Example 13-8 style bevel gear force analysis

```bash
python -m cli run \
  --infile ex_13_8_bevel_force.json \
  --outfile ex_13_8_bevel_force_out.json
```

## Example 13-9 style helical gear force analysis

```bash
python -m cli run \
  --infile ex_13_9_helical_force.json \
  --outfile ex_13_9_helical_force_out.json
```

## Example 13-10 style worm gear force analysis

```bash
python -m cli run \
  --infile ex_13_10_worm_force.json \
  --outfile ex_13_10_worm_force_out.json
```

## Inline solve example

```bash
python -m cli solve \
  --json '{"title":"inline spur case","inputs":{"solve_path":"spur_force","power_kw":2.5,"module_mm":2.5,"pressure_angle_deg":20.0,"driver_gear_id":"g2","selected_gear":"g3","gears":{"g2":{"teeth":24,"speed_rpm":1750},"g3":{"teeth":24,"speed_rpm":1750}},"meshes_on_selected_gear":[{"name":"g2_on_g3","tangential_unit_on_selected":[-1,0,0],"radial_unit_on_selected":[0,1,0]}]}}'
```
