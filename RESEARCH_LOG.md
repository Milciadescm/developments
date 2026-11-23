# Registro de investigación: ideas probadas y descartadas

Se guarda para que nadie vuelva a probarlas. Los números son R neto por operación después del spread salvo que se indique otra cosa.
(Desde el 22 nov 2026 todo se registra en el Documento Maestro: https://claude.ai/artifact/6ugpp8DiUYF5Np6ESd1KeL)

| Idea | Resultado | Por qué se descartó |
|---|---|---|
| Swing semanal v1 (TP1/TP2 fijos), 2005–2026 | +0.10R, ~2 %/año, caída del 41 % con $50k | Reemplazado por las salidas del Plan 1 (dejar correr las ganadoras triplicó la ventaja) |
| Motor micro de FVG en 4H | +0.06R, +0.03R fuera de muestra | Demasiado débil |
| Micro FVG en 1m / 5m / 15m / 30m / 1H (3 estilos de salida) | Bruto +0.01 a +0.17R, neto negativo o cambia de signo entre mitades | Sin ventaja después del spread |
| Scalper de FVG en S&P a 15/30/45 segundos | No se puede probar (sin datos por segundo) | Nunca validado |
| Invertir las operaciones perdedoras (espejo / 1:1) | −0.06R / −0.52R | Se pagan costos en ambos lados; solo el micro en oro llegó a empatar |
| Tiempo por conteo de velas Fibonacci, sesiones de Londres/NY, entradas semanales lun–mié | Ayudó en los datos tempranos, falló en los posteriores | Sobreajuste |
| Niveles + kill zones con el stop pasando la mecha de reacción | −0.12 a −0.36R (bruto negativo); algunas operaciones de 10R/50R | Stop dentro del ruido normal |
| Entradas solo en kill zones (stop de ATR diario) | No mejor que todas las horas, menos operaciones | Apagado por defecto (`KillZonesOnly`) |
| Objetivo fijo de 2R en las entradas de niveles | +2R alcanzado primero ~35 %; ≈ empate después de costos | Sin ventaja |
| Judas de Londres (barrido del rango de Asia) + 2R | −0.155R (ambas mitades negativas) | Sin ventaja |
| Barrido en NY del máximo/mínimo del día anterior + 2R | −0.105R (ambas mitades negativas) | Sin ventaja |
| Mitad en +2R con stop de medio rango diario | −0.03R | Stop demasiado ajustado |
| Saltar los días de CPI | Sin cambio medible (7 operaciones) | No hace falta |

## Compuertas de riesgo (Core + banco 2R, Instant Premium $100K, jul 2024 → nov 2026) — `results/gates.json`

| Compuerta | Pagado | Peor caída | Pagado por 1 % de caída | Mediana a 12 meses (peor) |
|---|---|---|---|---|
| Normal fijo (se mantiene: por defecto en fondeo) | $24,501 | 4.65 % | $5,269 | $15,809 (+$3,827) |
| Compuerta por mercado + Normal (se mantiene: dinero de la empresa/fondo; aún no en los bots) | $17,424 | 2.55 % | $6,833 | $12,432 (+$1,371) |
| Compuerta Normal primero | $21,855 | 3.98 % | $5,491 | $10,770 (−$427) |
| Compuerta de ventaja (regla de 20/40 operaciones) | $16,138 | 4.47 % | $3,610 | $9,214 (−$113) |
| Agresivo fijo | $8,184 | 4.94 % | $1,657 | $20,023 (−$740) |

Ninguna compuerta produjo una ventaja mayor; las operaciones con compuerta por mercado pagan con la mitad de la caída.
