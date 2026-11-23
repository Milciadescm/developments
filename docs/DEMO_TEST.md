# Prueba demo de 4 semanas: Exness (Normal) vs Vantage (Agresivo)

Dos bots corren a la vez en cada cuenta demo, así que los 5 mercados operan juntos:

| Bot | Archivo | Billetera | Mercados | Duración | Normal (Exness) | Agresivo (Vantage) |
|---|---|---|---|---|---|---|
| Prop24 | `mql5/FibFVG_Prop24.mq5` | 1, cuentas de fondeo | BTC, S&P 500, Nasdaq 100 | hasta 24 horas | 0.5 % de $100K por operación | 0.75 % de $100K por operación |
| Hold | `mql5/FibFVG_Hold.mq5` | 2, dinero real de Cueto & Co. | Oro, plata | semanas a un año | 0.5 % de $50K por unidad | 1.0 % de $50K por unidad |

Cada bot lleva su **propia cuenta virtual** (su saldo inicial más solo sus propias operaciones, identificadas por número mágico),
así que los dos bots pueden compartir una cuenta demo sin mezclar resultados. Cada uno escribe su propio archivo de registro.

## 1. Instalación (una vez por broker)

1. **Cuenta demo.** Exness: Área personal > Abrir cuenta nueva > Demo > MT5 Standard. Vantage: Portal de clientes > Cuenta
   demo > MT5. Saldo de **$150,000 o más** (Prop24 opera $100K, Hold opera $50K). Si el broker limita la demo
   a menos, usa el límite: los bots calculan el tamaño con sus propios saldos virtuales y solo comparten el margen. Apalancamiento 1:100 o más.
2. **MetaTrader 5.** Instala el MT5 de cada broker en su **propia carpeta** (dos terminales), para que ambos corran a la vez.
   Inicia sesión con la cuenta demo.
3. **Copia los archivos.** `Archivo > Abrir carpeta de datos`:
   - `MQL5\Experts` ← `FibFVG_Prop24.mq5` y `FibFVG_Hold.mq5`
   - `MQL5\Presets` ← Exness: `Prop24_Normal_Exness.set`, `Hold_Normal_Exness.set`;
     Vantage: `Prop24_Aggressive_Vantage.set`, `Hold_Aggressive_Vantage.set`
4. **Compila.** Abre cada `.mq5` en MetaEditor (F4) y presiona **Compilar (F7)**. Si la pestaña Errores muestra algo,
   envíame una captura antes de seguir.
5. **Observación del mercado.** Clic derecho > *Mostrar todo* (o añade los símbolos): Exness Standard usa `BTCUSDm`, `US500m`,
   `USTECm`, `XAUUSDm`, `XAGUSDm`; Vantage usa `BTCUSD`, `SP500`, `NAS100`, `XAUUSD`, `XAGUSD`.
6. **Trading algorítmico.** `Herramientas > Opciones > Asesores Expertos` > marca *Permitir trading algorítmico*; el botón
   **Algo Trading** de la barra debe estar en verde.
7. **Adjuntar.**
   - Abre un gráfico **BTCUSD H1**, arrastra **FibFVG_Prop24**, *Parámetros > Cargar* el preset de Prop24, Aceptar.
   - Abre un gráfico **XAUUSD H1**, arrastra **FibFVG_Hold**, *Parámetros > Cargar* el preset de Hold, Aceptar.
   - El panel debe listar **3 mercados** (Prop24) y **2 mercados** (Hold). Si falta alguno, escribe los nombres exactos
     de tu broker en `SymbolsToTrade` (p. ej. `BTCUSDm,US500m,USTECm`).
8. `Archivo > Perfiles > Guardar como` "FibFVG demo", y mantén ambos terminales encendidos 24/7 (PC o VPS) durante 4 semanas.

## 2. Qué enviarme

| Cuándo | Enviar |
|---|---|
| Día 0 | Captura del panel de cada bot (4 paneles: 2 bots × 2 brokers) y la pestaña **Expertos** con las líneas `START` |
| Cada viernes después de las 17:00 de Nueva York | Capturas de cada panel, la pestaña **Operaciones** y la pestaña **Historial** (con las columnas Mágico y Comentario); sube los 4 archivos de registro |
| Cada vez que aparezca un error | Captura de las pestañas **Expertos** y **Diario** |

**Archivos de registro:** `Archivo > Abrir carpeta de datos > MQL5 > Files`:
- `FibFVG_Prop24_<cuenta>.csv`
- `FibFVG_Hold_<cuenta>.csv`

Cada fila es un evento: `START`, `ORDER`, `FILL`, `STOP` (stop movido), `EXIT` (con P&L, R y motivo), `CANCEL`,
`SKIP`, `ERROR`, `HALT`, `DAY` (% de aciertos del día, ganancia y pérdida promedio en R, RR), `STOP` (bot quitado).

## 3. Qué revisaré cada semana

1. **Reglas cumplidas:** cada `ORDER` coincide con el gráfico (ruptura de 20 velas, impulso de al menos 1.5 ATR, fair value gap, entrada en
   0.705, stop en el origen del impulso; el stop de Hold 0.25 N más allá).
2. **Tiempos de Prop24:** ninguna operación abierta más de 24 horas; nada abierto después del viernes a las 16:00 de Nueva York.
3. **Tamaño:** `risk_usd` ≈ 0.5 % / 0.75 % de $100K (Prop24) y 0.5 % / 1 % del saldo de Hold por unidad.
4. **Stops:** Hold mueve la primera unidad a breakeven en +1R y luego sigue el mínimo de 120 días; los añadidos se cierran con la
   primera unidad.
5. **Errores:** cada `ERROR` explicado (nombres de símbolos, modo de llenado, mercado cerrado, lote mínimo).
6. **Resultados vs backtest:** % de aciertos, RR y R por operación a partir de las líneas `DAY`.

## 4. Qué esperar en 4 semanas

| | Backtest 2024–2026 | Esperado en 4 semanas |
|---|---|---|
| Prop24 (3 mercados) | 82 operaciones en 34 meses: 58.5 % ganadoras, ganancia prom. +1.20R, pérdida prom. −0.84R, RR 1.42 | unas 2–3 operaciones (0–6 es normal) |
| Hold (oro + plata) | 45 unidades en 29 meses; 2006–2026: cerca de 1 de cada 7 unidades gana, pero las ganadoras promedian ~18× las perdedoras | 0–3 llenados; una posición puede quedar abierta por meses |

Cuatro semanas prueban que los bots **siguen las reglas con datos reales de un broker**. No pueden probar ganancias: con 2–6 operaciones,
domina la suerte. La ganancia se juzga después de 3 meses (Prop24) y 12 meses (Hold).

## 5. Qué puede y qué no puede mostrar la prueba A/B

- **Tamaño:** Normal y Agresivo usan las mismas reglas; solo cambia el tamaño. En R por operación deberían coincidir;
  en dólares el Agresivo debería ser 1.5× (Prop24) y 2× (Hold).
- **Las velas del broker son distintas.** MT5 de Exness funciona en UTC (servidor GMT+0), así que sus velas diarias y de 4 horas coinciden con el
  backtest. Vantage funciona en GMT+2/+3, así que su vela diaria cierra a las 17:00 de Nueva York y sus velas de 4 horas empiezan
  2–3 horas después. Algunas señales aparecerán en un broker y no en el otro. Eso es parte de lo que mide esta prueba:
  qué reloj de velas deben usar los bots en vivo.
- **Precios y spreads:** pequeñas diferencias en llenados y spreads cambian el R un poco.
