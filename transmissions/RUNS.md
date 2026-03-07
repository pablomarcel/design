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
