#### Simpson Transmission

```bash
python -m kinematics.simpson_ratio_map \
  --sun-min 20 \
  --sun-max 40 \
  --ring-min 50 \
  --ring-max 90
```

```bash
python -m kinematics.simpson_ratio_map \
  --sun-min 20 \
  --sun-max 40 \
  --ring-min 50 \
  --ring-max 90 \
  --log-level INFO
```

```bash
python -m kinematics.simpson_ratio_map \
  --sun-min 20 \
  --sun-max 40 \
  --ring-min 50 \
  --ring-max 90 \
  --validate-with-solver \
  --log-level INFO
```

```bash
python -m kinematics.simpson_ratio_map \
  --sun-min 20 \
  --sun-max 40 \
  --ring-min 50 \
  --ring-max 90 \
  --no-progress \
  --log-level INFO
```

```bash
python -m kinematics.simpson_ratio_map \
  --log-level INFO
```

```bash
python -m kinematics.simpson_ratio_map \
  --no-progress \
  --log-level INFO
```

#### Ravigneaux Transmission

```bash
python -m kinematics.ravigneaux_ratio_map \
  --sun-min 20 \
  --sun-max 40 \
  --ring-min 50 \
  --ring-max 90 \
  --log-level INFO \
  --print-audit
```

```bash
python -m kinematics.ravigneaux_ratio_map \
  --sun-min 20 \
  --sun-max 40 \
  --ring-min 50 \
  --ring-max 90 \
  --log-level INFO \
  --validate-with-solver \
  --print-audit
```

#### Ford C4 3 Speed Transmission

```bash
python -m transmissions.three_speed \
  --state all \
  --Ns 33 \
  --Nr 72
```

```bash
python -m transmissions.three_speed \
  --state all \
  --Ns-front 34 \
  --Nr-front 72 \
  --Ns-rear 36 \
  --Nr-rear 74
```

```bash
python -m transmissions.three_speed \
  --state all
```

```bash
python -m transmissions.three_speed \
  --state 3rd
```

```bash
python -m transmissions.three_speed \
  --state rev \
  --json
```

```bash
python -m transmissions.three_speed \
  --state all \
  --ratios-only
```

```bash
python -m transmissions.three_speed \
  --list-presets
```

```bash
python -m transmissions.three_speed \
  --state all \
  --preset ford_c4_reference
```

#### Ravineaux 4 Speed Transmission

```bash
python -m transmissions.four_speed \
  --state all
```

```bash
python -m transmissions.four_speed \
  --state 4th
```

```bash
python -m transmissions.four_speed \
  --state all --json
```

```bash
python -m transmissions.four_speed --state all \
  --ratios-only
```

```bash
python -m transmissions.four_speed \
  --list-presets
```

#### W5A-580 5 Speed Transmission

```bash
python -m transmissions.five_speed \
  --state all
```

```bash
python -m transmissions.five_speed \
  --state all \
  --ratios-only
```

```bash
python -m transmissions.five_speed \
  --Ns-f 46 --Nr-f 72 \
  --Ns-r 68 --Nr-r 122 \
  --Ns-m 37 --Nr-m 91
```

#### Allison 6 Speed Transmission

```bash
python -m transmissions.six_speed \
  --state all
```

```bash
python -m transmissions.six_speed \
  --state 4th
```

```bash
python -m transmissions.six_speed \
  --state all \
  --json
```

# Allison 4000

```bash
python -m transmissions.six_speed \
  --state all \
  --Ns1 73 \
  --Nr1 125 \
  --Ns2 43 \
  --Nr2 109 \
  --Ns3 39 \
  --Nr3 101
```

# Allison 3000

```bash
python -m transmissions.six_speed \
  --state all \
  --Ns1 67 \
  --Nr1 109 \
  --Ns2 49 \
  --Nr2 91 \
  --Ns3 39 \
  --Nr3 97
```

# Allison 2000

```bash
python -m transmissions.six_speed \
  --state all \
  --Ns1 67 \
  --Nr1 109 \
  --Ns2 49 \
  --Nr2 91 \
  --Ns3 39 \
  --Nr3 97
```

# Allison 1000

```bash
python -m transmissions.six_speed \
  --state all \
  --Ns1 61 \
  --Nr1 111 \
  --Ns2 57 \
  --Nr2 111 \
  --Ns3 49 \
  --Nr3 103
```

# Allison Bad Combination of Teeth Numbers

```bash
python -m transmissions.six_speed \
  --state all \
  --Ns1 61 \
  --Nr1 100 \
  --Ns2 41 \
  --Nr2 79 \
  --Ns3 41 \
  --Nr3 79
```

```bash
python -m transmissions.six_speed \
  --state all \
  --ratios-only
```

```bash
python -m transmissions.six_speed \
  --list-presets
```

```bash
python -m transmissions.six_speed \
  --state all \
  --preset allison_4000
```

```bash
python -m transmissions.six_speed \
  --state all \
  --preset allison_3000
```

```bash
python -m transmissions.six_speed \
  --state all \
  --preset allison_2000
```

```bash
python -m transmissions.six_speed \
  --state all \
  --preset allison_1000
```

#### W7A-700 7 Speed Transmission

```bash
python -m transmissions.seven_speed \
  --state all
```

```bash
python -m transmissions.seven_speed \
  --state all \
  --ratios-only
```

```bash
python -m transmissions.seven_speed \
  --Ns-a 52 --Nr-a 106 \
  --Ns-b 78 --Nr-b 100 \
  --Ns-r 66 --Nr-r 164 \
  --Ns-m 62 --Nr-m 168
```

#### ZF8HP 8 Speed Transmission

```bash
python -m transmissions.eight_speed \
  --state all
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --ratios-only
```

# Override tooth counts manually - 4th Generation

```bash
python -m transmissions.eight_speed \
  --state all \
  --Ns1 48 --Nr1 96 \
  --Ns2 54 --Nr2 96 \
  --Ns3 60 --Nr3 108 \
  --Ns4 24 --Nr4 96
```

# Override tooth counts manually - 3rd Generation

```bash
python -m transmissions.eight_speed \
  --state all \
  --Ns1 48 --Nr1 96 \
  --Ns2 54 --Nr2 96 \
  --Ns3 60 --Nr3 96 \
  --Ns4 24 --Nr4 102
```

# Override tooth counts manually - 2nd Generation

```bash
python -m transmissions.eight_speed \
  --state all \
  --Ns1 48 --Nr1 96 \
  --Ns2 48 --Nr2 96 \
  --Ns3 60 --Nr3 96 \
  --Ns4 28 --Nr4 104
```

# Single-state with manual counts

```bash
python -m transmissions.eight_speed \
  --state 1st \
  --Ns1 48 --Nr1 96 \
  --Ns2 48 --Nr2 96 \
  --Ns3 38 --Nr3 96 \
  --Ns4 23 --Nr4 85
```

```bash
python -m transmissions.eight_speed \
  --state 1st
```

```bash
python -m transmissions.eight_speed \
  --state 6th
```

```bash
python -m transmissions.eight_speed \
  --state rev
```

```bash
python -m transmissions.eight_speed \
  --state reverse
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --json
```

```bash
python -m transmissions.eight_speed \
  --state 4th \
  --json
```

```bash
python -m transmissions.eight_speed \
  --state 8th \
  --ratios-only
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --show-topology
```

```bash
python -m transmissions.eight_speed \
  --list-presets
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp51_gen3
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp50_gen2_candidate
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp45_gen1_candidate
```

# Preset plus manual override

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp51_gen3 \
  --Ns4 24 --Nr4 85
```

# Strict / relaxed geometry

```bash
python -m transmissions.eight_speed \
  --state all \
  --strict-geometry
```

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp51_gen3 \
  --strict-geometry
```

# All gears, JSON, preset

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp51_gen3 \
  --json
```

# All gears, ratios only, manual tooth counts

```bash
python -m transmissions.eight_speed \
  --state all \
  --ratios-only \
  --Ns1 48 --Nr1 96 \
  --Ns2 48 --Nr2 96 \
  --Ns3 38 --Nr3 96 \
  --Ns4 23 --Nr4 85
```

# Show topology with preset

```bash
python -m transmissions.eight_speed \
  --state all \
  --preset zf_8hp45_reference_legacy \
  --show-topology
```

#### Mercedes 9G-tronic 9 Speed Transmission

# All states

```bash
python -m transmissions.nine_speed \
  --state all
```
# Ratios only

```bash
python -m transmissions.nine_speed \
  --state all \
  --ratios-only
```

# Show speeds

```bash
python -m transmissions.nine_speed \
  --state all \
  --show-speeds
```

# 9G-tronic preset

```bash
python -m transmissions.nine_speed \
  --preset mb_9gtronic_2016
```

# Override tooth counts manually

```bash
python -m transmissions.nine_speed \
  --state all \
  --S1 46 --R1 98 \
  --S2 44 --R2 100 \
  --S3 36 --R3 84 \
  --S4 34 --R4 86
```

#### Ford 10R80 10 Speed Transmission

```bash
python -m transmissions.ten_speed \
  --state all
```
# Override tooth counts manually

```bash
python -m transmissions.ten_speed \
  --state all \
  --Ns1 45 --Nr1 99 \
  --Ns2 51 --Nr2 89 \
  --Ns3 63 --Nr3 101 \
  --Ns4 23 --Nr4 85
```
