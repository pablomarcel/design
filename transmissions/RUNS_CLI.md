#### Ford C4 - 3 Speed Transmission



#### Mercedes Benz W5A-580 - 5 Speed Transmission



#### Allison 2000 Series - 6 Speed Transmission

### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json
```

### Solves a transmission spec - all states - show speeds

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --show-speeds
```

### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --state 8th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - legacy

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --preset legacy \
  --ratios-only
```

### Solves a transmission spec - shows ratios only - base

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --preset base \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --set P4.Ns=23 P4.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --list-presets
```

#### Mercedes Benz W7A-700 - 7 Speed Transmission



#### ZF 8HP - 8 Speed Transmission

### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --schedule in/shift_schedule_zf_8hp.json
```

### Solves a transmission spec - all states - show speeds

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --schedule in/shift_schedule_zf_8hp.json \
  --show-speeds
```

### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --schedule in/shift_schedule_zf_8hp.json \
  --state 8th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - legacy

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --schedule in/shift_schedule_zf_8hp.json \
  --preset legacy \
  --ratios-only
```

### Solves a transmission spec - shows ratios only - base

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --schedule in/shift_schedule_zf_8hp.json \
  --preset base \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --schedule in/shift_schedule_zf_8hp.json \
  --set P4.Ns=23 P4.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_zf_8hp.json \
  --list-presets
```

#### Mercedes Benz W9A-700 - 9 Speed Transmission



#### Ford 10R80 - 10 Speed Transmission


