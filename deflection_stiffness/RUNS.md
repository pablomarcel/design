# RUNS — `deflection_stiffness` Command Cookbook

Core CLI:

```bash
runroot python -m deflection_stiffness.cli [validate|solve|template] ...
```

## -1) One-time session bootstrap (design root discovery)

```bash
# --- run-from-root helpers (design-aware) ---------------------------------
_mech_root() {
  local d="$PWD"
  while [ "$d" != "/" ]; do
    # Layout A: .../design/deflection_stiffness
    if [ -d "$d/deflection_stiffness" ] && [ -f "$d/deflection_stiffness/__init__.py" ]; then
      echo "$d"; return
    fi
    # Layout B: .../repo/design/deflection_stiffness
    if [ -d "$d/design/deflection_stiffness" ] && [ -f "$d/design/deflection_stiffness/__init__.py" ]; then
      echo "$d/design"; return
    fi
    d="$(dirname "$d")"
  done
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git rev-parse --show-toplevel
    return
  fi
  echo "$PWD"
}
runroot() { ( cd "$(_mech_root)" && "$@" ); }
runroot mkdir -p deflection_stiffness/out deflection_stiffness/in
```

## 0) Help

```bash
runroot python -m deflection_stiffness.cli \
  --help
```

```bash
runroot python -m deflection_stiffness.cli solve \
  --help
```

## 1) Generate templates

```bash
runroot python -m deflection_stiffness.cli template \
  --kind beam_simple \
  --outfile deflection_stiffness/in/beam_simple.json
```

```bash
runroot python -m deflection_stiffness.cli template \
  --kind simply_supported_point \
  --outfile deflection_stiffness/in/simply_supported_point.json
```

## 2) Validate

```bash
runroot python -m deflection_stiffness.cli validate \
  --infile deflection_stiffness/in/beam_simple.json
```

```bash
runroot python -m deflection_stiffness.cli validate \
  --infile deflection_stiffness/in/beam_simple.json \
  --non-strict
```

## 3) Solve (default anastruct PNG plots)

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/beam_simple.json \
  --outdir deflection_stiffness/out/beam_simple_run
```

## 4) Solve with *all* anastruct plots + zip

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/beam_simple.json \
  --outdir deflection_stiffness/out/beam_simple_run_all \
  --plot-backend anastruct \
  --anastruct-plots structure,reaction_force,axial_force,shear_force,bending_moment,displacement \
  --plot-dpi 200 \
  --plot-figsize 12 8 \
  --zip-plots
```

## 5) Plotly fallback (interactive)

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/beam_simple.json \
  --outdir deflection_stiffness/out/beam_simple_plotly \
  --plot-backend plotly \
  --plot-format html \
  --deform-scale 20
```

Writes: `structure.html`, `deformed.html`.

## 6) Solve (default anastruct PNG plots) - Example 7-2 and 7-3 - xy plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xy.json \
  --outdir deflection_stiffness/out/ex_7_2_xy \
  --deform-scale 200
```

## 6a) Solve (default anastruct PNG plots) - Example 7-2 and 7-3 - xy plane - DEBUG

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xy.json \
  --outdir deflection_stiffness/out/ex_7_2_xy \
  --deform-scale 200 \
  --log-level DEBUG
```

## 6b) Solve (default anastruct PNG plots) - Example 7-2 and 7-3 - xz plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xz.json \
  --outdir deflection_stiffness/out/ex_7_2_xz \
  --deform-scale 200
```

## 6c) Solve (default anastruct PNG plots) - Example 7-2 and 7-3 - xy plane - DEBUG

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xz.json \
  --outdir deflection_stiffness/out/ex_7_2_xz \
  --deform-scale 200 \
  --log-level DEBUG
```

## 7) Solve with *all* anastruct plots + zip - Example 7-2 and 7-3 - xy plane - all plots

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xy.json \
  --outdir deflection_stiffness/out/ex_7_2_xy_all \
  --plot-backend anastruct \
  --anastruct-plots structure,reaction_force,axial_force,shear_force,bending_moment,displacement \
  --plot-dpi 200 \
  --plot-figsize 12 8 \
  --zip-plots
```

## 7a) Solve with *all* anastruct plots + zip - Example 7-2 and 7-3 - xz plane - all plots

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xz.json \
  --outdir deflection_stiffness/out/ex_7_2_xz_all \
  --plot-backend anastruct \
  --anastruct-plots structure,reaction_force,axial_force,shear_force,bending_moment,displacement \
  --plot-dpi 200 \
  --plot-figsize 12 8 \
  --zip-plots
```

## 8) Plotly fallback (interactive) - Example 7-2 and 7-3 - xy plane - plotly

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xy.json \
  --outdir deflection_stiffness/out/ex_7_2_xy_plotly \
  --plot-backend plotly \
  --plot-format html \
  --deform-scale 20
```

## 8a) Plotly fallback (interactive) - Example 7-2 and 7-3 - xz plane - plotly

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_7_2_xz.json \
  --outdir deflection_stiffness/out/ex_7_2_xz_plotly \
  --plot-backend plotly \
  --plot-format html \
  --deform-scale 20
```

## 9) RipGrep

rg "show_bending_moment" deflection_stiffness

## 10) Solve (default anastruct PNG plots) - Problem 7-4 - part b - xy plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_4_b_xy.json \
  --outdir deflection_stiffness/out/p_7_4_b_xy
```

## 10a) Solve (default anastruct PNG plots) - Problem 7-4 - part b - xz plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_4_b_xz.json \
  --outdir deflection_stiffness/out/p_7_4_b_xz
```

## 11) Solve (default anastruct PNG plots) - Problem 7-4 - part a - xy plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_4_a_xy.json \
  --outdir deflection_stiffness/out/p_7_4_a_xy
```

## 11a) Solve (default anastruct PNG plots) - Problem 7-4 - part a - xz plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_4_a_xz.json \
  --outdir deflection_stiffness/out/p_7_4_a_xz
```

## 12) Solve (default anastruct PNG plots) - Problem 7-6 - xy plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_6_xy.json \
  --outdir deflection_stiffness/out/p_7_6_xy
```

## 12a) Solve (default anastruct PNG plots) - Problem 7-6 - xz plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_6_xz.json \
  --outdir deflection_stiffness/out/p_7_6_xz
```

## 13) Solve (default anastruct PNG plots) - Problem 7-17

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_17.json \
  --outdir deflection_stiffness/out/p_7_17
```

## 14) Solve (default anastruct PNG plots) - Problem 7-19 - xy plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_19_xy.json \
  --outdir deflection_stiffness/out/p_7_19_xy
```

## 14a) Solve (default anastruct PNG plots) - Problem 7-19 - xz plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/p_7_19_xz.json \
  --outdir deflection_stiffness/out/p_7_19_xz
```

## 15) Solve (default anastruct PNG plots) - Example 11-18 - xy plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_11_18_xy.json \
  --outdir deflection_stiffness/out/ex_11_18_xy
```

## 15a) Solve (default anastruct PNG plots) - Example 11-18 - xz plane

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_11_18_xz.json \
  --outdir deflection_stiffness/out/ex_11_18_xz
```

## 15c) Solve (default anastruct PNG plots) - Example 11-18 - xy plane - no plots

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_11_18_xy.json \
  --outdir deflection_stiffness/out/ex_11_18_xy \
  --no-plots
```

## 15d) Solve (default anastruct PNG plots) - Example 11-18 - xz plane - no plots

```bash
runroot python -m deflection_stiffness.cli solve \
  --infile deflection_stiffness/in/ex_11_18_xz.json \
  --outdir deflection_stiffness/out/ex_11_18_xz \
  --no-plots
```
