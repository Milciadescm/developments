/* Driver screen: take a delivery, share live GPS with the customer's tracking map, mark delivered. */
(() => {
  "use strict";
  const { $, t, esc, money, itemName, waLink } = OPS;
  const API = window.ST_API;
  const MAP = window.ST_MAP?.available ? window.ST_MAP : null;
  const CFG = window.ST_CONFIG || {};
  let me = null, orders = [];
  let watchId = null, lastSent = 0, lastPos = null, wakeLock = null;
  let map = null, mk = {};

  const mine = () => orders.find((o) => o.driver_id === me.user_id && o.status === "on_the_way");
  const available = () => orders.filter((o) => o.mode === "delivery" && !o.driver_id && ["confirmed", "preparing"].includes(o.status));

  // ---------- GPS sharing ----------
  function gpsState(on, msg) {
    const el = $("#drv-gps"); el.classList.toggle("on", on);
    $("#drv-gps span").textContent = msg || (on ? t("drv.sharing") : t("drv.notSharing"));
  }
  async function send(pos, force = false) {
    const o = mine(); if (!o) return;
    const now = Date.now();
    if (!force && now - lastSent < (CFG.driverPingSeconds || 5) * 1000) return;
    lastSent = now;
    const patch = {
      driver_lat: +pos.coords.latitude.toFixed(6), driver_lng: +pos.coords.longitude.toFixed(6),
      driver_heading: Number.isFinite(pos.coords.heading) ? Math.round(pos.coords.heading) : null,
      driver_updated_at: new Date().toISOString(),
    };
    try { const u = await API.updateOrder(o.id, patch); upsert(u, false); moveMe(patch); } catch { /* retry on next fix */ }
  }
  function startGps() {
    if (watchId != null || !mine()) return;
    if (!navigator.geolocation) { gpsState(false, t("drv.gpsDenied")); return; }
    watchId = navigator.geolocation.watchPosition(
      (pos) => { const first = !lastPos; lastPos = pos; gpsState(true); send(pos, first); },
      () => gpsState(false, t("drv.gpsDenied")),
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 20000 });
    keepAwake();
  }
  function stopGps() {
    if (watchId != null) navigator.geolocation.clearWatch(watchId);
    watchId = null; lastPos = null;
    if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
  }
  async function keepAwake() {
    try { if ("wakeLock" in navigator && !wakeLock) wakeLock = await navigator.wakeLock.request("screen"); } catch { /* not supported */ }
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && watchId != null) { wakeLock = null; keepAwake(); } });

  // ---------- map ----------
  function moveMe(p) {
    if (!map) return;
    const ll = { lat: p.driver_lat, lng: p.driver_lng };
    if (!mk.me) mk.me = L.marker([ll.lat, ll.lng], { icon: MAP.icons.driver(), zIndexOffset: 500 }).addTo(map);
    else MAP.glide(mk.me, ll, 800);
  }
  function renderMap(o) {
    if (!MAP) { $("#drv-map").classList.add("hidden"); return; }
    const dest = o.dest_lat != null ? { lat: +o.dest_lat, lng: +o.dest_lng } : null;
    if (!map) map = MAP.create($("#drv-map"), dest || CFG.storeLocation, 14, { zoomControl: false });
    Object.values(mk).forEach((m) => map.removeLayer(m)); mk = {};
    mk.store = L.marker([CFG.storeLocation.lat, CFG.storeLocation.lng], { icon: MAP.icons.store() }).addTo(map);
    if (dest) mk.dest = L.marker([dest.lat, dest.lng], { icon: MAP.icons.home() }).addTo(map);
    if (o.driver_lat != null) moveMe(o);
    const pts = [[CFG.storeLocation.lat, CFG.storeLocation.lng]]; if (dest) pts.push([dest.lat, dest.lng]);
    if (o.driver_lat != null) pts.push([o.driver_lat, o.driver_lng]);
    map.fitBounds(pts, { padding: [40, 40], maxZoom: 16 });
    setTimeout(() => map.invalidateSize(), 60);
  }

  // ---------- render ----------
  const items = (o) => (o.items || []).map((i) => `<li><b>${i.qty}×</b> ${esc(itemName(i))}${i.notes ? ` <em>“${esc(i.notes)}”</em>` : ""}</li>`).join("");
  const payName = (id) => { const p = STORE.payments.find((x) => x.id === id); return p ? (OPS.lang === "en" ? p.en : p.es) : id; };

  function render() {
    const o = mine();
    $("#drv-active").classList.toggle("hidden", !o);
    if (o) {
      const dest = o.dest_lat != null ? { lat: o.dest_lat, lng: o.dest_lng } : null;
      $("#drv-active-body").innerHTML = `
        <h2 id="drv-active-h"><span class="ocode">${esc(o.code)}</span> · ${esc(o.customer_name)}</h2>
        <p class="drv-place">📍 ${esc(o.place || "")}${o.room ? ` · ${esc(o.room)}` : ""}<br><small>${esc(o.zone_name || "")}</small></p>
        ${o.driver_notes ? `<p class="drv-note">“${esc(o.driver_notes)}”</p>` : ""}
        <p class="drv-collect">${t("drv.collect")}: <strong>${money(o.total)}</strong> · ${esc(payName(o.payment))}${o.cash_for ? ` (${esc(o.cash_for)})` : ""}${o.age_confirmed ? ` · <b>18+ ID</b>` : ""}</p>
        <ul class="oitems">${items(o)}</ul>
        <div class="drv-buttons">
          ${dest ? `<a class="btn" href="${MAP ? MAP.gmapsDir(dest) : "#"}" target="_blank" rel="noopener">🧭 ${t("drv.navigate")}</a>` : ""}
          <a class="btn btn-ghost" href="tel:${esc(o.customer_phone)}">📞 ${t("drv.callCustomer")}</a>
          <a class="btn btn-ghost" href="${waLink(o.customer_phone, `Saint Tropez Market · ${o.code}`)}" target="_blank" rel="noopener">WhatsApp</a>
        </div>
        <button type="button" class="btn btn-block btn-lg drv-done" data-done="${o.id}">✓ ${t("drv.delivered")}</button>
        <p class="fine">${t("drv.keepOpen")}</p>`;
      renderMap(o);
      startGps();
    } else stopGps();

    const list = available();
    $("#drv-list").innerHTML = list.length ? list.map((x) => `
      <article class="ocard">
        <header><strong class="ocode">${esc(x.code)}</strong><span class="tag tag-status">${t(`lt.s.${x.status}`)}</span></header>
        <div class="ocust"><strong>${esc(x.customer_name)}</strong><span>📍 ${esc(x.place || "")} <small>${esc(x.zone_name || "")}</small></span></div>
        <ul class="oitems">${items(x)}</ul>
        <div class="ototal"><span>${esc(payName(x.payment))}</span><strong>${money(x.total)}</strong></div>
        <div class="oactions"><button type="button" class="btn btn-block" data-take="${x.id}" ${o ? "disabled" : ""}>🛵 ${t("drv.take")}</button></div>
      </article>`).join("") : `<p class="col-empty">${t("drv.empty")}</p>`;
  }

  function upsert(o, rerender = true) {
    const i = orders.findIndex((x) => x.id === o.id);
    if (i >= 0) orders[i] = o; else orders.unshift(o);
    if (rerender) render();
  }

  document.addEventListener("click", async (e) => {
    const take = e.target.closest("[data-take]"), done = e.target.closest("[data-done]");
    if (take) {
      take.disabled = true;
      try { upsert(await API.claimOrder(take.dataset.take, { driver_id: me.user_id, driver_name: me.name, status: "on_the_way" })); }
      catch (ex) {
        toast(String(ex?.message) === "taken" ? t("drv.taken") : String(ex?.message || ex));
        try { orders = await API.orders({ since: new Date(Date.now() - 86400000).toISOString() }); } catch { /* keep */ }
        render();
      }
    }
    if (done) {
      done.disabled = true;
      try {
        if (lastPos) await send(lastPos, true);
        upsert(await API.updateOrder(done.dataset.done, { status: "delivered" }));
        stopGps();
      } catch (ex) { toast(String(ex?.message || ex)); done.disabled = false; }
    }
  });

  let tt;
  function toast(m) { const el = $("#toast"); el.textContent = m; el.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => el.classList.remove("show"), 4000); }

  OPS.onLang(render);
  OPS.gate(async (who) => {
    me = who;
    orders = await API.orders({ since: new Date(Date.now() - 86400000).toISOString() });
    render();
    API.onOrdersChange((e) => { if (e.new && e.new.id) upsert(e.new); });
    setInterval(async () => { try { orders = await API.orders({ since: new Date(Date.now() - 86400000).toISOString() }); render(); } catch { /* keep */ } }, 60000);
  });
})();
