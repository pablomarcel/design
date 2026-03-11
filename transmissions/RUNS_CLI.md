#### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_8hp.json \
  --schedule in/shift_schedule_8hp.json
```

#### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_8hp.json \
  --schedule in/shift_schedule_8hp.json \
  --state 8th \
  --show-speeds
```

#### Solves a transmission spec - shows ratios only

```bash
python -m cli \
  --spec in/transmission_spec_8hp.json \
  --schedule in/shift_schedule_8hp.json \
  --preset legacy \
  --ratios-only
```

#### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_8hp.json \
  --schedule in/shift_schedule_8hp.json \
  --set P4.Ns=23 P4.Nr=85
```

#### List presets

```bash
python -m cli \
  --spec in/transmission_spec_8hp.json \
  --list-presets
```