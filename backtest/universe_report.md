# Universum-Backtest ohne BTC, ETH, BNB

Erzeugt 2026-10-16T09:03:48.560937+00:00. Startkapital 50 USDT, Hebel 2×, Maker 0.02 %, Taker 0.06 %, Slippage auf Notausstiegen 2 bp, Funding-Abschlag 0.01 % je 8h auf die Nettoposition.

Fenster 2026-06-18 bis 2026-10-16. In-Sample bis 2026-09-06 (80 Tage), danach Out-of-Sample. Die Parameterwahl sieht die letzten 40 Tage nicht.

## Auswahlregel

Varianten sind Ein-Faktor-Abweichungen vom Default (6 Levels, Abstand 3× Maker-Round-Trip, ADX 22/25): 4 Levels, 8 Levels, weiter Abstand (4,5×), strenger ADX (18/21), lockerer ADX (28/32).

Pro Coin gewinnt auf dem In-Sample die Variante mit dem höchsten Netto, sofern mindestens 4 Grids liefen und der Drawdown höchstens 15 % war. Sonst bleibt der Default.

Empfohlen wird ein Coin nur, wenn In-Sample und Out-of-Sample nach Fees positiv sind und Out-of-Sample mindestens 2 Grids hatte. Sortierung nach dem schwächeren der beiden Abschnitte, höchstens 8.

Universum: die liquidesten USDT-M-Perps mit 24h-Umsatz ab 1,000,000 USDT, deren Mindestorder bei 2× in 25 USDT Margin passt (ein Level ≤ 25 USDT Notional). BTC, ETH, BNB und Stablecoin-Paare sind draußen. Geprüft: 60 Coins, mit genug Historie: 55.

## Empfehlung für die Config

Der Bot hat einen Parametersatz für alle Symbole. In `config.example.py` stehen deshalb nur Coins, die unter dem Default (6 Levels, Abstand 3×, ADX 22/25) in beiden Abschnitten positiv sind. Per-Coin-Varianten teilt sich der laufende Bot nicht.

| Coin | IS-Netto | OOS-Netto | 120T-Netto | 120T-DD | Grids IS/OOS/120T | Breakouts IS/OOS/120T | PF IS/OOS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOGEUSDT | +0.38 | +0.41 | +0.80 | 1.6 % | 28/7/35 | 7/2/9 | 1.21 / 1.72 |
| SUIUSDT | +0.37 | +0.18 | +0.69 | 2.8 % | 23/3/26 | 10/1/11 | 1.14 / 1.49 |
| SNDKUSDT | +0.71 | +0.13 | +0.84 | 0.3 % | 9/4/13 | 1/0/1 | 7.48 / 6.21 |
| INTCUSDT | +0.07 | +0.14 | +0.21 | 1.7 % | 14/5/19 | 6/2/8 | 1.06 / 1.44 |
| ANTHROPICUSDT | +0.05 | +0.34 | +0.40 | 1.0 % | 7/6/13 | 0/2/2 | 1.21 / 1.57 |

## Per-Coin-Variante, beide Abschnitte positiv

Jede Zeile benutzt die Variante, die auf dem In-Sample am besten war. Das ist nicht die Config des Bots: die Symbole teilen sich dort einen Parametersatz. Wer nur die Out-of-Sample-Gewinner behält, sieht ein schöneres Bild als die In-Sample-Rangliste.

| Coin | Variante | IS-Netto | OOS-Netto | 120T-Netto | OOS-DD | 120T-DD | Grids IS/OOS/120T | Breakouts IS/OOS/120T | PF IS/OOS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOTUSDT | adx_28 | +1.85 | +0.85 | +2.74 | 1.8 % | 2.3 % | 31/6/37 | 11/4/15 | 1.66 / 8.88 |
| SUIUSDT | adx_18 | +0.93 | +0.75 | +1.77 | 0.9 % | 1.9 % | 20/2/22 | 6/0/6 | 1.91 / – |
| DELLUSDT | adx_28 | +0.84 | +0.65 | +1.48 | 0.5 % | 3.2 % | 17/14/31 | 6/2/8 | 1.60 / 3.87 |
| INJUSDT | levels_4 | +0.62 | +1.07 | +1.70 | 1.1 % | 2.8 % | 23/5/28 | 9/1/10 | 1.44 / 6.62 |
| DOGEUSDT | default | +0.38 | +0.41 | +0.80 | 0.9 % | 1.6 % | 28/7/35 | 7/2/9 | 1.21 / 1.72 |
| INTCUSDT | adx_18 | +1.11 | +0.22 | +1.34 | 0.4 % | 0.7 % | 8/4/12 | 2/2/4 | 14.79 / 2.18 |
| UNIUSDT | adx_28 | +0.22 | +0.59 | +0.81 | 1.9 % | 3.2 % | 23/5/28 | 10/3/13 | 1.07 / 2.39 |
| MSTRUSDT | adx_28 | +0.69 | +0.14 | +1.03 | 4.1 % | 5.7 % | 23/19/42 | 10/9/19 | 1.29 / 1.07 |

## Portfolio

### Ehrlich: Default-Parameter, die 8 besten In-Sample-Coins, nur die folgenden 40 Tage, Verlierer bleiben drin

Parametersatz: default. Reihenfolge im einen Grid-Slot: TIAUSDT, SPCXUSDT, LINKUSDT, ARBUSDT, SNDKUSDT, DOGEUSDT, SUIUSDT, ENAUSDT. Netto -1.73 USDT, Max-DD 6.0 %, Grids 21, Breakouts 5, Profit Factor 0.47, Fees 0.40.

### Config-Liste (Default, beide Fenster positiv), nur Out-of-Sample — nach oben verzerrt, Verlierer wurden mit dem OOS-Filter entfernt

Parametersatz: default. Reihenfolge im einen Grid-Slot: DOGEUSDT, SUIUSDT, SNDKUSDT, INTCUSDT, ANTHROPICUSDT. Netto +1.57 USDT, Max-DD 2.5 %, Grids 18, Breakouts 5, Profit Factor 2.18, Fees 0.46.

### Dieselbe Config-Liste über die vollen 120 Tage, ebenfalls mit diesem Filter

Parametersatz: default. Reihenfolge im einen Grid-Slot: DOGEUSDT, SUIUSDT, SNDKUSDT, INTCUSDT, ANTHROPICUSDT. Netto +1.81 USDT, Max-DD 3.4 %, Grids 70, Breakouts 17, Profit Factor 1.30, Fees 1.81.

### Per-Coin-Variante nach In-Sample gewählt, Slot aber mit Default-Parametern, nur Out-of-Sample

Parametersatz: default. Reihenfolge im einen Grid-Slot: TIAUSDT, ADAUSDT, SPCXUSDT, ARBUSDT, DOTUSDT, ENAUSDT, LINKUSDT, WLDUSDT. Netto -0.41 USDT, Max-DD 2.5 %, Grids 16, Breakouts 6, Profit Factor 0.74, Fees 0.39.

### Die 8 Varianten-Überlebenden, Slot mit Default-Parametern, nur Out-of-Sample

Parametersatz: default. Reihenfolge im einen Grid-Slot: DOTUSDT, SUIUSDT, DELLUSDT, INJUSDT, DOGEUSDT, INTCUSDT, UNIUSDT, MSTRUSDT. Netto -1.56 USDT, Max-DD 3.1 %, Grids 31, Breakouts 13, Profit Factor 0.56, Fees 0.61.

### Dieselben 8 Namen, Default-Parameter, volle 120 Tage

Parametersatz: default. Reihenfolge im einen Grid-Slot: DOTUSDT, SUIUSDT, DELLUSDT, INJUSDT, DOGEUSDT, INTCUSDT, UNIUSDT, MSTRUSDT. Netto -0.70 USDT, Max-DD 7.1 %, Grids 100, Breakouts 35, Profit Factor 0.93, Fees 2.28.

Ein Grid zur Zeit, gemeinsames 50-USDT-Kapital, Priorität in der genannten Reihenfolge. Der erste Block wählt die Coins nur nach In-Sample und lässt die Out-of-Sample-Verlierer drin.

## Alle geprüften Coins

Sortiert nach Out-of-Sample-Netto der gewählten Variante. Default-OOS steht daneben, damit sichtbar ist, ob die Variante out-of-sample etwas geändert hat.

| Coin | 24h-Umsatz | Min-Order | Wahl | IS | OOS | Default-OOS | OOS-DD | OOS-Grids | OOS-Breakouts | OOS-PF | Liste |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BTWUSDT | 16M | 5.0 | default | +0.12 | +1.18 | +1.18 | 0.6 % | 1 | 0 | – |  |
| INJUSDT | 18M | 5.0 | levels_4 | +0.62 | +1.07 | +2.85 | 1.1 % | 5 | 1 | 6.62 | Variante |
| PEPEUSDT | 22M | 5.0 | levels_4 | -0.55 | +0.96 | +0.82 | 1.0 % | 13 | 7 | 2.75 |  |
| DOTUSDT | 15M | 5.0 | adx_28 | +1.85 | +0.85 | +0.25 | 1.8 % | 6 | 4 | 8.88 | Variante |
| SUIUSDT | 44M | 5.0 | adx_18 | +0.93 | +0.75 | +0.18 | 0.9 % | 2 | 0 | – | Config |
| DELLUSDT | 11M | 5.0 | adx_28 | +0.84 | +0.65 | -0.30 | 0.5 % | 14 | 2 | 3.87 | Variante |
| SKHYNIXUSDT | 101M | 9.6 | levels_4 | -0.58 | +0.63 | +0.85 | 0.7 % | 11 | 3 | 4.31 |  |
| SIRENUSDT | 41M | 5.0 | default | -0.49 | +0.62 | +0.62 | 1.0 % | 3 | 1 | 7.14 |  |
| UNIUSDT | 18M | 7.5 | adx_28 | +0.22 | +0.59 | +1.47 | 1.9 % | 5 | 3 | 2.39 | Variante |
| KORUUSDT | 279M | 5.0 | adx_28 | -0.47 | +0.47 | -0.05 | 0.6 % | 7 | 1 | 8.35 |  |
| QNTUSDT | 13M | 5.0 | levels_4 | -0.04 | +0.42 | +0.41 | 0.3 % | 5 | 2 | 22.55 |  |
| DOGEUSDT | 45M | 5.0 | default | +0.38 | +0.41 | +0.41 | 0.9 % | 7 | 2 | 1.72 | Config |
| ANTHROPICUSDT | 53M | 19.4 | default | +0.05 | +0.34 | +0.34 | 1.0 % | 6 | 2 | 1.57 | Config |
| RKLBUSDT | 11M | 5.0 | levels_8 | +0.05 | +0.28 | -0.70 | 0.5 % | 12 | 5 | 1.94 |  |
| TSLAUSDT | 42M | 5.0 | adx_18 | -0.18 | +0.23 | +0.32 | 0.2 % | 7 | 0 | 5.35 |  |
| INTCUSDT | 25M | 5.0 | adx_18 | +1.11 | +0.22 | +0.14 | 0.4 % | 4 | 2 | 2.18 | Config |
| XRPUSDT | 176M | 5.0 | levels_4 | -0.27 | +0.15 | +0.16 | 1.9 % | 11 | 3 | 1.19 |  |
| MSTRUSDT | 97M | 5.0 | adx_28 | +0.69 | +0.14 | -0.02 | 4.1 % | 19 | 9 | 1.07 | Variante |
| SNDKUSDT | 260M | 5.0 | default | +0.71 | +0.13 | +0.13 | 0.1 % | 4 | 0 | 6.21 | Config |
| AMDUSDT | 18M | 5.6 | adx_18 | -0.18 | +0.05 | -0.30 | 0.1 % | 1 | 0 | – |  |
| ENAUSDT | 32M | 5.0 | levels_4 | +1.49 | +0.04 | -0.91 | 0.8 % | 4 | 3 | 1.15 |  |
| EWYUSDT | 14M | 5.0 | adx_28 | +0.63 | +0.01 | -0.16 | 1.5 % | 18 | 2 | 1.01 |  |
| NEARUSDT | 142M | 5.3 | levels_4 | -0.46 | +0.00 | +0.00 | 0.0 % | 0 | 0 | – |  |
| NVDAUSDT | 49M | 5.0 | adx_18 | -0.04 | +0.00 | -0.01 | 0.0 % | 1 | 0 | – |  |
| LITEUSDT | 16M | 8.8 | spacing_4_5 | +0.18 | -0.06 | -0.06 | 0.1 % | 7 | 1 | 0.35 |  |
| ADAUSDT | 25M | 5.0 | levels_8 | +2.28 | -0.06 | -0.20 | 3.0 % | 5 | 1 | 0.95 |  |
| AAOIUSDT | 15M | 5.0 | adx_28 | +0.03 | -0.07 | +0.93 | 4.2 % | 14 | 3 | 0.97 |  |
| FILUSDT | 27M | 5.0 | levels_4 | +0.05 | -0.09 | -0.57 | 0.2 % | 5 | 2 | 0.00 |  |
| QQQUSDT | 21M | 7.3 | levels_4 | -0.02 | -0.10 | -0.28 | 0.4 % | 13 | 3 | 0.44 |  |
| MUUUSDT | 11M | 5.0 | levels_8 | -0.19 | -0.11 | -0.24 | 0.2 % | 3 | 1 | 0.11 |  |
| PAXGUSDT | 16M | 5.0 | adx_18 | -0.07 | -0.11 | -0.04 | 0.4 % | 6 | 1 | 0.46 |  |
| SPCXUSDT | 94M | 5.0 | default | +2.16 | -0.12 | -0.12 | 0.3 % | 6 | 0 | 0.00 |  |
| SOLUSDT | 250M | 10.7 | adx_18 | +0.60 | -0.12 | -0.51 | 2.4 % | 7 | 2 | 0.87 |  |
| NBISUSDT | 19M | 5.0 | levels_4 | -0.47 | -0.12 | -0.85 | 0.5 % | 9 | 3 | 0.69 |  |
| ZECUSDT | 204M | 5.0 | levels_4 | -0.34 | -0.16 | +0.66 | 1.8 % | 5 | 4 | 0.83 |  |
| BATUSDT | 15M | 5.0 | adx_18 | -0.11 | -0.17 | -0.34 | 0.4 % | 2 | 0 | 0.00 |  |
| CRCLUSDT | 41M | 5.0 | adx_18 | -0.32 | -0.18 | -0.30 | 0.9 % | 4 | 1 | 0.59 |  |
| OPENAIUSDT | 35M | 5.0 | adx_18 | +0.04 | -0.22 | +0.20 | 0.5 % | 2 | 2 | 0.00 |  |
| CLUSDT | 81M | 5.0 | adx_18 | -0.13 | -0.28 | -1.27 | 0.9 % | 7 | 1 | 0.38 |  |
| WALUSDT | 21M | 5.0 | adx_18 | -0.04 | -0.35 | -0.08 | 1.1 % | 2 | 2 | 0.00 |  |
| SOXSUSDT | 81M | 5.0 | adx_28 | -0.89 | -0.38 | -0.08 | 0.8 % | 3 | 1 | 0.00 |  |
| MUUSDT | 103M | 9.2 | levels_4 | -1.06 | -0.45 | -0.32 | 1.0 % | 10 | 1 | 0.09 |  |
| BZUSDT | 27M | 5.0 | adx_18 | -0.01 | -0.60 | -0.71 | 1.2 % | 10 | 1 | 0.01 |  |
| STRKUSDT | 59M | 5.0 | levels_4 | +0.70 | -0.64 | -0.60 | 1.3 % | 2 | 2 | 0.00 |  |
| SOXLUSDT | 461M | 5.0 | adx_28 | -1.88 | -0.67 | +0.00 | 1.4 % | 4 | 1 | 0.00 |  |
| DRAMUSDT | 30M | 5.0 | levels_4 | -0.79 | -0.70 | -1.28 | 1.5 % | 11 | 4 | 0.17 |  |
| PYTHUSDT | 14M | 5.0 | levels_8 | +0.12 | -1.10 | -1.06 | 3.8 % | 5 | 3 | 0.00 |  |
| ARBUSDT | 12M | 5.0 | levels_4 | +1.90 | -1.21 | -0.61 | 3.1 % | 6 | 4 | 0.00 |  |
| XAGUSDT | 47M | 5.0 | levels_8 | -0.44 | -1.46 | -0.45 | 3.2 % | 16 | 4 | 0.11 |  |
| WLDUSDT | 22M | 5.0 | adx_28 | +1.21 | -1.48 | -0.82 | 3.1 % | 7 | 5 | 0.15 |  |
| ONDOUSDT | 14M | 5.0 | levels_8 | +0.14 | -1.57 | -0.69 | 3.8 % | 9 | 5 | 0.23 |  |
| TIAUSDT | 18M | 5.0 | levels_8 | +3.94 | -1.93 | -0.86 | 4.0 % | 3 | 1 | 0.00 |  |
| HYPEUSDT | 71M | 5.0 | adx_28 | -0.17 | -2.44 | -1.84 | 5.6 % | 14 | 5 | 0.15 |  |
| SAMSUNGUSDT | 24M | 5.0 | adx_28 | -0.31 | -2.55 | -1.72 | 5.2 % | 27 | 10 | 0.16 |  |
| LINKUSDT | 20M | 12.6 | default | +1.39 | -3.76 | -3.76 | 7.5 % | 6 | 3 | 0.00 |  |

## Was das nicht ist

24h-Volumen ist der Stand zum Lauf, nicht das historische Volumen. Neue oder sterbende Coins sind damit falsch gewichtet. Docht-Fills sind für Post-only leicht optimistisch, Notausstiege zahlen Taker plus 2 bp. Funding ist eine Pauschale. Wer auf dem Out-of-Sample die Verlierer streichen darf, sieht ein schöneres Portfolio als der, der die Liste vorher festnageln muss.

Zu wenig Historie und deshalb nicht gewertet: SKHYUSDT, SNXXUSDT, AKEUSDT, MINIMAXUSDT, ZHIPUUSDT.
