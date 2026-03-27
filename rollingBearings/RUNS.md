# rollingBearings

Run these commands from inside the `rollingBearings` package directory.

## Example 11-1 / 11-3 style: required catalog C10

```bash
python -m cli catalog_c10 \
  --FD 413 \
  --af 1.2 \
  --hours 500 \
  --speed-rpm 600 \
  --reliability 0.99 \
  --a 3 \
  --x0 0.02 \
  --theta-minus-x0 4.439 \
  --b 1.483
````

## Solve Example 11-4 style problem from file

```bash
python -m cli run \
  --infile example_11_4_ball_l10_life.json \
  --outfile example_11_4_ball_l10_life.out.json
```

## Solve Example 11-7 cylindrical roller preselection

```bash
python -m cli run \
  --infile example_11_7_bearing_D.json \
  --outfile example_11_7_bearing_D.out.json
```

## Solve Example 11-7 angular-contact selection

```bash
python -m cli run \
  --infile example_11_7_bearing_C.json \
  --outfile example_11_7_bearing_C.out.json
```

## Solve Example 11-8 tapered pair (direct mount)

```bash
python -m cli run \
  --infile example_11_8_tapered_direct.json \
  --outfile example_11_8_tapered_direct.out.json
```

## Solve Example 11-10 tapered pair reliability

```bash
python -m cli tapered_reliability \
  --xD 2.67 \
  --C10 12100 \
  --af 1 \
  --FeA 4938 \
  --FeB 2654
```

## Solve Example 11-11 thrust-only tapered selection

```bash
python -m cli run \
  --infile example_11_11_tapered_thrust_only.json \
  --outfile example_11_11_tapered_thrust_only.out.json
```
