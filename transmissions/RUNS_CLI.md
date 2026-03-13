#### Ford C4 - 3 Speed Transmission



#### Mercedes Benz W5A-580 - 5 Speed Transmission

### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_w5a_580.json \
  --schedule in/shift_schedule_w5a_580.json
```

### Solves a transmission spec - all states - show speeds

```bash
python -m cli \
  --spec in/transmission_spec_w5a_580.json \
  --schedule in/shift_schedule_w5a_580.json \
  --show-speeds
```

### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_w5a_580.json \
  --schedule in/shift_schedule_w5a_580.json \
  --state 5th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - w5a580_candidate

```bash
python -m cli \
  --spec in/transmission_spec_w5a_580.json \
  --schedule in/shift_schedule_w5a_580.json \
  --preset w5a580_candidate \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_w5a_580.json \
  --schedule in/shift_schedule_w5a_580.json \
  --set PG_forward.Ns=23 PG_forward.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_w5a_580.json \
  --list-presets
```

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
  --state 6th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - allison_1000_candidate

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --preset allison_1000_candidate \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --schedule in/shift_schedule_allison_2k.json \
  --set PG1.Ns=23 PG1.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_allison_2k.json \
  --list-presets
```

#### Mercedes Benz W7A-700 - 7 Speed Transmission

### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_w7a_700.json \
  --schedule in/shift_schedule_w7a_700.json
```

### Solves a transmission spec - all states - show speeds

```bash
python -m cli \
  --spec in/transmission_spec_w7a_700.json \
  --schedule in/shift_schedule_w7a_700.json \
  --show-speeds
```

### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_w7a_700.json \
  --schedule in/shift_schedule_w7a_700.json \
  --state 7th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - w7a700_candidate

```bash
python -m cli \
  --spec in/transmission_spec_w7a_700.json \
  --schedule in/shift_schedule_w7a_700.json \
  --preset w7a700_candidate \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_w7a_700.json \
  --schedule in/shift_schedule_w7a_700.json \
  --set PG_A.Ns=23 PG_A.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_w7a_700.json \
  --list-presets
```

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

### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --schedule in/shift_schedule_w9a_700.json
```

### Solves a transmission spec - all states - show speeds

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --schedule in/shift_schedule_w9a_700.json \
  --show-speeds
```

### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --schedule in/shift_schedule_w9a_700.json \
  --state 8th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - legacy

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --schedule in/shift_schedule_w9a_700.json \
  --preset legacy \
  --ratios-only
```

### Solves a transmission spec - shows ratios only - base

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --schedule in/shift_schedule_w9a_700.json \
  --preset base \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --schedule in/shift_schedule_w9a_700.json \
  --set P4.Ns=23 P4.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_w9a_700.json \
  --list-presets
```

#### Ford 10R80 - 10 Speed Transmission

### Solves a transmission spec - all states

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --schedule in/shift_schedule_ford_10R80.json
```

### Solves a transmission spec - all states - show speeds

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --schedule in/shift_schedule_ford_10R80.json \
  --show-speeds
```

### Solves a transmission spec - 8th gear - shows speeds

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --schedule in/shift_schedule_ford_10R80.json \
  --state 8th \
  --show-speeds
```

### Solves a transmission spec - shows ratios only - legacy

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --schedule in/shift_schedule_ford_10R80.json \
  --preset legacy \
  --ratios-only
```

### Solves a transmission spec - shows ratios only - base

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --schedule in/shift_schedule_ford_10R80.json \
  --preset base \
  --ratios-only
```

### Solves a transmission spec - overrides teeth count

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --schedule in/shift_schedule_ford_10R80.json \
  --set P4.Ns=23 P4.Nr=85
```

### List presets

```bash
python -m cli \
  --spec in/transmission_spec_ford_10R80.json \
  --list-presets
```
