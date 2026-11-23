# Goat Funded Trader: instalación del EA

> **23 nov 2026: FibFVG_NY10 (vela de las 10am de Nasdaq) está retirado.** Su ventaja en el backtest venía de un error (el breakeven se activaba con el máximo de la vela del llenado, que ocurría antes del llenado). Corregido, pierde en todos los mercados. No lo corras.

| EA | Mercado | Cuándo opera | Riesgo por defecto | Cuenta |
|---|---|---|---|---|
| `mql5/FibFVG_GoldMidnight.mq5` | Oro | Orden a mercado a las 00:00 de Nueva York cuando la tendencia y el día anterior coinciden; se cierra a las 14:00 | 0.9 % (costo del stop de emergencia) | **$50K o más** (en $5K el mínimo de 0.01 lote es demasiado grande) |

El EA está hecho para **Instant Premium**: pérdida máxima trailing intradía del 6 % (deja de subir en el saldo inicial),
pérdida diaria del 3 % desde las 17:00 de Nueva York, límite del 1 % de pérdida flotante para todas las operaciones abiertas, pagos cada 14 días después de
5 días rentables de al menos +0.5 %. El EA:
- opera solo una posición a la vez y nunca la mantiene de noche;
- calcula el tamaño de cada operación para que todos los stops abiertos queden bajo el límite flotante del 1 %, y deja de operar a 1 % de la línea del 6 %;
- cierra sus operaciones si la cuenta queda a menos del 0.5 % de la línea del 6 % o a 2.7 % del límite diario;
- cuenta en su panel tus días rentables desde el último pago (se necesitan 5 por pago);
- escribe cada evento en `MQL5\Files\FibFVG_<EA>_<cuenta>.csv`.

## Antes de comprar

- El EA de oro necesita $10K+ (mínimo de 0.01 lote); se probó con $50K y $100K. Usa solo dinero que no
  necesites para deudas o cuentas; la cuota solo se reembolsa cuando la cuenta paga.
- Los backtests (jul 2024 – nov 2026, datos horarios) son alentadores pero **no están probados** (t de 1.4–1.5).
  Las primeras semanas son una prueba en vivo.
- Pruebas del 23 nov con cuentas pequeñas (ver el Registro del Documento Maestro): por debajo de $5K, usa solo BTC, S&P y Nasdaq.

## Instalación (en tu propia PC con Windows: GFT prohíbe VPS, VPN y proxies)

1. Instala el MT5 de GFT e inicia sesión. No uses una VPN ni un servidor remoto en ningún momento.
2. `Archivo > Abrir carpeta de datos > MQL5 > Experts`: copia `FibFVG_GoldMidnight.mq5` (o `FibFVG_Prop24.mq5` con el preset `presets/GFT_InstantPremium_100K_Prop24.set`).
   `MQL5 > Presets`: copia los archivos de `presets/gft/`.
3. Abre cada `.mq5` en MetaEditor (F4) y presiona **Compilar (F7)**. Envíame una captura si la pestaña Errores muestra algo.
4. `Herramientas > Opciones > Asesores Expertos`: marca *Permitir trading algorítmico*; el botón **Algo Trading** debe estar en verde.
5. Abre un gráfico de **oro H1**, arrastra **FibFVG_GoldMidnight**, *Parámetros > Cargar* `GFT_50K_GoldMidnight.set`
   (o el preset de $100K / plata), Aceptar. El panel debe mostrar el símbolo, la línea de la firma y "waiting for 00:00 New York".
6. Mantén la PC encendida y MetaTrader abierto de 23:30 a 14:30 de Nueva York los días de trading.
7. Guarda este repositorio: GFT puede pedir prueba de que construiste el EA (código fuente y su historial).

## Qué enviar

- Después de cada día o cada semana de trading: una captura del panel y de la pestaña Historial, y el registro CSV.
- Cualquier línea `ERROR` o `HALT` del registro, de inmediato.
