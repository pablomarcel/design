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

## Philpot Example 13.2

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx -680e-6 \
  --eyy 320e-6 \
  --ezz 0 \
  --gxy -980e-6 \
  --gyz 0 \
  --gxz 0 \
  --unit microstrain \
  --pretty \
  --show-plot \
  --show
```

## Philpot Example 13.3

```bash
python -m cli run \
  --solve-path general_3d_strain \
  --exx 435e-6 \
  --eyy -135e-6 \
  --ezz 0 \
  --gxy -642e-6 \
  --gyz 0 \
  --gxz 0 \
  --unit microstrain \
  --pretty \
  --show-plot \
  --show
```

## Example 13.4 equiangular rosette + principal strains

```bash
python -m cli run \
  --solve-path strain_rosette_equiangular \
  --ea -600e-6 \
  --eb -900e-6 \
  --ec 700e-6 \
  --nu 0.30 \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Example 13.4 - Same rosette commands with custom output files

```bash
python -m cli run \
  --solve-path strain_rosette_general \
  --ea 350e-6 \
  --eb 990e-6 \
  --ec 900e-6 \
  --theta-a 45 \
  --theta-b 90 \
  --theta-c 135 \
  --E 115000 \
  --nu 0.307 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --outfile out/example_13_9.json \
  --plotfile out/example_13_9.png \
  --pretty
```

## Example 13.4 - General 3-gage rosette with arbitrary angles

```bash
python -m cli run \
  --solve-path strain_rosette_general \
  --ea -600e-6 \
  --eb -900e-6 \
  --ec 700e-6 \
  --theta-a 0 \
  --theta-b 135 \
  --theta-c 225 \
  --E 200000 \
  --nu 0.3 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```


## Example 13.6

```bash
python -m cli run \
  --solve-path hooke_3d_from_strain \
  --exx -650e-6 \
  --eyy -370e-6 \
  --ezz -370e-6 \
  --gxy 0 \
  --gyz 0 \
  --gxz 0 \
  --E 55000 \
  --nu 0.22 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Example 13.6 - output files named explicitly

```bash
python -m cli run \
  --solve-path hooke_3d_from_strain \
  --exx -650e-6 \
  --eyy -370e-6 \
  --ezz -370e-6 \
  --gxy 0 \
  --gyz 0 \
  --gxz 0 \
  --E 55000 \
  --nu 0.22 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --outfile out/example_13_6.json \
  --plotfile out/example_13_6.png \
  --pretty \
  --show
```

## Example 13.7 likely rectangular rosette + stress along gage b

```bash
python -m cli run \
  --solve-path strain_rosette_rectangular \
  --ea -420e-6 \
  --eb 380e-6 \
  --ec 240e-6 \
  --E 10000 \
  --nu 0.33 \
  --stress-unit ksi \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Example 13.8 - Single gage on a biaxial plane-stress state 

```bash
python -m cli run \
  --solve-path single_gauge_biaxial_plane_stress \
  --sxx 70 \
  --E 210000 \
  --G 80000 \
  --eg 230e-6 \
  --theta-deg 60 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Example 13.9 full rosette + stress recovery

```bash
python -m cli run \
  --solve-path strain_rosette_general \
  --ea 350e-6 \
  --eb 990e-6 \
  --ec 900e-6 \
  --theta-a 45 \
  --theta-b 90 \
  --theta-c 135 \
  --E 115000 \
  --nu 0.307 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Rectangular rosette (0, 45, 90)

```bash
python -m cli run \
  --solve-path strain_rosette_rectangular \
  --ea -420e-6 \
  --eb 380e-6 \
  --ec 240e-6 \
  --E 10000 \
  --nu 0.33 \
  --unit microstrain \
  --pretty \
  --show
```

## Rectangular rosette (0, 45, 90) - stress units

```bash
python -m cli run \
  --solve-path strain_rosette_rectangular \
  --ea -420e-6 \
  --eb 380e-6 \
  --ec 240e-6 \
  --E 10000 \
  --nu 0.33 \
  --stress-unit ksi \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Equiangular rosette (0, 120, 240)

```bash
python -m cli run \
  --solve-path strain_rosette_equiangular \
  --ea -600e-6 \
  --eb -900e-6 \
  --ec 700e-6 \
  --nu 0.30 \
  --unit microstrain \
  --pretty \
  --show
```

## Equiangular rosette (0, 120, 240) - recovered stresses from isotropic Hooke’s law

```bash
python -m cli run \
  --solve-path strain_rosette_equiangular \
  --ea -600e-6 \
  --eb -900e-6 \
  --ec 700e-6 \
  --E 210000 \
  --nu 0.30 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```

## General 3-gage rosette with arbitrary angles

```bash
python -m cli run \
  --solve-path strain_rosette_general \
  --ea 350e-6 \
  --eb 990e-6 \
  --ec 900e-6 \
  --theta-a 45 \
  --theta-b 90 \
  --theta-c 135 \
  --E 115000 \
  --nu 0.307 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```


## Single gage on a biaxial plane-stress state - nu instead of G

```bash
python -m cli run \
  --solve-path single_gauge_biaxial_plane_stress \
  --sigma-x 70 \
  --E 210000 \
  --nu 0.3125 \
  --eg 230e-6 \
  --theta-deg 60 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```

## Generalized Hooke’s law, 3D, from strain

```bash
python -m cli run \
  --solve-path hooke_3d_from_strain \
  --exx -650e-6 \
  --eyy -370e-6 \
  --ezz -370e-6 \
  --gxy 0 \
  --gyz 0 \
  --gxz 0 \
  --E 55000 \
  --nu 0.22 \
  --stress-unit MPa \
  --strain-unit microstrain \
  --pretty \
  --show
```