"""Descarga velas de 5 minutos de Binance (servidor público de datos de mercado) con volumen comprador agresivo.

    python tools/get_binance_m5.py PAXGUSDT data/PAXGUSD_M5.csv
    python tools/get_binance_m5.py BTCUSDT data/BTCUSDT_M5_flow.csv
Columnas: t (UTC), Open, High, Low, Close, Volume, TakerBuy (volumen comprado a mercado). Desde 2024-01-01 hasta hoy.
PAXG es un token respaldado 1:1 por una onza de oro físico: sirve como precio del oro 24/7.
"""
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

URL = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval=5m&limit=1000&startTime={t}"


def main(sym, out):
    t = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    now = int(time.time() * 1000)
    rows = 0
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "Open", "High", "Low", "Close", "Volume", "TakerBuy"])
        while t < now:
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(URL.format(s=sym, t=t), timeout=30) as r:
                        data = json.loads(r.read())
                    break
                except Exception as e:      # reintento con espera creciente
                    time.sleep(2 ** attempt)
            else:
                raise SystemExit(f"falló en {t}")
            if not data:
                break
            for k in data:
                ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat()
                w.writerow([ts, k[1], k[2], k[3], k[4], k[5], k[9]])
            rows += len(data)
            t = data[-1][0] + 300_000
            time.sleep(0.15)
    print(sym, rows, "velas ->", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
