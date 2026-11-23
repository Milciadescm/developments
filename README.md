# FibFVG Pro

Bot de trading para XAUUSD, XAGUSD, BTCUSD, US500 y NAS100 en cuentas de fondeo instantáneas (sin objetivo de ganancia,
sin regla de consistencia, pérdida máxima del 6 %). Solo se mantienen los planes que ganaron dinero con datos de 2024 → hoy.

> Estado actual (23 nov 2026): las reglas vigentes están en el Documento Maestro
> (https://claude.ai/artifact/6ugpp8DiUYF5Np6ESd1KeL) y en `CLAUDE.md`. Este README describe la versión original FibFVG_Pro.

| Plan | Qué hace | 2024 → hoy (R neto por operación, después del spread) |
|---|---|---|
| Plan 1 Posición | Sesgo mensual + semanal, impulso de ruptura Turtle en diario con un fair value gap, orden límite en el OTE Fibonacci 0.705, añadidos Turtle, salida chandelier, breakeven en +1R, stop por tiempo de 10 días | +0.82R · 52 % ganadoras · R:R realizado 3.3 |
| Plan 3 Niveles | Sesgo semanal, reacción en 1H en los niveles 00/20/50/60/80 (sin el almuerzo de NY), stop = 1 ATR diario, breakeven en +1R, trailing del mínimo de 5 días desde +2R, añadidos solo mientras la primera unidad esté en ≥ +1R | +0.16R · 28 % ganadoras · R:R realizado 3.4 |
| Plan 3B Niveles · banco 2R (por defecto) | Plan 3 más cierre de la mitad de cada unidad en +2R | +0.11R · 32 % ganadoras · R:R realizado 2.6, pagos más tempranos |

Cartera por defecto: **Core + banco 2R** (Plan 1 + Plan 3B) en modo **Normal**.
Instant Premium $100K, jul 2024 → hoy: $24,501 pagados al trader, 14 pagos, peor caída 4.65 %, sin incumplimiento.
Hoja de ruta de 12 meses desde 16 meses de inicio: primer pago en menos de 90 días en el 69 % de los inicios, neto mediano $15,809 (peor +$3,827).

## Archivos

```
fibfvg/edgebook.py   todos los resultados (planes, pips, puntos débiles, fondeo, hoja de ruta)  -> results/edge_book.json, trades_*.csv
fibfvg/playbook.py   construye results/playbook.html a partir de esos resultados
fibfvg/plans.py      motor del Plan 1        fibfvg/levels.py   motor del Plan 3 / 3B
fibfvg/propsim.py    simulador de cuentas de fondeo (protección, pagos, compuerta de ventaja)
fibfvg/roadmap.py    hoja de ruta de pagos a 12 meses    fibfvg/calendar.py  fechas de CPI / NFP / FOMC
mql5/FibFVG_Pro.mq5  mql4/FibFVG_Pro.mq4  ctrader/FibFVGPro.cs   los bots (ver INSTALL.md)
data/                velas diarias (2024+) y horarias de Yahoo Finance usadas por los planes
```

Reconstruir todo: `pip install pandas numpy yfinance && python -m fibfvg.edgebook && python -m fibfvg.playbook`.
Las ideas rechazadas y sus números están en `RESEARCH_LOG.md`.

## Límites

- El historial horario de Yahoo empieza en julio 2024 (BTC en noviembre 2024). Oro/plata usan precios de futuros; los índices usan contado (diario) y futuros (horario).
- Los tamaños de contrato y spreads en `fibfvg/config.py` son valores típicos de CFD en MT5; los bots leen los valores reales del broker.
- Ninguno de los bots se ha compilado aquí (no hay MetaEditor ni cTrader en este entorno). Compílalos y córrelos primero en demo.
- Julio 2024 → hoy fue una tendencia fuerte para el oro y la plata; con historia más larga se ganó menos por año.
