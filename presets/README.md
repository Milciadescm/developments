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

## V2 (26 nov 2026) — `mql5/FibFVG_Prop24_V2.mq5` + `presets/v2/`
El mismo bot de 24 horas con dos cambios: entradas solo de 08:00 a 18:00 hora de Nueva York (pasó los 4 controles) y un freno
opcional para cuentas reales (mitad del riesgo tras 2 pérdidas seguidas; riesgo mínimo si el saldo cae 20 % desde su máximo).

| Preset | Cartera | Riesgo | Freno |
|---|---|---|---|
| `GFT_100K_Prop24_V2.set` | Cueto & Co. Prop (GFT $100K) | 0.9 % fijo | no |
| `Real_Prop24_V2_5pct_freno.set` | Cueto & Co. Real (recomendado) | 5 % del saldo actual | sí, 1 % en caída de 20 % |
| `Real_Prop24_V2_10pct_freno.set` | Cueto & Co. Real (agresivo) | 10 % del saldo actual | sí, 2 % en caída de 20 % |

Instalación: copiar `FibFVG_Prop24_V2.mq5` a `MQL5\Experts`, compilar con F7, copiar los `.set` a `MQL5\Presets`, quitar el V1 del
gráfico y arrastrar el V2 (un solo bot de 24 horas por cuenta). En Expertos, la línea START debe decir `version=2`.
