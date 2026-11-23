# FibFVG Pro v3 — README del bot e instalación en MT5 (PC con Windows encendida 24/7)

## Qué hace el bot, en un párrafo

FibFVG Pro opera oro (XAUUSD), plata (XAGUSD), Bitcoin (BTCUSD), S&P 500 (US500) y Nasdaq 100 (NAS100)
desde **un solo gráfico**. Solo opera en la dirección de la tendencia mensual y semanal. Cuando el precio rompe el
máximo (o mínimo) de 20 días con un fair value gap, coloca una orden límite en el **nivel Fibonacci 0.705** de ese
movimiento (la zona OTE), con el stop justo más allá del inicio del movimiento. Las ganadoras se mantienen días o semanas: el
stop pasa a breakeven en +1R y luego sigue a 3 rangos diarios del mejor precio. Las perdedoras se cortan a los 10
días si nunca llegaron a +0.5R. Mientras una operación funciona, añade hasta 3 unidades más (reglas Turtle).
Una protección mantiene la caída más el riesgo abierto bajo el 5 %, para que la cuenta nunca toque la línea del 6 % de la firma.

## Mejores reglas para una cuenta de $100K (v3, archivo `presets/FibFVG_Pro_100K_Best.set`)

| Ajuste | Valor | Por qué |
|---|---|---|
| Plan de posiciones (Plan 1) | ENCENDIDO | +0.71R por operación después de swaps, probado (t = 4.0) |
| Plan de niveles (Plan 3) | APAGADO | Después de swaps solo +0.06R y más caída |
| Riesgo por unidad | 0.5 % de $100,000 = $500 | El mejor pago con la peor caída bajo el 5 % en el backtest |
| Salida | Chandelier (3 rangos diarios), breakeven en +1R, stop por tiempo de 10 días | Deja correr las ganadoras, corta las operaciones muertas |
| Protección | 5 % (línea de la firma 6 %), reduce operaciones cerca de la línea | Sin incumplimiento en ninguna prueba |
| Solo day trading | NO se usa | Todas las versiones solo intradía perdieron dinero (−0.02R a −0.31R por operación) |

Backtest, julio 2024 → noviembre 2026, con swaps: **$23,541 pagados** en una cuenta de $100K, peor caída
bajo el 5 %, unas 4 operaciones al mes entre 5 mercados, mediana $13,900 pagados por 12 meses; 1 de 16 meses de inicio pagó
$0 en su primer año. Son simulaciones, no resultados en vivo.

## Comportamiento en fin de semana y cierre de mercado

- El bot revisa cada mercado antes de hacer nada: la sesión del broker debe estar abierta **y** debe haber llegado
  una cotización en los últimos 10 minutos. Los mercados cerrados (viernes 17:00 NY → domingo 18:00 NY para oro,
  plata e índices; pausas diarias; feriados) simplemente se saltan y se reintentan cada 5 segundos.
- BTC opera durante el fin de semana.
- Las posiciones quedan abiertas el fin de semana con sus stops puestos en el broker. Un hueco puede saltar un stop; la protección
  guarda un margen del 1 % para esto.
- El estado (saldo inicial, máximo, progreso de las operaciones) se guarda en variables globales del terminal, así que un reinicio,
  un apagado o una desconexión de fin de semana no pierde el control de las operaciones.

## Instalación en tu PC con Windows (encendida 24/7)

### 1. Instalar

1. Descarga MetaTrader 5 desde el panel de tu firma de fondeo (o metatrader5.com) e inicia sesión con la cuenta de $100K.
2. `Archivo > Abrir carpeta de datos` → `MQL5\Experts` → copia allí `FibFVG_Pro.mq5`.
3. `MQL5\Presets` → copia allí `FibFVG_Pro_100K_Best.set`.
4. Abre `FibFVG_Pro.mq5` en MetaEditor (F4) → **Compilar (F7)**. Corrige cualquier mensaje antes de seguir.

### 2. Activar el trading algorítmico

1. `Herramientas > Opciones > Asesores Expertos`: marca **Permitir trading algorítmico**. Desmarca *Desactivar el trading algorítmico
   al cambiar de cuenta* y *…al cambiar de perfil*.
2. Pulsa el botón **Algo Trading** de la barra de herramientas (se pone en verde).

### 3. Adjuntar el bot

1. Abre un gráfico (XAUUSD H1 sirve). Arrastra **FibFVG_Pro** desde el Navegador.
2. Pestaña **Común**: marca *Permitir Algo Trading*. Pestaña **Parámetros**: **Cargar** → `FibFVG_Pro_100K_Best.set` → Aceptar.
3. Revisa el panel en el gráfico: lista los 5 mercados que encontró, el margen de la protección y los lotes. Un icono de carita/gorro azul
   en la esquina superior derecha del gráfico significa que está funcionando.
4. `Archivo > Perfiles > Guardar como` "FibFVG" para que MT5 vuelva a abrir este gráfico y el bot después de reiniciar.

### 4. Mantener la PC encendida 24/7

| Elemento | Ajuste |
|---|---|
| Energía | `Configuración > Sistema > Energía`: suspensión **Nunca**, apagar la pantalla está bien. Desactiva la hibernación. |
| Windows Update | Configura las *horas activas*, pausa las actualizaciones 5 semanas a la vez y reinicia a mano los sábados |
| Inicio automático | Pon un acceso directo a `terminal64.exe` en `shell:startup`; activa el inicio de sesión automático |
| BIOS | *Restaurar al volver la corriente* = **Encender**, para que la PC se reinicie sola después de un apagón |
| Cortes de luz | UPS (batería de respaldo) de 600–1000 VA |
| Internet | Router 4G/5G de respaldo o el punto de acceso del teléfono; MT5 se reconecta solo |
| Revisión | Mira las pestañas Diario y Expertos una vez al día; el panel muestra "HALTED" si la protección detiene el bot |

Un VPS con Windows en un centro de datos (o el VPS integrado de MT5) es más confiable que una PC en casa y elimina los riesgos de
electricidad e internet. **Revisa primero la firma:** Goat Funded Trader prohíbe VPS, VPN, proxies y cualquier servicio de hosting
en todas las cuentas desde el 6 oct 2026 (el bot debe correr en tu propia computadora y conexión), y FundedNext permite
EAs y VPS solo en cuentas de $5K–$25K, cada una con un complemento pagado. Nunca uses una VPN mientras operas una cuenta de fondeo.

**Prueba de autoría:** algunas firmas (Goat Funded Trader) solo permiten EAs que hayas construido tú y pueden pedir el
código fuente. Guarda este repositorio (código fuente y su historial de commits) como esa prueba.

### 5. Muchas cuentas (hasta 50 por firma)

- MT5 inicia sesión en una cuenta por terminal. Para varias cuentas, instala MT5 una vez por cuenta en carpetas separadas
  (o usa el instalador multiterminal de la firma) y adjunta el bot a cada una con el mismo preset.
- Mismas reglas + mismos precios = las mismas entradas en cada cuenta, así que un copiador de operaciones es opcional. Si usas uno,
  copia *señales*, no lotes: cada cuenta calcula su propio tamaño con sus propios $100K iniciales.
- Cada terminal usa unos 300–500 MB de RAM. 50 terminales necesitan un VPS con unos 16–32 GB de RAM.
- Ejemplo de tamaño: si el bot abre 0.05 lotes de XAGUSD en una cuenta, 50 cuentas tienen 2.5 lotes en total — 50
  veces la ganancia en dólares y 50 veces la pérdida en dólares. Revisa las reglas de cada firma sobre operaciones idénticas entre cuentas.

## Costos (aproximados, verifica antes de comprar)

| Artículo | Costo | Cuándo |
|---|---|---|
| Cuenta instantánea de $100K | $740 (promoción vista en tu captura); unos $1,480 a precio completo | Por cuenta |
| MetaTrader 5 y MetaEditor | Gratis | — |
| Electricidad de la PC en casa, 24/7 | unos $10–20 al mes | Mensual |
| UPS 600–1000 VA | unos $80–150 | Una vez |
| Internet de respaldo | unos $20–40 al mes | Mensual |
| VPS con Windows, 1–3 terminales | unos $15–40 al mes | Mensual |
| VPS con Windows, 50 terminales (16–32 GB RAM) | unos $80–200 al mes | Mensual |
| Copiador de operaciones (opcional) | unos $20–50 al mes o $100–300 una vez | Opcional |
| Billetera cripto física (billetera fría) | unos $79–150 | Una vez |

## Archivos

| Archivo | Uso |
|---|---|
| `mql5/FibFVG_Pro.mq5` | Bot de MetaTrader 5 |
| `mql4/FibFVG_Pro.mq4` | Versión para MetaTrader 4 |
| `ctrader/FibFVGPro.cs` | Versión para cTrader |
| `presets/FibFVG_Pro_100K_Best.set` | Mejores reglas, $100K, pérdida máxima 6 %, sin límite diario |
| `presets/FibFVG_Pro_100K_Best_3pctDaily.set` | Lo mismo, para firmas con límite diario del 3 % |
| `presets/FibFVG_Pro_100K_Best.cbotset` | Parámetros de cTrader |

Los bots todavía no se han compilado ni corrido en vivo. Compílalos, córrelos 4 semanas en demo o en la primera cuenta con
mucha atención, y compara sus operaciones con el backtest antes de añadir cuentas.
