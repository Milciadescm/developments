# Cueto & Co. / FibFVG Pro — reglas de trabajo

## Idioma
Todo se escribe en **español**: el Documento Maestro, los documentos del repositorio y las respuestas al usuario.
Los nombres de archivos, código, parámetros de los EAs y símbolos del broker se quedan como están.

## Un documento maestro
Todo (pruebas, resultados, planes, cambios del bot, operaciones en vivo, pagos, cuentas, pasos de la empresa) se registra en el
**Cueto & Co. — Documento Maestro**: https://claude.ai/artifact/6ugpp8DiUYF5Np6ESd1KeL
- Agrega cada nuevo elemento como una fila arriba en la tabla de Entradas de la pestaña **Registro (gana el mejor resultado)** (fecha, tipo, qué, resultado, decisión).
- Actualiza las demás pestañas (Estrategia, Pruebas, Planes, Instalación, Empresa, Riesgos) cuando cambie su contenido.
- No crees nuevos artifacts para resultados; los artifacts anteriores y el white paper son solo archivo.

## Gana el mejor resultado
El bot cambia solo si una regla nueva supera a la mejor actual en los cuatro controles:
1. Más R por operación después de spread y swaps.
2. Rentable en ambas mitades de los datos (división 2025-08-19).
3. Estadístico t >= 2.
4. Peor caída en una cuenta de $100K < 5 % (línea de la firma 6 %).
Todo lo que falle se registra como rechazado u opcional y queda fuera del preset por defecto.

## Dos tipos de dinero
- Regla de mercados: un mercado se queda en una billetera solo si es rentable en ambas mitades de los datos.
- Cuentas de fondeo (Billetera 1): ninguna operación más de 24 horas ni durante el fin de semana. Mercados BTC, US500, NAS100 al 0.75 %. Señales: `fibfvg/prop24.py`
  (señales diarias + 4 horas en 0.705, stop en el origen del impulso, cerrado en 24 h): 3 mercados +0.35R, t = 1.8, RR 1.42.
- Calendario (fechas, hitos, puntos de revisión): `fibfvg/calendar3y.py`; prueba del 6 % al mes: `fibfvg/walletbook.py`.
- Dinero real de Cueto & Co. (Billetera 2): se permite mantener posiciones. Solo oro y plata (+2.15R, t 6.4). Plan de posiciones del bot v3, 0.5 % por unidad, salida chandelier
  (+0.71R después de swaps, t = 4.0). Empieza cuando la Billetera 2 >= $100K, la mitad en el bot, stop duro del 10 % (`fibfvg/livefund.py`).
- Cuentas pequeñas (pruebas del 23 nov, `fibfvg/onemarket.py`): por debajo de $5K solo BTC, S&P y Nasdaq; nada de oro ni plata (0.01 lote arriesga demasiado).
- Billeteras (`fibfvg/wallets3.py`): una firma de fondeo a la vez hasta 50 cuentas; con menos de 50: 50 % compra cuentas,
  25 % Billetera 2, 25 % Billetera 3 cripto; con 50: 70 % Billetera 2, 25 % cripto, 5 % reserva para cuentas quemadas (5 cuentas), luego a la Billetera 2.

Primera cuenta de $100K en vivo: 1 de diciembre de 2026. Todos los números antes de esa fecha son backtests.
