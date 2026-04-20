# RUNS.md

Run these commands from inside the `load_stress` package directory.

## List available solve paths

```bash
python -m cli list
```

```bash
python -m cli list --json
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

## Plane-stress - No-plot run

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

## 2D Strain

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0
```

## 2D strain, no arbitrary angle

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --unit microstrain \
  --pretty \
  --show
```

## 2D strain with arbitrary angle

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --phi-deg 20 \
  --strain-unit "microstrain" \
  --pretty \
  --show
```

## Dedicated 2D rotation route

```bash
python -m cli run \
  --solve-path plane_strain_rotation \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --phi-deg 20 \
  --unit microstrain \
  --pretty \
  --show
```

## 2D Strain

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --phi-deg 17
```

## 2D strain with custom output files

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --phi-deg 20 \
  --unit microstrain \
  --outfile out/plane_strain_phi20.json \
  --plotfile out/plane_strain_phi20.png \
  --pretty
```

## 2D strain without generating a plot

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --unit microstrain \
  --pretty \
  --no-plot \
  --show
```

## 2D strain with displayed plot window

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy 642e-6 \
  --gyz 0 \
  --gxz 0 \
  --phi-deg 20 \
  --unit microstrain \
  --show-plot \
  --pretty
```

## Same 2D case, but using plain decimal strain values

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 0.000435 \
  --eyy -0.000135 \
  --ezz 0.0 \
  --gxy 0.000642 \
  --gyz 0.0 \
  --gxz 0.0 \
  --phi-deg 20 \
  --unit strain \
  --pretty \
  --show
```

## 3D general strain

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 420e-6 \
  --eyy -180e-6 \
  --ezz 90e-6 \
  --gxy 300e-6 \
  --gyz -120e-6 \
  --gxz 210e-6 \
  --unit microstrain \
  --pretty \
  --show
```

## 3D general strain with custom output files

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 420e-6 \
  --eyy -180e-6 \
  --ezz 90e-6 \
  --gxy 300e-6 \
  --gyz -120e-6 \
  --gxz 210e-6 \
  --unit microstrain \
  --outfile out/general_3d_strain_case_01.json \
  --plotfile out/general_3d_strain_case_01.png \
  --pretty
```

## 3D Strain

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 420e-6 \
  --eyy -180e-6 \
  --ezz 90e-6 \
  --gxy 300e-6 \
  --gyz -120e-6 \
  --gxz 210e-6
```