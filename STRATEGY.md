# Strategie

Grid nur dann, wenn der Markt seitwärts läuft. Jede Order, die das Grid aufmacht oder ein Los mit Gewinn schließt, ist Post-only. Der Notausstieg darf Taker sein, weil eine hängende Lage im Ausbruch teurer ist als die Taker-Fee.

## Warum nicht V2

Subaccount `at-HNKHNK`, 792 geschlossene Trades vom 05.07.2026 bis 20.09.2026, durchweg Isolated:

| | USDT |
| --- | ---: |
| Brutto-PnL | −31,00 |
| Fees | −32,89 |
| Funding | +0,78 |
| Netto | −63,11 |

739 Shorts, 53 Longs. Symbole vor allem ETH, BTC, SOL, etwas XRP. Die Fee je Round-Trip, geteilt durch Entry- plus Exit-Notional, lag im Median bei etwa 0,04 % **pro Seite** — zwischen Maker 0,02 % und Taker 0,06 %, näher am Taker. Bei rund 800 Round-Trips haben die Fees mehr gekostet als der Markt hergegeben hat.

Dieser Bot handelt deshalb selten, nur in einer erkannten Range, und kassiert auf dem normalen Weg die Maker-Fee. Der Mindestabstand zweier Levels ist das Dreifache der Maker-Round-Trip-Fee: 2 × 0,02 % × 3 = **0,12 %**. Ein voller Umlauf (Kauf und Verkauf als Maker) kostet 0,04 % und lässt bei genau 0,12 % Abstand rechnerisch 0,08 % vor Funding und vor dem Notausstieg übrig. Enger wird nicht gehandelt.

## Regime

Kein Grid, solange eine Bedingung fehlt. Geschlossene Kerzen, kein Blick in die Zukunft.

| Filter | Default | Bedeutung |
| --- | --- | --- |
| ADX(14) 1h | unter 22 | kein gerichteter 1h-Trend |
| ADX(14) 4h | unter 25 | der höhere Zeitrahmen ist nicht trendig |
| Efficiency Ratio, 24×1h | unter 0,35 | der Pfad ist verschlungen, nicht eine Gerade |
| Bollinger-Breite(20, 2) **oder** ATR(14)/Preis | unter 6 % bzw. unter 1,5 % | Volatilität ist komprimiert, eine der beiden reicht |
| Mittelkreuzungen im 48h-Fenster | mindestens 3 | beide Seiten der Range wurden gehandelt |

Eine glatte Sinuswelle kann den ADX hochziehen, obwohl sie optisch „seitwärts“ aussieht. Der Filter will Gehacker, nicht die erste Hälfte eines Schwungs. Im Backtest blockiert vor allem der ADX.

## Grid

Die Grenzen sind das Tief und das Hoch der letzten 48 Stundenkerzen. Der letzte Schluss muss im mittleren 70 % dieser Spanne liegen (`EDGE_INSET` 0,15). Die Spanne selbst muss zwischen 0,8 % und 8 % des Mittelpreises liegen.

Daraus werden bis zu 6 Levels. Die Zahl sinkt, bis jedes Intervall mindestens 0,12 % weit ist. Unter 3 Levels wird abgelehnt.

Die Stückzahl je Level zielt auf 20 % des Kapitals als Notional, wird aber auf die Börsenmindestgröße angehoben und auf den Step abgerundet. Budget ist 50 % des Kapitals als Margin bei dem Symbol-Hebel. Zwei Orders (eine unter dem Preis, eine darüber) müssen in dieses Budget passen, sonst gibt es kein Grid.

Unter dem Preis liegen Post-only-Buys (Long öffnen), darüber Post-only-Sells (Short öffnen), höchstens 3 offene Lose je Seite inklusive schon liegender Einstiege. Ein Long-Fill bekommt einen Post-only-Sell eine Stufe höher (`tradeSide=close` im Hedge). Ein Short-Fill bekommt den Buy eine Stufe tiefer. Reduce-only im One-Way-Modus ist `reduceOnly=YES` und die Orderbuch-Seite, ohne `tradeSide`.

## Schutz

| Ereignis | Reaktion |
| --- | --- |
| Stunden-Schluss jenseits der Range plus 0,25 % | Alles stornieren, Lage schließen |
| Regime nicht mehr seitwärts | dasselbe |
| Grid-Netto ≤ −6 % des Kapitals beim Start | dasselbe |
| UTC-Tagesverlust ≥ 5 % vom Tagesstart | schließen, an diesem Tag nichts Neues |
| Datei `KILL_SWITCH` oder Config | schließen, bis der Schalter weg ist |

Nach einem Ausstieg 6 Stunden Pause auf dem Symbol. Im Live-Betrieb wird der Close zuerst als Post-only versucht (20 Sekunden), der Rest geht als Market-IOC. Der Backtest bucht den Notausstieg sofort als Taker (0,06 %) plus 2 bp Slippage. Zusätzlich ein pauschales Funding von 0,01 % je 8 Stunden auf den Betrag der Nettoposition — das sind nicht die historischen Funding-Raten, sondern ein Abschlag.

Live versucht außerdem einen Börsen-Stop auf der ganzen Long- bzw. Short-Lage an der Range-Grenze. Das ist ein Zusatz, kein Ersatz für einen laufenden Prozess.

## Parameter (Defaults)

Hebel 2, Deckel 3, Isolated, Hedge. Ein Grid zur Zeit. Paper-Kapital, wenn kein Kontostand lesbar ist: 50 USDT. Loop 20 Sekunden. Symbole BTCUSDT, ETHUSDT, BNBUSDT.

Die vollständige Liste steht in `config.example.py`. Fehlende Felder in einem eingeworfenen V2-`config.py` fallen auf diese Defaults zurück. Der Hebel wird gekappt, auch wenn dort 5 steht.

## Backtest

`python3 backtest.py --days 120 --equity 50` auf öffentlichen Bitget-1h-Kerzen, 18.06.2026 bis 16.10.2026, 2865 Stunden, jedes Symbol mit eigenen 50 USDT und dasselbe noch einmal als Portfolio mit einem Grid zur Zeit. Report: `backtest/latest_report.json`.

Gebühren: Maker 0,02 %, Taker 0,06 % nur auf Notausstiegen, Funding-Abschlag 0,01 % / 8h. Dieselbe Engine wie Paper und Live.

| | Ende | Netto | Realisiert | Fees (Maker/Taker) | Funding | Max. DD | Grids | Round-Trips | Ausstiege |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| BTCUSDT | 49,36 | −0,64 | +0,02 | 0,62 (0,32/0,30) | 0,03 | 1,68 % | 35 | 72 | 24 Regime, 11 Breakouts |
| ETHUSDT | 49,79 | −0,21 | +0,30 | 0,42 (0,22/0,20) | 0,09 | 3,56 % | 22 | 19 | 18 Regime, 4 Breakouts |
| BNBUSDT | 50,60 | +0,60 | +1,33 | 0,70 (0,37/0,33) | 0,04 | 1,38 % | 39 | 101 | 30 Regime, 9 Breakouts |
| Portfolio | 49,45 | −0,55 | +0,81 | 1,28 (0,66/0,61) | 0,08 | 2,22 % | 72 | 136 | 52 Regime, 20 Breakouts |

Alle 136 Portfolio-Round-Trips sind positiv. Das ist keine Trefferquote, sondern die Konstruktion: ein abgeschlossener Umlauf verkauft eine Stufe über dem Kauf (oder kauft eine Stufe unter dem Short). Der Verlust sitzt in den Notausstiegen. Im Portfolio ist das realisierte Handelsergebnis +0,81 USDT, die Fees sind 1,28 USDT. Die Kosten sind größer als der Roh-Edge. Ohne den Funding-Abschlag bleibt das Portfolio bei etwa −0,46 USDT.

BNB ist im Fenster das einzige positive Symbol (+0,60 USDT, rund +1,2 % in vier Monaten). Das ist eine Stichprobe, kein Grund, die anderen Symbole aus der Liste zu streichen. BTC ist nach Fees negativ, obwohl fast jeder Umlauf gewonnen hat: 0,62 USDT Fees bei 0,02 USDT realisiertem Preis-PnL.

ETH wird oft gar nicht erst aufgemacht. Mindestgröße 0,01 ETH. Am Ende des Fensters lag ETH bei etwa 2454 USDT, also rund 24,5 USDT Notional und 12,3 USDT Margin bei 2×. Zwei solche Orders brauchen ~24,5 USDT Margin, das Budget bei 50 USDT Kapital und 50 % Einsatz sind 25 USDT. Knapp, und in teureren Stunden abgelehnt (188 Stunden `unter_mindestgroesse`). Der Bot geht dann nicht auf eine kleinere Stückzahl herunter.

Der Filter ist eng. Von den Stunden scheitern die meisten am ADX. Gestartet wurde im Portfolio 72-mal.

### Was der Backtest nicht ist

- Fill, sobald der Docht das Limit berührt. Das ist für Post-only leicht optimistisch.
- Innerhalb einer Breakout-Kerze werden keine Take-Profits gutgeschrieben, wohl aber berührte Einstiege. Das ist absichtlich streng.
- Kein Orderbuch, keine Teilausführung, keine API-Fehler, keine Warteschlange.
- Notausstieg zum Schlusskurs plus 2 bp, nicht zum echten Slippage-Pfad.
- Funding ist eine Pauschale, kein historischer Satz.
- Ein Fenster, drei große Symbole, 50 USDT. Kein Beweis für die nächsten vier Monate.
- Der Drawdown bleibt klein, weil die Stückzahl klein ist und der Stop greift. Klein heißt hier nicht „ohne Verlust“.

Gegen die V2-Historie ist das ein anderes Profil: wenige Grids statt hunderter Taker-Scalps, und ein Verlust in der Größenordnung von einem USDT statt rund 63 USDT. Es ist trotzdem kein nachgewiesener Vorteil nach Fees.

## Betrieb

Paper ist der Default. Live ist in [README.md](README.md) und [TRADING_RULES.md](TRADING_RULES.md) beschrieben. Wer live geht, tut das mit dem Wissen, dass dieser Backtest nach Kosten negativ ist, und mit einem Konto, das die Mindestgrößen tragen kann.
