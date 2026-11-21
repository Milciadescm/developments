/* Store dashboard: incoming orders in real time, status buttons, new-order alerts. */
(() => {
  "use strict";
  const { $, t, esc, money, time, itemName, waLink } = OPS;
  const API = window.ST_API;
  let orders = [];
  let audio = null, alertsOn = false;

  const startOfDay = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
  const isOpen = (o) => !["delivered", "cancelled"].includes(o.status);

  // ---------- alerts ----------
  function beep() {
    if (!audio) return;
    const now = audio.currentTime;
    [0, .22, .44].forEach((d, i) => {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = "sine"; o.frequency.value = [880, 1175, 1568][i];
      g.gain.setValueAtTime(.0001, now + d); g.gain.exponentialRampToValueAtTime(.35, now + d + .02); g.gain.exponentialRampToValueAtTime(.0001, now + d + .2);
      o.connect(g).connect(audio.destination); o.start(now + d); o.stop(now + d + .22);
    });
  }
  $("#sound-btn").addEventListener("click", async () => {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    await audio.resume(); alertsOn = true; beep();
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
    renderSoundBtn();
  });
  function renderSoundBtn() {
    const b = $("#sound-btn"); b.classList.remove("hidden");
    b.textContent = alertsOn ? t("staff.soundOn") : t("staff.sound");
    b.classList.toggle("on", alertsOn);
  }
  function alertNew(o) {
    beep();
    toast(t("staff.newAlert", o.code));
    if (alertsOn && "Notification" in window && Notification.permission === "granted" && document.hidden) {
      try { new Notification(t("staff.newAlert", o.code), { body: `${o.customer_name} · ${money(o.total)}`, icon: "images/emblem.svg" }); } catch { /* ignore */ }
    }
  }

  // ---------- actions per status ----------
  function actions(o) {
    const del = o.mode === "delivery";
    const A = (status, label, cls = "") => `<button type="button" class="btn ${cls}" data-id="${o.id}" data-status="${status}">${label}</button>`;
    switch (o.status) {
      case "pending": return A("confirmed", t("staff.confirm")) + A("cancelled", t("staff.cancel"), "btn-ghost");
      case "confirmed": return A("preparing", t("staff.prepare"));
      case "preparing": return del ? `<span class="wait">🛵 ${t("staff.dispatch")}</span>` + A("delivered", t("staff.deliver"), "btn-ghost") : A("ready", t("staff.ready"));
      case "ready": return A("delivered", t("staff.deliver"));
      case "on_the_way": return A("delivered", t("staff.deliver"), "btn-ghost");
      default: return "";
    }
  }

  function card(o) {
    const del = o.mode === "delivery";
    const mins = Math.round((Date.now() - new Date(o.created_at).getTime()) / 60000);
    const items = (o.items || []).map((i) => `<li><b>${i.qty}×</b> ${esc(itemName(i))} <small>${esc(i.unit)}</small>${i.notes ? `<em>“${esc(i.notes)}”</em>` : ""}</li>`).join("");
    const mapUrl = o.dest_lat != null ? `https://www.google.com/maps/search/?api=1&query=${o.dest_lat},${o.dest_lng}` : null;
    return `<article class="ocard st-${o.status}" data-id="${o.id}">
      <header>
        <strong class="ocode">${esc(o.code)}</strong>
        <span class="tag ${del ? "tag-del" : "tag-pick"}">${del ? t("staff.delivery") : t("staff.pickup")}</span>
        <span class="tag tag-status">${t(`lt.s.${o.status}`)}</span>
        <time title="${esc(new Date(o.created_at).toLocaleString())}">${time(o.created_at)} · ${t("staff.ago", mins)}</time>
      </header>
      ${o.scheduled_for ? `<p class="sched">⏰ ${t("staff.scheduled")}: ${new Date(o.scheduled_for).toLocaleString(T[OPS.lang].locale, { weekday: "short", hour: "numeric", minute: "2-digit" })}</p>` : ""}
      <div class="ocust">
        <strong>${esc(o.customer_name)}</strong>
        <span>${esc(o.customer_phone)}</span>
        ${del ? `<span>📍 ${esc(o.place || "")}${o.room ? ` · ${esc(o.room)}` : ""} <small>${esc(o.zone_name || "")}</small></span>` : ""}
        ${o.driver_notes ? `<em>“${esc(o.driver_notes)}”</em>` : ""}
      </div>
      <ul class="oitems">${items}</ul>
      <div class="ototal">
        <span>${esc(nmPay(o.payment))}${o.cash_for ? ` · ${esc(o.cash_for)}` : ""}${o.age_confirmed ? ` · <b>${t("staff.age")}</b>` : ""}</span>
        <strong>${money(o.total)}</strong>
      </div>
      ${del ? `<p class="odriver">🛵 ${t("staff.driver")}: <b>${esc(o.driver_name || t("staff.noDriver"))}</b></p>` : ""}
      <div class="olinks">
        <a href="tel:${esc(o.customer_phone)}">${t("staff.call")}</a>
        <a href="${waLink(o.customer_phone, `Saint Tropez Market · ${o.code}`)}" target="_blank" rel="noopener">WhatsApp</a>
        ${mapUrl ? `<a href="${mapUrl}" target="_blank" rel="noopener">${t("staff.map")}</a>` : ""}
        <a href="track.html?t=${encodeURIComponent(o.track_token)}" target="_blank" rel="noopener">${t("staff.track")}</a>
      </div>
      <div class="oactions">${actions(o)}</div>
    </article>`;
  }
  const nmPay = (id) => { const p = STORE.payments.find((x) => x.id === id); return p ? (OPS.lang === "en" ? p.en : p.es) : id; };

  function render() {
    const today = startOfDay();
    const neu = orders.filter((o) => o.status === "pending");
    const act = orders.filter((o) => isOpen(o) && o.status !== "pending");
    const done = orders.filter((o) => !isOpen(o) && new Date(o.updated_at) >= today);
    const fill = (id, list) => { $(id).innerHTML = list.length ? list.map(card).join("") : `<p class="col-empty">${t("staff.empty")}</p>`; };
    fill("#col-new", neu.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)));
    fill("#col-active", act.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)));
    fill("#col-done", done.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)));
    $("#n-new").textContent = neu.length; $("#n-active").textContent = act.length; $("#n-done").textContent = done.length;
    document.title = `${neu.length ? `(${neu.length}) ` : ""}${t("staff.title")} · Saint Tropez`;
  }

  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-status]"); if (!b) return;
    const status = b.dataset.status;
    if (status === "cancelled" && !confirm(t("staff.cancelQ"))) return;
    b.disabled = true;
    try {
      const updated = await API.updateOrder(b.dataset.id, { status });
      upsert(updated);
    } catch (ex) { toast(String(ex?.message || ex)); b.disabled = false; }
  });

  function upsert(o) {
    const i = orders.findIndex((x) => x.id === o.id);
    if (i >= 0) orders[i] = o; else orders.unshift(o);
    render();
  }

  let tt;
  function toast(m) { const el = $("#toast"); el.textContent = m; el.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => el.classList.remove("show"), 4000); }

  OPS.onLang(() => { renderSoundBtn(); render(); });
  OPS.gate(async () => {
    renderSoundBtn();
    const since = new Date(Date.now() - 2 * 86400000).toISOString();
    orders = await API.orders({ since });
    render();
    API.onOrdersChange((e) => {
      if (e.eventType === "INSERT") { upsert(e.new); alertNew(e.new); }
      else if (e.eventType === "UPDATE") upsert(e.new);
    });
    // safety net: refresh list every minute and keep "x min ago" current
    setInterval(async () => { try { orders = await API.orders({ since: new Date(Date.now() - 2 * 86400000).toISOString() }); } catch { /* keep */ } render(); }, 60000);
  });
})();
