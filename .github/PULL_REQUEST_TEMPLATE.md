## Was & Warum
<!-- Kurz: Was ändert dieser PR und warum? Backtest-Zahlen, wenn die Order- oder Risiko-Logik betroffen ist. -->

## Betroffene Dateien
<!-- z. B. gridbot/engine.py — Grid-Abstand, grid_bot.py — Flatten -->

## Risiko-Einschätzung
- [ ] Logik-Änderung (Order, Exit, Grid, Kill-Switch) → Review und Tests zwingend
- [ ] Parameter (Schwellen, Symbole, Hebel, Fees) → trotzdem gegen Mindestabstand und Mindestgröße prüfen
- [ ] Doku / Kommentare

## Tests / Checks
<!-- python3 -m unittest discover -s tests -t . -->
<!-- Fake-Client: Post-only, Größe, Reduce-only-Exit (Hedge: tradeSide=close, One-Way: reduceOnly=YES) -->

## Erwartete Auswirkung
<!-- Paper bleibt der Default. Live nur mit DRY_RUN=False und LIVE_TRADING=True. -->

## Secrets
- [ ] Keine API-Keys, keine Telegram-Tokens, kein config.py
