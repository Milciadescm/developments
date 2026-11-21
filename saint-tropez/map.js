/* Map helpers shared by checkout, tracking, staff and driver pages (Leaflet + OpenStreetMap). */
(() => {
  const cfg = window.ST_CONFIG || {};
  const L = window.L;

  const pin = (cls, html) => L && L.divIcon({ className: `st-pin ${cls}`, html, iconSize: [44, 44], iconAnchor: [22, 22] });

  window.ST_MAP = {
    available: !!L,
    create(el, center, zoom = 14, opts = {}) {
      if (!L) return null;
      const map = L.map(el, { zoomControl: opts.zoomControl ?? true, attributionControl: true, scrollWheelZoom: opts.scroll ?? false });
      L.tileLayer(cfg.tiles, { maxZoom: 19, attribution: cfg.tilesAttribution }).addTo(map);
      map.setView([center.lat, center.lng], zoom);
      return map;
    },
    icons: {
      store: () => pin("pin-store", '<span class="pin-disc"><img src="images/emblem.svg" alt=""></span>'),
      home: () => pin("pin-home", '<svg viewBox="0 0 24 24"><path d="M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.6"/></svg>'),
      driver: () => pin("pin-driver", '<span class="pin-pulse"></span><svg viewBox="0 0 24 24"><circle cx="6" cy="17" r="2.6"/><circle cx="18" cy="17" r="2.6"/><path d="M8.6 17h6.8M14 8h3l3 6M6 14l3-6h4l2 9"/></svg>'),
    },
    // metres between two {lat,lng}
    distance(a, b) {
      const R = 6371000, rad = (d) => (d * Math.PI) / 180;
      const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
      const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
      return 2 * R * Math.asin(Math.sqrt(h));
    },
    // rough driving minutes in town: road factor 1.35, 28 km/h average, +2 min to park & hand over
    etaMinutes(a, b) {
      const km = (this.distance(a, b) * 1.35) / 1000;
      return Math.max(1, Math.round((km / 28) * 60 + 2));
    },
    // smoothly move a marker to a new position
    glide(marker, to, ms = 1200) {
      const from = marker.getLatLng(); const t0 = performance.now();
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { marker.setLatLng(to); return; }
      const step = (t) => {
        const k = Math.min(1, (t - t0) / ms); const e = k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
        marker.setLatLng([from.lat + (to.lat - from.lat) * e, from.lng + (to.lng - from.lng) * e]);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    },
    gmapsDir: (p) => `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=driving`,
  };
})();
