# screws_fasteners CLI runs

Run these commands from inside the `screws_fasteners` package directory.

## Example 8-1 - from file

```bash
python -m cli run \
  --infile example_8_1_square_thread_power_screw.json \
  --outfile example_8_1_square_thread_power_screw_out.json \
  --pretty \
  --show
```

## Example 8-2 mixed-material joint - from file

```bash
python -m cli run \
  --infile example_8_2_fastener_member_stiffness_mixed.json \
  --outfile example_8_2_fastener_member_stiffness_mixed_out.json \
  --pretty \
  --show
```

## Example 8-2 all-steel joint - from file

```bash
python -m cli run \
  --infile example_8_2_fastener_member_stiffness_steel.json \
  --outfile example_8_2_fastener_member_stiffness_steel_out.json \
  --pretty \
  --show
```

## Direct square-thread power screw solve - cli

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

## Direct fastener/member stiffness solve - cli

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

## Example 8-3 Bolt Strength - from file

```bash
python -m cli run \
  --infile example_8_3_bolt_strength.json \
  --outfile example_8_3_bolt_strength_out.json \
  --pretty \
  --show
```

## Example 8-3 Bolt Strength - cli

```bash
python -m cli bolt_strength \
  --nominal-diameter-in 0.75 \
  --threads-per-inch 16 \
  --thread-series UNF \
  --bolt-length-in 2.5 \
  --sae-grade 5 \
  --external-load-kip 6 \
  --initial-bolt-tension-kip 25 \
  --bolt-stiffness-Mlbf-per-in 6.5 \
  --member-stiffness-Mlbf-per-in 13.8 \
  --torque-factor-K 0.2 \
  --thread-friction 0.15 \
  --collar-friction 0.15 \
  --show
```

## Example 8-4 Statically Loaded Tension Joint with Preload - from file

```bash
python -m cli run \
  --infile example_8_4_statically_loaded_tension_joint_with_preload.json \
  --outfile example_8_4_statically_loaded_tension_joint_with_preload_out.json \
  --pretty \
  --show
```

## Example 8-4 Statically Loaded Tension Joint with Preload - auto - from file

```bash
python -m cli run \
  --infile example_8_4_statically_loaded_tension_joint_with_preload_auto.json \
  --outfile example_8_4_statically_loaded_tension_joint_with_preload_auto_out.json \
  --pretty \
  --show
```

## Example 8-4 Statically Loaded Tension Joint with Preload - cli

```bash
python -m cli tension_joint_preload \
  --nominal-diameter-in 0.625 \
  --threads-per-inch 11 \
  --thread-series UNC \
  --sae-grade 5 \
  --grip-length-in 1.5 \
  --total-separating-force-kip 36 \
  --desired-load-factor-nL 2 \
  --bolts-reused \
  --extra-threads-beyond-nut 2 \
  --bolt-modulus-material Steel \
  --member-material-astm-number 25 \
  --member-modulus-Mpsi-override 14.0 \
  --eq-8-23-material Steel \
  --show
```

## Example 8-4 Statically Loaded Tension Joint with Preload - cli

```bash
python -m cli tension_joint_preload \
  --nominal-diameter-in 0.625 \
  --threads-per-inch 11 \
  --thread-series UNC \
  --sae-grade 5 \
  --grip-length-in 1.5 \
  --total-separating-force-kip 36 \
  --desired-load-factor-nL 2 \
  --bolts-reused \
  --extra-threads-beyond-nut 2 \
  --bolt-modulus-material Steel \
  --member-material-astm-number 25 \
  --member-modulus-Mpsi-override 14.0 \
  --show
```

## Example 8-4 Statically Loaded Tension Joint with Preload - cli

```bash
python -m cli tension_joint_preload \
  --nominal-diameter-in 0.625 \
  --threads-per-inch 11 \
  --thread-series UNC \
  --sae-grade 5 \
  --grip-length-in 1.5 \
  --total-separating-force-kip 36 \
  --desired-load-factor-nL 2 \
  --bolts-reused \
  --extra-threads-beyond-nut 2 \
  --bolt-modulus-material Steel \
  --member-material-astm-number 25 \
  --member-modulus-Mpsi-override 14.0 \
  --eq-8-23-material "Gray Cast Iron" \
  --show
```

## Example 8-5 Fatigue Loading of Tension Joints - from file

```bash
python -m cli run \
  --infile example_8_5_fatigue_loading_tension_joint.json \
  --outfile example_8_5_fatigue_loading_tension_joint_out.json \
  --pretty \
  --show
```

## Example 8-5 Fatigue Loading of Tension Joints - cli

```bash
python -m cli fatigue_tension_joint \
  --nominal-diameter-in 0.625 \
  --threads-per-inch 11 \
  --thread-series UNC \
  --sae-grade 5 \
  --washer-thickness-in 0.0625 \
  --steel-cover-thickness-in 0.625 \
  --steel-modulus-Mpsi 30 \
  --cast-iron-base-thickness-in 0.625 \
  --cast-iron-modulus-Mpsi 16 \
  --max-force-per-screw-kip 5 \
  --min-force-per-screw-kip 0 \
  --show
```

## Example 8-6 Bolted and Riveted Joints Loaded in Shear - from file

```bash
python -m cli run \
  --infile example_8_6_bolted_shear_joint.json \
  --outfile example_8_6_bolted_shear_joint_out.json \
  --pretty \
  --show
```

## Example 8-6 Bolted and Riveted Joints Loaded in Shear - cli

```bash
python -m cli shear_loaded_joint \
  --nominal-diameter-in 0.75 \
  --threads-per-inch 16 \
  --thread-series UNF \
  --bolt-grade 5 \
  --design-factor-nd 1.5 \
  --member-material-sae-aisi-no 1018 \
  --member-processing CD \
  --member-width-in 4.0 \
  --member-thickness-in 1.0 \
  --splice-plate-thickness-in 0.5 \
  --bolt-count-total 4 \
  --bolts-per-loaded-side 2 \
  --edge-bolt-count 2 \
  --shear-planes-total 4 \
  --hole-diameter-in 0.75 \
  --edge-distance-center-to-edge-in 1.5 \
  --holes-in-critical-section 2 \
  --show
```