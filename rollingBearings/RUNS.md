# rollingBearings

Run these commands from inside the `rollingBearings` package directory.

## Example 11-1 style: required catalog C10

```bash
python -m cli catalog_c10 \
  --FD 400 \
  --hours 5000 \
  --speed-rpm 1725
````

## Example 11-3 style: required catalog C10

```bash
python -m cli catalog_c10_reliable \
  --FD 413 \
  --af 1.2 \
  --hours 30000 \
  --speed-rpm 300 \
  --reliability 0.99 \
  --a 3 \
  --x0 0.02 \
  --theta-minus-x0 4.439 \
  --b 1.483
````

## Solve Example 11-4 style problem from file

```bash
python -m cli run \
  --infile ex_11_4.json \
  --outfile ex_11_4.out.json
```

## Solve Example 11-7 cylindrical roller preselection - needs review

```bash
python -m cli run \
  --infile ex_11_7_bearing_D.json \
  --outfile ex_11_7_bearing_D.out.json
```

## Solve Example 11-7 angular-contact selection - needs review

```bash
python -m cli run \
  --infile ex_11_7_bearing_C.json \
  --outfile ex_11_7_bearing_C.out.json
```

## Solve Example 11-8 tapered pair (direct mount) - needs review

```bash
python -m cli run \
  --infile ex_11_8.json \
  --outfile ex_11_8.out.json
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
  --infile ex_11_11.json \
  --outfile ex_11_11.out.json
```

## RipGrep

rg "figure_11_15_timken_straight_bore_partial.csv" rollingBearings
rg "figure_11_15_timken_straight_bore_partial" rollingBearings
rg "table_11_3_cylindrical_roller" rollingBearings
rg "table_11_2_ball_bearings" rollingBearings
rg "table_11_1_ball_equivalent_factors" rollingBearings
