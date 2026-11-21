/* Live order tracking: map + status, updated in real time from the store and the driver's phone. */
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const API = window.ST_API?.available ? window.ST_API : null;
  const MAP = window.ST_MAP?.available ? window.ST_MAP : null;
  const CFG = window.ST_CONFIG || {};
  const token = new URLSearchParams(location.search).get("t");
  const lsGet = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };

  let lang = lsGet("st-lang") || ((navigator.language || "es").startsWith("en") ? "en" : "es");
  const t = (k, ...a) => { const v = T[lang][k] ?? T.es[k] ?? k; return typeof v === "function" ? v(...a) : v; };
  const money = (n) => `${STORE.currency} ${Math.round(n).toLocaleString(t("locale"))}`;

  let order = null; const started = Date.now();
  let map = null, mk = {}, line = null, fitted = false, lastPoll = 0, live = false;

  const STEPS = {
    delivery: ["pending", "confirmed", "preparing", "on_the_way", "delivered"],
    pickup: ["pending", "confirmed", "preparing", "ready", "delivered"],
  };
  const hasDriver = () => order && order.driver_lat != null && order.driver_lng != null;
  const dest = () => (order && order.dest_lat != null ? { lat: +order.dest_lat, lng: +order.dest_lng } : null);
  const store = CFG.storeLocation;

  function fmtDist(m) { return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`; }
  function ago(iso) {
    const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    return s < 60 ? `${s} s` : `${Math.round(s / 60)} min`;
  }

  // ---------- static text ----------
  function applyStatic() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { const v = T[lang][el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
    $("#lang-toggle").textContent = lang === "en" ? "ES" : "EN";
    $("#lang-toggle").setAttribute("aria-label", lang === "en" ? "Cambiar a español" : "Switch to English");
    document.title = `${t("lt.title")} · Saint Tropez Market 24/7`;
  }
  $("#lang-toggle").addEventListener("click", () => { lang = lang === "en" ? "es" : "en"; lsSet("st-lang", lang); applyStatic(); if (order) render(); });

  // ---------- map ----------
  function ensureMap() {
    if (map || !MAP) return;
    map = MAP.create($("#lt-map"), store, 14, { zoomControl: false, scroll: true });
    mk.store = L.marker([store.lat, store.lng], { icon: MAP.icons.store(), title: t("lt.store") }).addTo(map);
  }
  function renderMap() {
    if (!MAP) { $("#lt-map").classList.add("no-map"); return; }
    ensureMap();
    const d = dest();
    if (d && !mk.dest) mk.dest = L.marker([d.lat, d.lng], { icon: MAP.icons.home(), title: t("lt.you") }).addTo(map);
    const showDriver = hasDriver() && order.status === "on_the_way";
    if (showDriver) {
      const p = { lat: +order.driver_lat, lng: +order.driver_lng };
      if (!mk.driver) mk.driver = L.marker([p.lat, p.lng], { icon: MAP.icons.driver(), zIndexOffset: 500, title: t("lt.driver") }).addTo(map);
      else MAP.glide(mk.driver, p);
    } else if (mk.driver) { map.removeLayer(mk.driver); mk.driver = null; }

    // dashed path from where the order is now to where it's going
    const from = showDriver ? { lat: +order.driver_lat, lng: +order.driver_lng } : store;
    const to = order.mode === "delivery" ? d : null;
    if (line) { map.removeLayer(line); line = null; }
    if (to && order.status !== "delivered" && order.status !== "cancelled") {
      line = L.polyline([[from.lat, from.lng], [to.lat, to.lng]], { color: "#e8cf98", weight: 4, opacity: .85, dashArray: "2 10", lineCap: "round" }).addTo(map);
    }
    const pts = [[store.lat, store.lng]];
    if (d) pts.push([d.lat, d.lng]);
    if (showDriver) pts.push([+order.driver_lat, +order.driver_lng]);
    if (!fitted || showDriver) {
      const wide = window.innerWidth >= 900;
      const sheetH = $("#lt-sheet").offsetHeight;
      const pad = wide ? { paddingTopLeft: [460, 90], paddingBottomRight: [60, 60] } : { paddingTopLeft: [40, 80], paddingBottomRight: [40, sheetH + 30] };
      if (pts.length > 1) map.fitBounds(pts, { ...pad, maxZoom: 16, animate: fitted });
      else map.setView(pts[0], 15);
      fitted = true;
    }
  }

  // ---------- sheet ----------
  function etaText() {
    const s = order.status;
    if (s === "delivered") return { label: "", big: t("lt.st.delivered") };
    if (s === "cancelled") return { label: "", big: t("lt.st.cancelled") };
    if (order.scheduled_for && (s === "pending" || s === "confirmed")) {
      return { label: t("lt.scheduled"), big: new Date(order.scheduled_for).toLocaleString(t("locale"), { weekday: "short", hour: "numeric", minute: "2-digit" }) };
    }
    if (order.mode === "pickup") return { label: s === "ready" ? "" : t("lt.ready"), big: s === "ready" ? t("lt.st.ready") : `${STORE.pickupMinutes} ${t("lt.min")}` };
    if (s === "on_the_way" && hasDriver() && dest() && MAP) {
      const m = MAP.etaMinutes({ lat: +order.driver_lat, lng: +order.driver_lng }, dest());
      const at = new Date(Date.now() + m * 60000).toLocaleTimeString(t("locale"), { hour: "numeric", minute: "2-digit" });
      return { label: t("lt.arriving"), big: `${m} ${t("lt.min")}`, sub: at };
    }
    return { label: t("lt.eta"), big: `${order.eta || "30–45"} ${t("lt.min")}` };
  }

  function render() {
    $("#lt-loading").classList.add("hidden");
    $("#lt-content").classList.remove("hidden");
    const e = etaText();
    $("#lt-eta-label").textContent = e.label || "";
    $("#lt-eta").textContent = e.big + (e.sub ? ` · ${e.sub}` : "");
    $("#lt-status").textContent = order.status === "delivered" || order.status === "cancelled" ? "" : t(`lt.st.${order.status}`);

    const steps = STEPS[order.mode] || STEPS.delivery;
    const cur = steps.indexOf(order.status);
    $("#lt-steps").innerHTML = order.status === "cancelled" ? "" : steps.map((s, i) => {
      const at = order.status_times?.[s];
      return `<li class="${i < cur || order.status === "delivered" ? "done" : i === cur ? "now" : ""}">
        <span class="bar"></span><span class="lbl">${t(`lt.s.${s}`)}</span>${at ? `<time>${new Date(at).toLocaleTimeString(t("locale"), { hour: "numeric", minute: "2-digit" })}</time>` : ""}
      </li>`;
    }).join("");

    // driver card
    const showDriver = order.mode === "delivery" && order.status === "on_the_way" && (order.driver_name || hasDriver());
    $("#lt-driver").classList.toggle("hidden", !showDriver);
    if (showDriver) {
      $("#lt-driver-name").textContent = order.driver_name || "Saint Tropez";
      renderSeen();
    }

    // where
    const del = order.mode === "delivery";
    $("#lt-where-label").textContent = del ? t("lt.deliverTo") : t("lt.pickupAt");
    $("#lt-where").textContent = del ? `${order.place || ""}${order.room ? ` · ${order.room}` : ""}` : t("lt.store");
    $("#lt-where-sub").textContent = del ? order.zone_name || "" : "Downtown Punta Cana";

    $("#lt-call").href = `tel:${STORE.phone}`;
    $("#lt-wa").href = `https://wa.me/${STORE.whatsapp}?text=${encodeURIComponent(`${t("lt.order")} ${order.code}`)}`;
    $("#lt-code").textContent = order.code;
    const nameOf = (i) => (lang === "en" ? i.name_en : i.name_es) || i.name_es;
    $("#lt-items").innerHTML = (order.items || []).map((i) =>
      `<li><span class="ci-q">${i.qty}×</span><span class="ci-n">${esc(nameOf(i))}${i.notes ? `<small>“${esc(i.notes)}”</small>` : ""}</span><span>${money(i.price * i.qty)}</span></li>`).join("");
    $("#lt-totals").innerHTML = `
      <div><dt>${t("cart.subtotal")}</dt><dd>${money(order.subtotal)}</dd></div>
      ${del ? `<div><dt>${t("co.delivery")}</dt><dd>${money(order.delivery_fee)}</dd></div><div><dt>${t("co.tip")}</dt><dd>${money(order.tip)}</dd></div>` : ""}
      <div class="grand"><dt>${t("co.total")}</dt><dd>${money(order.total)}</dd></div>`;
    renderMap();
  }
  function renderSeen() {
    if (!order?.driver_updated_at) { $("#lt-driver-seen").textContent = ""; return; }
    const parts = [t("lt.lastSeen", ago(order.driver_updated_at))];
    if (hasDriver() && dest() && MAP) parts.unshift(t("lt.away", fmtDist(MAP.distance({ lat: +order.driver_lat, lng: +order.driver_lng }, dest()))));
    $("#lt-driver-seen").textContent = parts.join(" · ");
  }

  // ---------- data ----------
  async function load() {
    try {
      const o = await API.track(token);
      if (!o) throw new Error("not found");
      const firstLoad = !order;
      order = o; lastPoll = Date.now();
      if (firstLoad && o.lang && !lsGet("st-lang")) { lang = o.lang; applyStatic(); }
      render();
      lsSet("st-last-order", { ...(lsGet("st-last-order") || {}), id: o.code, token, createdAt: o.created_at });
    } catch {
      if (!order) { $("#lt-loading").textContent = t("lt.notFound"); }
    }
  }

  function start() {
    applyStatic();
    if (!token || !API) { $("#lt-loading").textContent = API ? t("lt.notFound") : t("ops.offline"); return; }
    load().then(() => {
      if (!order) return;
      try {
        API.subscribeOrder(token,
          (patch) => { order = { ...order, ...patch }; lastPoll = Date.now(); render(); },
          (status) => { live = status === "SUBSCRIBED"; });
      } catch { /* polling only */ }
    });
    setInterval(() => {
      if (!order) return;
      renderSeen();
      if (order.status === "on_the_way" && hasDriver()) { const e = etaText(); $("#lt-eta").textContent = e.big + (e.sub ? ` · ${e.sub}` : ""); }
      if (Date.now() - lastPoll > 20000 && order.status !== "delivered" && order.status !== "cancelled") load();
      $("#lt-offline").classList.toggle("hidden", live || order.status === "delivered" || Date.now() - started < 8000);
    }, 1000);
  }

  $("#lt-share").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); toast(t("lt.copied")); } catch { prompt("", location.href); }
  });
  let tt;
  function toast(m) { const el = $("#toast"); el.textContent = m; el.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => el.classList.remove("show"), 1600); }

  start();
})();
