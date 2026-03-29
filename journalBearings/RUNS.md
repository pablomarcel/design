# journalBearings RUNS

Run these commands from inside the `journalBearings` package directory.

## Example 12-1 from CLI flags

```bash
python -m cli ex12_1 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --h0-over-c 0.42 \
  --epsilon 0.58 \
  --phi-deg 53 \
  --outfile out/example_12_1.json
```

## Example 12-2 from CLI flags

```bash
python -m cli ex12_2 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --rcf 3.50 \
  --outfile out/example_12_2.json
```

## Example 12-3 from CLI flags

```bash
python -m cli ex12_3 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --q-over-rcNl 4.28 \
  --qs-over-q 0.655 \
  --outfile out/example_12_3.json
```

## Example 12-4 from CLI flags

```bash
python -m cli ex12_4 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --p-over-pmax 0.42 \
  --theta-pmax-deg 18.5 \
  --theta-p0-deg 75 \
  --outfile out/example_12_4.json
```

## Interactive mode

When chart values are not known in advance, let the app pause and prompt for them:

```bash
python -m cli ex12_1 \
  --mu 4e-6 \
  --N 30 \
  --W 500 \
  --r 0.75 \
  --c 0.0015 \
  --l 1.5 \
  --interactive
```

## Solve from JSON file

```bash
python -m cli run \
  --infile in/example_12_3.json \
  --outfile out/example_12_3_from_file.json
```
