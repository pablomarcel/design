# screws_fasteners CLI runs

Run these commands from inside the `screws_fasteners` package directory.

## Example 8-1 from file

```bash
python -m cli run \
  --infile example_8_1_square_thread_power_screw.json \
  --outfile example_8_1_square_thread_power_screw_out.json \
  --pretty \
  --show
```

## Example 8-2 mixed-material joint from file

```bash
python -m cli run \
  --infile example_8_2_fastener_member_stiffness_mixed.json \
  --outfile example_8_2_fastener_member_stiffness_mixed_out.json \
  --pretty \
  --show
```

## Example 8-2 all-steel joint from file

```bash
python -m cli run \
  --infile example_8_2_fastener_member_stiffness_steel.json \
  --outfile example_8_2_fastener_member_stiffness_steel_out.json \
  --pretty \
  --show
```

## Direct square-thread power screw solve

```bash
python -m cli power_screw \
  --major-diameter-mm 32 \
  --pitch-mm 4 \
  --starts 2 \
  --friction-thread 0.08 \
  --friction-collar 0.08 \
  --collar-mean-diameter-mm 40 \
  --axial-load-N 6400 \
  --engaged-threads 1 \
  --first-thread-load-fraction 0.38 \
  --show
```

## Direct fastener/member stiffness solve

```bash
python -m cli fastener_stiffness \
  --nominal-diameter-in 0.5 \
  --threads-per-inch 20 \
  --thread-series UNF \
  --bolt-length-in 1.5 \
  --washer-type N \
  --layer steel:0.095 \
  --layer steel:0.5 \
  --layer gray\ cast\ iron:0.75 \
  --show
```
