# Presets listos para $100K

| Archivo | Plataforma | Uso |
|---|---|---|
| FibFVG_Pro_100K_Normal.set | MT5 / MT4 | $100K estilo Instant Premium (3 % diario, 6 % máx.). Recomendado. |
| FibFVG_Pro_100K_Normal_NoDaily.set | MT5 / MT4 | $100K con pérdida máxima trailing del 6 % y sin límite diario (reglas de FundedNext Stellar Instant). |
| FibFVG_Pro_100K_Aggressive.set | MT5 / MT4 | La misma cuenta, modo Agresivo (pagó menos en el backtest). |
| *.cbotset | cTrader | Los mismos tres, como archivos de parámetros de cBot. Si la importación falla, escribe los valores en el panel de parámetros del cBot. |

Pasos: compila el bot (MetaEditor F7 / cTrader Build) → adjúntalo a UN gráfico (cualquier símbolo) → Parámetros → Cargar el preset → activa el trading algorítmico.
El bot opera XAUUSD, XAGUSD, BTCUSD, US500 y NAS100 desde ese único gráfico y muestra los tamaños de lote, el margen de la protección y el plan de pagos.

Plan de pagos en el panel: la ganancia cerrada del mes se retira al final de cada mes para que la cuenta vuelva a empezar en $100,000.
Mes 1 → cuenta privada del fundador. Meses 2+ se acumulan por trimestre → Cueto & Co → nuevas cuentas de $100K (cuota fijada con AccountFee).
