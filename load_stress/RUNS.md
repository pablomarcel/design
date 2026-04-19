# RUNS.md

Run these commands from inside the `load_stress` package directory.

## List available solve paths

```bash
python -m cli list
```

## sandbox - Mohr circle

```bash
python -m sandbox.sandbox_mohr3d \
  --sxx 80 --syy 20 --szz 0 \
  --txy 30 --tyz 0 --tzx 0 \
  --show-plot
```

## sandbox - Example 3-4

```bash
python -m sandbox.sandbox_mohr3d \
  --sxx 80 --syy 0 --szz 0 \
  --txy -50 --tyz 0 --txz 0 \
  --show-plot
```

## sandbox - Example 3-4 - Optional Phi

```bash
python -m sandbox.sandbox_mohr3d \
  --sxx 80 --syy 0 --szz 0 \
  --txy -50 --tyz 0 --txz 0 \
  --phi-deg 15 \
  --show-plot
```

## General three-dimensional stress state

```bash
python -m cli run \
  --solve-path general_3d_stress \
  --sxx 80 \
  --syy 20 \
  --szz -10 \
  --txy -30 \
  --tyz 15 \
  --txz 10 \
  --unit MPa \
  --title "General 3D stress example" \
  --pretty \
  --show
```

## Plane-stress Example 3-4 style solve with rotation

```bash
python -m cli run \
  --solve-path general_3d_stress \
  --sxx 80 \
  --syy 0 \
  --szz 0 \
  --txy -50 \
  --phi-deg 20 \
  --unit ksi \
  --title "Plane stress with arbitrary angle" \
  --pretty \
  --show
```

## Plane-stress rotation route explicitly

```bash
python -m cli run \
  --solve-path plane_stress_rotation \
  --sxx 80 \
  --syy 0 \
  --szz 0 \
  --txy -50 \
  --phi-deg 25 \
  --unit ksi \
  --pretty
```

## No-plot run

```bash
python -m cli run \
  --solve-path general_3d_stress \
  --sxx 55 \
  --syy 10 \
  --szz -5 \
  --txy 12 \
  --tyz 4 \
  --txz -7 \
  --no-plot \
  --pretty
```