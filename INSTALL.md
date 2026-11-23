# FibFVG Pro: instalar y correr

Un bot, tres plataformas, las mismas reglas. Ponlo en **un solo gráfico cualquiera**. Encuentra los nombres que usa tu broker para
oro, plata, BTC, US500 y NAS100 (GOLD, XAUUSD.r, USTEC, US100.cash, etc.) y los opera todos desde ese gráfico.

| Plataforma | Archivo | Instalación |
|---|---|---|
| MetaTrader 5 | `mql5/FibFVG_Pro.mq5` | Archivo → Abrir carpeta de datos → `MQL5/Experts` → pegar → abrir en MetaEditor → Compilar (F7) → arrastrar a un gráfico → marcar "Permitir trading algorítmico" |
| MetaTrader 4 | `mql4/FibFVG_Pro.mq4` | Igual, en `MQL4/Experts`; activar "Permitir trading en vivo" |
| cTrader | `ctrader/FibFVGPro.cs` | Automate → New cBot → pegar → Build → añadir una instancia a un gráfico → Start |

Ninguno de los tres archivos se ha compilado todavía. Corrige cualquier mensaje de compilación y córrelo primero en demo.

## Ajustes importantes

| Ajuste | Por defecto | Opciones |
|---|---|---|
| Preset | FundedNext Stellar Instant | FundedNext Stellar Instant (6 % trailing, sin diario), Instant Premium (3 % diario, 6 % máx.), Personal, Custom |
| RiskMode | Normal | Conservador 0.15 % / 0.05 % · Normal 0.25 % / 0.10 % · Agresivo 0.50 % / 0.25 % · Compuerta de ventaja |
| Plan1Exit | Chandelier | Chandelier para cuentas de fondeo, Mensual para dinero personal |
| Plan3Bank2R | true | cerrar la mitad de cada unidad de niveles en +2R (Plan 3B, el plan por defecto) |
| KillZonesOnly | false | true limita las entradas a las 20, 00, 02, 06, 07, 09, 10, 15 NY (probado: menos operaciones, sin ganancia extra) |
| StartBalance | 0 (auto) | ponlo en el tamaño inicial de la cuenta en una cuenta fondeada |

El riesgo es una parte del **saldo inicial** por unidad (Plan 1 / Plan 3).

## Qué protege la cuenta

- Antes de cada operación: la caída desde el máximo + el riesgo de los stops abiertos + el riesgo de la nueva operación deben quedar bajo el límite de la firma menos 1 %
  (5 % de un límite del 6 %) y bajo el límite diario menos 0.5 %. Cerca de la línea, las operaciones se reducen a la mitad del margen que queda.
- Línea de emergencia: si el equity queda a menos del 0.5 % de la línea de pérdida máxima de la firma, cierra todo y detiene el bot (hay que reiniciarlo);
  a menos del 0.3 % de la línea diaria, cierra todo hasta el día siguiente.
- El estado (saldo inicial, máximo, estado del TP1 del Plan 1, añadidos) se guarda en variables globales del terminal / LocalStorage de cTrader, así que los reinicios son seguros.
- Los lotes por debajo del mínimo del broker se saltan, nunca se redondean hacia arriba.

El panel del gráfico muestra el modo, el margen que queda antes de la línea del bot y los lotes por mercado (recomendados y abiertos).

## La regla de ventaja (RiskMode = Compuerta de ventaja)

```
EDGE_CONFIRMED -> Normal     : últimas 20 posiciones cerradas  suma >= +3R  y PF >= 1.3  y caída <= 2 %
STRONG_EDGE    -> Agresivo   : últimas 40 posiciones cerradas  suma >= +8R  y PF >= 1.5  y caída <= 1.5 %
en otro caso (o caída >= 3 %) -> Conservador
```

## Pagos y la hoja de ruta de 12 meses

1. Mes 1: pide un primer pago pequeño (hasta $1,000 de ganancia cerrada) si la hay. Esto pasó en cerca de 1 de cada 5 meses de inicio. Lo normal es en los meses 2–3.
2. Mes 3: retira toda la ganancia cerrada y compra con ella más de las cuentas instantáneas más grandes. El retiro mediano del mes 3 fue de unos $444, así que normalmente 0–1 cuentas.
3. Meses 4–8: pagos mensuales, entre el mínimo y el máximo de la firma por pago.
4. Mes 9: retira todo de cada cuenta y compra tantas cuentas como alcance. Repetir durante 2027.
5. Pide solo el monto "retirable ahora" que muestra el panel. El bot ve el retiro y reinicia su máximo.
6. Nunca subas el modo de riesgo para alcanzar un pago. Revisa la asignación máxima de cada firma y sus reglas sobre correr el mismo bot en varias cuentas.
   Lucid Trading es una firma de futuros (futuros CME en NinjaTrader/Tradovate/Rithmic): este bot necesita una versión para futuros antes de poder correr allí.
