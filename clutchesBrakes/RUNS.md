# clutchesBrakes RUNS

Run commands are intended to be executed **from inside the `clutchesBrakes` directory**.

## One-time shell helper

```bash
runroot() {
  local d="$PWD"
  while [ "$d" != "/" ]; do
    if [ -f "$d/cli.py" ] && [ -f "$d/app.py" ] && [ -d "$d/in" ] && [ -d "$d/out" ]; then
      (cd "$d" && "$@")
      return
    fi
    d="$(dirname "$d")"
  done
  echo "Could not locate clutchesBrakes package root." >&2
  return 1
}
```

## Generate templates

```bash
python -m cli template doorstop --outfile doorstop_template.json
python -m cli template rim_brake --outfile rim_brake_template.json
python -m cli template annular_pad --outfile annular_pad_template.json
```

## Solve Example 16-1 from JSON

```bash
python -m cli run \
  --infile example_16_1_uniform_leftward.json \
  --outfile example_16_1_uniform_leftward_out.json
```

```bash
python -m cli run \
  --infile example_16_1_uniform_rightward.json \
  --outfile example_16_1_uniform_rightward_out.json
```

```bash
python -m cli run \
  --infile example_16_1_linear_leftward.json \
  --outfile example_16_1_linear_leftward_out.json
```

## Solve Example 16-2 from JSON

```bash
python -m cli run \
  --infile example_16_2_rim_brake.json \
  --outfile example_16_2_rim_brake_out.json
```

## Solve Example 16-3 from JSON

```bash
python -m cli run \
  --infile example_16_3_annular_pad.json \
  --outfile example_16_3_annular_pad_out.json
```

## CLI-only doorstop solve

```bash
python -m cli doorstop \
  --F 10 \
  --a 4 \
  --b 2 \
  --c 1.6 \
  --w1 1 \
  --w2 0.75 \
  --mu 0.4 \
  --pressure-model uniform \
  --motion leftward \
  --outfile doorstop_cli.json
```

## CLI-only rim brake solve

```bash
python -m cli rim_brake \
  --mu 0.32 \
  --p-a 1000000 \
  --b 0.032 \
  --r 0.150 \
  --a 0.1227 \
  --c 0.212 \
  --theta1-deg 0 \
  --theta2-deg 126 \
  --theta-a-deg 90 \
  --rotation clockwise \
  --Fx 0.927281 \
  --Fy 2.082942 \
  --actuator-force-units kN \
  --pair-enable \
  --pair-rotation counterclockwise \
  --pair-Fx -0.927281 \
  --pair-Fy 2.082942 \
  --pair-actuator-force-units kN \
  --outfile rim_brake_pair_example_16_2.json
```

## CLI-only rim brake (main shoe) solve

```bash
python -m cli rim_brake \
  --mu 0.32 \
  --p-a 1000000 \
  --b 0.032 \
  --r 0.150 \
  --a 0.1227 \
  --c 0.212 \
  --theta1-deg 0 \
  --theta2-deg 126 \
  --theta-a-deg 90 \
  --rotation clockwise \
  --Fx 0.927281 \
  --Fy 2.082942 \
  --actuator-force-units kN \
  --outfile rim_brake_main_shoe.json
```

## CLI-only rim brake (other shoe) solve

```bash
python -m cli rim_brake \
  --mu 0.32 \
  --p-a 442837.191551 \
  --b 0.032 \
  --r 0.150 \
  --a 0.1227 \
  --c 0.212 \
  --theta1-deg 0 \
  --theta2-deg 126 \
  --theta-a-deg 90 \
  --rotation counterclockwise \
  --Fx -0.927281 \
  --Fy 2.082942 \
  --actuator-force-units kN \
  --outfile rim_brake_other_shoe.json
```

## CLI-only annular pad solve

```bash
python -m cli annular_pad \
  --model uniform_wear \
  --mu 0.37 \
  --ri 3.875 \
  --ro 5.50 \
  --theta2-deg 108 \
  --n-pads 2 \
  --torque-total 13000 \
  --cylinder-diameter 1.5 \
  --n-cylinders 2 \
  --outfile annular_cli.json
```
