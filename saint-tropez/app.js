/* Saint Tropez Market 24/7 — online ordering (static, no build step). */
(() => {
  "use strict";

  // ---------- helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ls = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  };
  const byId = Object.fromEntries(PRODUCTS.map((p) => [p.id, p]));

  // ---------- state ----------
  let lang = ls.get("st-lang", null) || ((navigator.language || "es").startsWith("en") ? "en" : "es");
  const state = {
    mode: ls.get("st-mode", "delivery"),
    zone: ls.get("st-zone", null),
    cart: ls.get("st-cart", []).filter((l) => byId[l.id]), // [{id, qty, notes}]
    tipPct: ls.get("st-tip", 10),
    pay: "cash",
    when: "asap",
    coords: null,
    lastOrder: ls.get("st-last-order", null),
  };
  const save = () => {
    ls.set("st-cart", state.cart); ls.set("st-mode", state.mode); ls.set("st-zone", state.zone); ls.set("st-tip", state.tipPct);
  };

  const t = (k, ...a) => { const v = T[lang][k] ?? T.es[k] ?? k; return typeof v === "function" ? v(...a) : v; };
  const money = (n) => `${STORE.currency} ${Math.round(n).toLocaleString(t("locale"))}`;
  const usd = (n) => `≈ US$ ${(n / STORE.usdRate).toFixed(2)}`;
  const nm = (o) => o[lang] || o.es;
  const zoneObj = () => STORE.zones.find((z) => z.id === state.zone) || null;
  const minFee = Math.min(...STORE.zones.map((z) => z.fee));

  // ---------- totals ----------
  function totals() {
    const items = state.cart.reduce((n, l) => n + l.qty, 0);
    const subtotal = state.cart.reduce((n, l) => n + byId[l.id].price * l.qty, 0);
    const delivery = state.mode === "delivery" ? (zoneObj()?.fee ?? 0) : 0;
    const tip = state.mode === "delivery" ? Math.round((subtotal * state.tipPct) / 100) : 0;
    return { items, subtotal, delivery, tip, total: subtotal + delivery + tip };
  }
  const hasAlcohol = () => state.cart.some((l) => byId[l.id].alcohol);

  // ---------- static text ----------
  function applyStatic() {
    document.documentElement.lang = lang;
    $$("[data-i18n]").forEach((el) => { const v = T[lang][el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $$("[data-i18n-alt]").forEach((el) => { el.alt = t(el.dataset.i18nAlt); });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    $("#lang-toggle").textContent = lang === "en" ? "ES" : "EN";
    $("#lang-toggle").setAttribute("aria-label", lang === "en" ? "Cambiar a español" : "Switch to English");
    $("#cart-btn").setAttribute("aria-label", `${t("top.cart")} (${totals().items})`);
    $(".skip").textContent = lang === "en" ? "Skip to products" : "Saltar a los productos";
  }

  // ---------- header: mode + address ----------
  function renderMode() {
    $$("[data-mode]").forEach((b) => {
      const on = b.dataset.mode === state.mode;
      b.setAttribute("aria-checked", String(on)); b.classList.toggle("on", on);
    });
    const z = zoneObj();
    $$(".addr-label").forEach((el) => { el.textContent = state.mode === "delivery" ? t("top.deliverTo") : t("top.pickupAt"); });
    $$(".addr-value").forEach((el) => { el.textContent = state.mode === "delivery" ? (z ? nm(z) : t("top.chooseZone")) : t("top.store"); });
    renderStats();
  }
  function renderStats() {
    const z = zoneObj();
    const items = state.mode === "delivery"
      ? [
          [z ? z.eta : `${STORE.zones[0].eta}`, t("min")],
          [z ? money(z.fee) : `${t("hero.fee")} ${money(minFee)}`, state.mode === "delivery" && z ? t("co.delivery") : ""],
          [money(STORE.minOrder), t("hero.min")],
        ]
      : [[`${STORE.pickupMinutes}`, t("min")], [t("hero.open"), "24/7"]];
    $("#store-stats").innerHTML = items.map(([a, b]) => `<li><strong>${esc(a)}</strong>${b ? `<span>${esc(b)}</span>` : ""}</li>`).join("");
  }

  function openZones() {
    $("#zone-list").innerHTML = STORE.zones.map((z) => `
      <button type="button" class="zone ${z.id === state.zone ? "on" : ""}" data-zone="${z.id}">
        <span><strong>${esc(nm(z))}</strong><small>${z.eta} ${t("min")}</small></span>
        <em>${money(z.fee)}</em>
      </button>`).join("");
    $("#zone-dialog").showModal();
  }
  $("#zone-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-zone]"); if (!b) return;
    state.zone = b.dataset.zone; state.mode = "delivery"; save();
    $("#zone-dialog").close(); renderAll();
  });
  $$("[data-addr]").forEach((b) => b.addEventListener("click", () => {
    if (state.mode === "pickup") { document.getElementById("visit").scrollIntoView({ behavior: "smooth" }); return; }
    openZones();
  }));
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-mode]"); if (!b) return;
    state.mode = b.dataset.mode; save(); renderAll();
    if ($("#checkout-dialog").open) renderCheckout();
  });

  // ---------- catalogue ----------
  const tile = (p, big) => p.img
    ? `<img src="${esc(p.img)}" alt="" loading="lazy">`
    : `<span class="emoji${big ? " big" : ""}" aria-hidden="true">${p.emoji}</span>`;

  function qtyOf(id) { return state.cart.filter((l) => l.id === id).reduce((n, l) => n + l.qty, 0); }

  function card(p, rail = false) {
    const q = qtyOf(p.id);
    const pct = p.was ? Math.round((1 - p.price / p.was) * 100) : 0;
    return `<article class="pcard${rail ? " rail-card" : ""}" data-id="${p.id}">
      <button type="button" class="pcard-open" data-open="${p.id}" aria-label="${esc(nm(p))}, ${money(p.price)}">
        <div class="pcard-media cat-${p.cat}">${tile(p)}
          ${pct ? `<span class="badge">-${pct}%</span>` : ""}${p.alcohol ? `<span class="badge age-badge">${t("shop.age")}</span>` : ""}
        </div>
        <div class="pcard-body">
          <p class="pcard-price"><strong>${money(p.price)}</strong>${p.was ? `<s>${money(p.was)}</s>` : ""}</p>
          <h3>${esc(nm(p))}</h3>
          <p class="pcard-unit">${esc(p.unit)}</p>
        </div>
      </button>
      ${q
        ? `<div class="qty qty-float" aria-label="${esc(nm(p))}">
             <button type="button" data-dec="${p.id}" aria-label="${t("qtyMinus")}">${q === 1 ? "🗑" : "−"}</button>
             <output>${q}</output>
             <button type="button" data-inc="${p.id}" aria-label="${t("qtyPlus")}">+</button>
           </div>`
        : `<button type="button" class="add-float" data-inc="${p.id}" aria-label="${t("shop.add")}: ${esc(nm(p))}">+</button>`}
    </article>`;
  }

  function renderCatbar() {
    $("#catbar").innerHTML = CATEGORIES.map((c) =>
      `<a href="#cat-${c.id}" data-cat="${c.id}"><span aria-hidden="true">${c.icon}</span>${esc(nm(c))}</a>`).join("");
  }

  function renderShop() {
    const q = $("#search").value.trim().toLowerCase();
    const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    if (q) {
      const hits = PRODUCTS.filter((p) => norm(`${p.es} ${p.en}`).includes(norm(q)));
      $("#results").innerHTML = hits.length ? hits.map((p) => card(p)).join("") : `<p class="empty-note">${t("shop.noResults")}</p>`;
      $("#results-shelf").classList.remove("hidden");
      $("#popular-shelf").classList.add("hidden");
      $("#categories").classList.add("hidden");
      return;
    }
    $("#results-shelf").classList.add("hidden");
    $("#popular-shelf").classList.remove("hidden");
    $("#categories").classList.remove("hidden");
    $("#popular").innerHTML = PRODUCTS.filter((p) => p.popular).map((p) => card(p, true)).join("");
    $("#categories").innerHTML = CATEGORIES.map((c) => {
      const items = PRODUCTS.filter((p) => p.cat === c.id);
      if (!items.length) return "";
      return `<section class="shelf" id="cat-${c.id}" aria-labelledby="h-${c.id}">
        <h2 id="h-${c.id}"><span aria-hidden="true">${c.icon}</span> ${esc(nm(c))}</h2>
        <div class="grid">${items.map((p) => card(p)).join("")}</div>
      </section>`;
    }).join("");
  }

  // Re-render only cards of one product (keeps scroll position & focus reasonable)
  function refreshCards(id) {
    $$(`.pcard[data-id="${id}"]`).forEach((el) => {
      const rail = el.classList.contains("rail-card");
      el.outerHTML = card(byId[id], rail);
    });
  }

  let searchTimer;
  $("#search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderShop, 120); });

  // scroll-spy on category bar
  const spy = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      const id = en.target.id.replace("cat-", "");
      $$("#catbar a").forEach((a) => a.classList.toggle("on", a.dataset.cat === id));
      const on = $(`#catbar a[data-cat="${id}"]`);
      if (on) on.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  const observeShelves = () => { spy.disconnect(); $$("#categories .shelf").forEach((s) => spy.observe(s)); };

  // ---------- cart ops ----------
  function add(id, qty = 1, notes = "") {
    const line = state.cart.find((l) => l.id === id && (l.notes || "") === (notes || ""));
    if (line) line.qty += qty; else state.cart.push({ id, qty, notes });
    save(); afterCartChange(id);
    toast(`${nm(byId[id])} · ${t("shop.added")} ✓`);
  }
  function dec(id) {
    // remove from the last line of this product
    for (let i = state.cart.length - 1; i >= 0; i--) {
      if (state.cart[i].id === id) { state.cart[i].qty -= 1; if (state.cart[i].qty <= 0) state.cart.splice(i, 1); break; }
    }
    save(); afterCartChange(id);
  }
  function afterCartChange(id) {
    if (id) refreshCards(id); else renderShop();
    renderCartBadge(); if ($("#cart-dialog").open) renderCart();
  }

  document.addEventListener("click", (e) => {
    const inc = e.target.closest("[data-inc]"); if (inc) { e.stopPropagation(); add(inc.dataset.inc); return; }
    const d = e.target.closest("[data-dec]"); if (d) { e.stopPropagation(); dec(d.dataset.dec); return; }
    const o = e.target.closest("[data-open]"); if (o) openProduct(o.dataset.open);
  });

  function renderCartBadge() {
    const { items, subtotal } = totals();
    $("#cart-count").textContent = items;
    $("#cart-count").classList.toggle("zero", !items);
    $("#cart-btn").setAttribute("aria-label", `${t("top.cart")} (${items})`);
    $("#cartbar").classList.toggle("hidden", !items);
    $("#cartbar-count").textContent = items;
    $("#cartbar-total").textContent = money(subtotal);
  }

  // ---------- product dialog ----------
  let pd = { id: null, qty: 1, lineIndex: -1 };
  function openProduct(id, lineIndex = -1) {
    const p = byId[id];
    const line = lineIndex >= 0 ? state.cart[lineIndex] : null;
    pd = { id, qty: line ? line.qty : 1, lineIndex };
    $("#pd-media").className = `pd-media cat-${p.cat}`;
    $("#pd-media").innerHTML = tile(p, true);
    $("#pd-name").textContent = nm(p);
    $("#pd-unit").textContent = p.unit;
    $("#pd-price").innerHTML = `<strong>${money(p.price)}</strong>${p.was ? ` <s>${money(p.was)}</s>` : ""}`;
    $("#pd-alcohol").classList.toggle("hidden", !p.alcohol);
    $("#pd-alcohol").textContent = t("pm.alcohol");
    $("#pd-notes").value = line?.notes || "";
    updatePd();
    $("#product-dialog").showModal();
  }
  function updatePd() {
    const p = byId[pd.id];
    $("#pd-qty").textContent = pd.qty;
    $("#pd-minus").disabled = pd.qty <= 1;
    $("#pd-add").textContent = pd.lineIndex >= 0 ? t("pm.update", money(p.price * pd.qty)) : t("pm.add", money(p.price * pd.qty));
  }
  $("#pd-minus").addEventListener("click", () => { pd.qty = Math.max(1, pd.qty - 1); updatePd(); });
  $("#pd-plus").addEventListener("click", () => { pd.qty = Math.min(99, pd.qty + 1); updatePd(); });
  $("#product-form").addEventListener("submit", (e) => {
    if (e.submitter?.value !== "add") return;
    const notes = $("#pd-notes").value.trim();
    if (pd.lineIndex >= 0) {
      state.cart[pd.lineIndex] = { id: pd.id, qty: pd.qty, notes };
      save(); afterCartChange(pd.id);
    } else add(pd.id, pd.qty, notes);
  });

  // ---------- cart drawer ----------
  function renderCart() {
    const tt = totals();
    if (!state.cart.length) {
      $("#cart-body").innerHTML = `<div class="empty">
        <span aria-hidden="true">🛒</span><strong>${t("cart.empty")}</strong><p>${t("cart.emptySub")}</p>
        <button type="button" class="btn" id="cart-browse">${t("cart.browse")}</button></div>`;
      $("#cart-foot").innerHTML = "";
      $("#cart-browse").addEventListener("click", () => $("#cart-dialog").close());
      return;
    }
    $("#cart-body").innerHTML = `
      <div class="cart-meta"><span>${t("cart.items", tt.items)}</span><button type="button" class="link" id="cart-clear">${t("cart.clear")}</button></div>
      <ul class="lines">${state.cart.map((l, i) => {
        const p = byId[l.id];
        return `<li class="line">
          <button type="button" class="line-media cat-${p.cat}" data-edit="${i}" aria-label="${esc(nm(p))}">${tile(p)}</button>
          <div class="line-text">
            <strong>${esc(nm(p))}</strong>
            <small>${esc(p.unit)}${l.notes ? ` · “${esc(l.notes)}”` : ""}</small>
            <span class="line-price">${money(p.price * l.qty)}</span>
          </div>
          <div class="qty">
            <button type="button" data-line-dec="${i}" aria-label="${l.qty === 1 ? t("remove") : t("qtyMinus")}">${l.qty === 1 ? "🗑" : "−"}</button>
            <output>${l.qty}</output>
            <button type="button" data-line-inc="${i}" aria-label="${t("qtyPlus")}">+</button>
          </div>
        </li>`;
      }).join("")}</ul>`;
    const short = state.mode === "delivery" ? STORE.minOrder - tt.subtotal : 0;
    $("#cart-foot").innerHTML = `
      ${short > 0 ? `<div class="min-meter"><div style="width:${Math.min(100, (tt.subtotal / STORE.minOrder) * 100)}%"></div></div><p class="min-note">${t("cart.minLeft", money(short))}</p>` : ""}
      <div class="foot-row"><span>${t("cart.subtotal")}</span><strong>${money(tt.subtotal)}</strong></div>
      <button type="button" class="btn btn-block btn-lg" id="go-checkout" ${short > 0 ? "disabled" : ""}>${t("cart.checkout")}</button>`;
    $("#cart-clear").addEventListener("click", () => { const ids = state.cart.map((l) => l.id); state.cart = []; save(); ids.forEach(refreshCards); renderCartBadge(); renderCart(); });
    $("#go-checkout").addEventListener("click", openCheckout);
  }
  $("#cart-body").addEventListener("click", (e) => {
    const inc = e.target.closest("[data-line-inc]"), d = e.target.closest("[data-line-dec]"), ed = e.target.closest("[data-edit]");
    if (inc) { const l = state.cart[+inc.dataset.lineInc]; l.qty++; save(); afterCartChange(l.id); }
    else if (d) { const i = +d.dataset.lineDec, l = state.cart[i]; l.qty--; if (l.qty <= 0) state.cart.splice(i, 1); save(); afterCartChange(l.id); }
    else if (ed) { openProduct(state.cart[+ed.dataset.edit].id, +ed.dataset.edit); }
  });
  const openCart = () => { renderCart(); $("#cart-dialog").showModal(); };
  $("#cart-btn").addEventListener("click", openCart);
  $("#cartbar").addEventListener("click", openCart);
  $("#cart-close").addEventListener("click", () => $("#cart-dialog").close());

  // close dialogs when clicking the backdrop
  $$("dialog").forEach((d) => d.addEventListener("click", (e) => { if (e.target === d) d.close(); }));

  // ---------- checkout ----------
  function slots() {
    const out = []; const d = new Date(); d.setMinutes(d.getMinutes() + 60);
    d.setMinutes(d.getMinutes() < 30 ? 30 : 60, 0, 0);
    for (let i = 0; i < 46; i++) { out.push(new Date(d)); d.setMinutes(d.getMinutes() + 30); }
    return out;
  }
  const fmtSlot = (d) => d.toLocaleString(t("locale"), { weekday: "short", hour: "numeric", minute: "2-digit" });

  function openCheckout() {
    if ($("#cart-dialog").open) $("#cart-dialog").close();
    $("#co-zone").innerHTML = `<option value="">${t("top.chooseZone")}</option>` +
      STORE.zones.map((z) => `<option value="${z.id}">${esc(nm(z))} — ${money(z.fee)} · ${z.eta} ${t("min")}</option>`).join("");
    $("#co-zone").value = state.zone || "";
    $("#co-slot").innerHTML = slots().map((d) => `<option value="${d.toISOString()}">${fmtSlot(d)}</option>`).join("");
    $("#co-pay").innerHTML = STORE.payments.map((p) =>
      `<label class="choice"><input type="radio" name="pay" value="${p.id}" ${p.id === state.pay ? "checked" : ""}><span><strong>${esc(nm(p))}</strong></span></label>`).join("");
    const prev = ls.get("st-customer", {});
    ["name", "phone", "place", "room"].forEach((k) => { const el = $(`#co-${k}`); if (!el.value && prev[k]) el.value = prev[k]; });
    $("#co-error").textContent = "";
    renderCheckout();
    $("#checkout-dialog").showModal();
  }
  function renderCheckout() {
    const del = state.mode === "delivery";
    renderMode();
    $("#co-delivery-fields").classList.toggle("hidden", !del);
    $("#co-pickup-info").classList.toggle("hidden", del);
    $("#co-tip-sec").classList.toggle("hidden", !del);
    $("#co-slot").classList.toggle("hidden", state.when !== "later");
    const z = zoneObj();
    $("#co-asap-eta").textContent = del ? (z ? `${z.eta} ${t("min")}` : "") : `${STORE.pickupMinutes} ${t("min")}`;
    $("#co-cash-wrap").classList.toggle("hidden", state.pay !== "cash");
    $("#co-tips").innerHTML = [0, 10, 15, 20].map((p) =>
      `<button type="button" class="tip ${p === state.tipPct ? "on" : ""}" data-tip="${p}" aria-pressed="${p === state.tipPct}">${p ? `${p}%` : t("co.noTip")}${p ? `<small>${money((totals().subtotal * p) / 100)}</small>` : ""}</button>`).join("");
    const tt = totals();
    $("#co-items").innerHTML = state.cart.map((l) => {
      const p = byId[l.id];
      return `<li><span class="ci-q">${l.qty}×</span><span class="ci-n">${esc(nm(p))}${l.notes ? `<small>“${esc(l.notes)}”</small>` : ""}</span><span>${money(p.price * l.qty)}</span></li>`;
    }).join("");
    $("#co-totals").innerHTML = `
      <div><dt>${t("cart.subtotal")}</dt><dd>${money(tt.subtotal)}</dd></div>
      ${del ? `<div><dt>${t("co.delivery")}</dt><dd>${z ? money(tt.delivery) : "—"}</dd></div>
               <div><dt>${t("co.tip")}</dt><dd>${money(tt.tip)}</dd></div>` : ""}
      <div class="grand"><dt>${t("co.total")}</dt><dd>${money(tt.total)}<small>${usd(tt.total)}</small></dd></div>`;
    $("#co-age-wrap").classList.toggle("hidden", !hasAlcohol());
    $("#co-submit").textContent = t("co.place_order", money(tt.total));
  }
  $("#co-zone").addEventListener("change", (e) => { state.zone = e.target.value || null; save(); renderCheckout(); renderMode(); });
  $("#checkout-form").addEventListener("input", (e) => {
    if ($("#co-error").textContent) { $("#co-error").textContent = ""; e.target.removeAttribute("aria-invalid"); }
  });
  $("#checkout-form").addEventListener("change", (e) => {
    if (e.target.id === "co-age" && e.target.checked) $("#co-error").textContent = "";
    if (e.target.name === "when") { state.when = e.target.value; renderCheckout(); }
    if (e.target.name === "pay") { state.pay = e.target.value; renderCheckout(); }
  });
  $("#co-tips").addEventListener("click", (e) => { const b = e.target.closest("[data-tip]"); if (!b) return; state.tipPct = +b.dataset.tip; save(); renderCheckout(); });
  $("#co-back").addEventListener("click", () => { $("#checkout-dialog").close(); openCart(); });
  $("#co-loc").addEventListener("click", () => {
    const btn = $("#co-loc span");
    if (!navigator.geolocation) { btn.textContent = t("co.locErr"); return; }
    btn.textContent = "…";
    navigator.geolocation.getCurrentPosition(
      (pos) => { state.coords = { lat: pos.coords.latitude.toFixed(6), lng: pos.coords.longitude.toFixed(6) }; btn.textContent = t("co.locOk"); },
      () => { btn.textContent = t("co.locErr"); },
      { enableHighAccuracy: true, timeout: 10000 });
  });

  function validate() {
    const del = state.mode === "delivery";
    const tt = totals();
    const fail = (msg, el) => { $("#co-error").textContent = msg; if (el) { el.focus(); el.setAttribute("aria-invalid", "true"); } return false; };
    $$("#checkout-form [aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
    if (del && !state.zone) return fail(t("co.err.zone"), $("#co-zone"));
    if (del && tt.subtotal < STORE.minOrder) return fail(t("co.err.min", money(STORE.minOrder)));
    if (del && !$("#co-place").value.trim()) return fail(t("co.err.place"), $("#co-place"));
    if (!$("#co-name").value.trim()) return fail(t("co.err.name"), $("#co-name"));
    if ($("#co-phone").value.replace(/\D/g, "").length < 7) return fail(t("co.err.phone"), $("#co-phone"));
    if (hasAlcohol() && !$("#co-age").checked) return fail(t("co.err.age"), $("#co-age"));
    $("#co-error").textContent = "";
    return true;
  }

  function buildOrder() {
    const tt = totals(); const z = zoneObj();
    const slot = state.when === "later" ? $("#co-slot").value : null;
    return {
      id: `ST-${Date.now().toString(36).slice(-4).toUpperCase()}${Math.floor(Math.random() * 90 + 10)}`,
      createdAt: new Date().toISOString(),
      lang, mode: state.mode,
      zone: state.mode === "delivery" ? z?.id : null,
      zoneName: state.mode === "delivery" ? nm(z) : null,
      eta: state.mode === "delivery" ? z?.eta : STORE.pickupMinutes,
      place: $("#co-place").value.trim(), room: $("#co-room").value.trim(), driverNotes: $("#co-dnotes").value.trim(),
      coords: state.mode === "delivery" ? state.coords : null,
      scheduledFor: slot,
      customer: { name: $("#co-name").value.trim(), phone: $("#co-phone").value.trim() },
      payment: state.pay, paymentName: nm(STORE.payments.find((p) => p.id === state.pay)), cashFor: state.pay === "cash" ? $("#co-cash").value.trim() : "",
      items: state.cart.map((l) => ({ id: l.id, name: nm(byId[l.id]), unit: byId[l.id].unit, qty: l.qty, price: byId[l.id].price, notes: l.notes || "" })),
      ageConfirmed: hasAlcohol() ? $("#co-age").checked : null,
      itemCount: tt.items, subtotal: tt.subtotal, delivery: tt.delivery, tip: tt.tip, total: tt.total,
    };
  }

  function waText(o) {
    const L = (k) => T[o.lang][k];
    const m = (n) => `${STORE.currency} ${Math.round(n).toLocaleString(T[o.lang].locale)}`;
    const lines = [
      `*${L("wa.new")} ${o.id}* — ${STORE.name}`,
      `${L("wa.mode")}: ${o.mode === "delivery" ? L("wa.delivery") : L("wa.pickup")}`,
    ];
    if (o.mode === "delivery") {
      lines.push(`${L("wa.zone")}: ${o.zoneName}`, `${L("wa.place")}: ${o.place}`);
      if (o.room) lines.push(`${L("wa.room")}: ${o.room}`);
      if (o.coords) lines.push(`${L("wa.map")}: https://maps.google.com/?q=${o.coords.lat},${o.coords.lng}`);
      if (o.driverNotes) lines.push(`${L("wa.driverNotes")}: ${o.driverNotes}`);
    }
    lines.push(`${L("wa.when")}: ${o.scheduledFor ? new Date(o.scheduledFor).toLocaleString(T[o.lang].locale, { weekday: "short", hour: "numeric", minute: "2-digit" }) : L("co.asap")}`);
    lines.push(`${L("wa.client")}: ${o.customer.name} · ${o.customer.phone}`, "", `*${L("wa.items")}*`);
    o.items.forEach((i) => { lines.push(`• ${i.qty} × ${i.name} (${i.unit}) — ${m(i.price * i.qty)}`); if (i.notes) lines.push(`   ${L("wa.note")}: ${i.notes}`); });
    lines.push("", `${L("cart.subtotal")}: ${m(o.subtotal)}`);
    if (o.mode === "delivery") lines.push(`${L("co.delivery")}: ${m(o.delivery)}`, `${L("co.tip")}: ${m(o.tip)}`);
    lines.push(`*${L("co.total")}: ${m(o.total)}*`, `${L("wa.pay")}: ${o.paymentName}`);
    if (o.cashFor) lines.push(`${L("wa.cashFor")}: ${o.cashFor}`);
    if (o.ageConfirmed) lines.push(`✔ ${L("wa.ageOk")}`);
    return lines.join("\n");
  }
  const waUrl = (text) => `https://wa.me/${STORE.whatsapp}?text=${encodeURIComponent(text)}`;

  $("#checkout-form").addEventListener("submit", (e) => {
    e.preventDefault();
    if (!validate()) return;
    const order = buildOrder();
    // open WhatsApp synchronously (inside the click) so pop-up blockers allow it
    window.open(waUrl(waText(order)), "_blank", "noopener");
    if (STORE.orderEndpoint) {
      fetch(STORE.orderEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(order) }).catch(() => {});
    }
    ls.set("st-customer", { name: order.customer.name, phone: order.customer.phone, place: order.place, room: order.room });
    state.lastOrder = order; ls.set("st-last-order", order);
    const ids = state.cart.map((l) => l.id);
    state.cart = []; save(); ids.forEach(refreshCards); renderCartBadge();
    $("#checkout-dialog").close();
    openTrack();
  });

  // ---------- order status ----------
  function openTrack() {
    const o = state.lastOrder; if (!o) return;
    const del = o.mode === "delivery";
    const placed = new Date(o.createdAt).toLocaleTimeString(t("locale"), { hour: "numeric", minute: "2-digit" });
    const steps = [t("tr.s1"), t("tr.s2"), t("tr.s3"), del ? t("tr.s4d") : t("tr.s4p"), del ? t("tr.s5d") : t("tr.s5p")];
    const m = (n) => money(n);
    $("#track").innerHTML = `
      <header class="co-head">
        <button type="button" class="back" id="tr-close" aria-label="${t("close")}">×</button>
        <h2 id="tr-h">${t("tr.title")}</h2>
      </header>
      <div class="track-body">
        <div class="track-hero">
          <div class="track-check" aria-hidden="true">✓</div>
          <p class="track-id">${t("tr.order")} <strong>${esc(o.id)}</strong></p>
          <p class="track-eta">${del ? t("tr.eta") : t("tr.ready")}: <strong>${o.scheduledFor ? fmtSlot(new Date(o.scheduledFor)) : `${esc(o.eta)} ${t("min")}`}</strong></p>
        </div>
        <ol class="timeline">
          ${steps.map((s, i) => `<li class="${i === 0 ? "done" : i === 1 ? "next" : ""}"><span class="dot"></span><div><strong>${s}</strong>${i === 0 ? `<small>${placed}</small>` : ""}</div></li>`).join("")}
        </ol>
        <p class="info">${t("tr.note")}</p>
        <div class="track-actions">
          <a class="btn" href="${waUrl(waText(o))}" target="_blank" rel="noopener">${t("tr.resend")}</a>
          <a class="btn btn-ghost" href="tel:${STORE.phone}">${t("tr.call")}</a>
        </div>
        <section class="track-card">
          <h3>${del ? t("tr.to") : t("tr.pickup")}</h3>
          <p>${del ? `${esc(o.place)}${o.room ? ` · ${esc(o.room)}` : ""}<br><small>${esc(o.zoneName)}</small>` : "Saint Tropez Market 24/7 · Downtown Punta Cana"}</p>
        </section>
        <section class="track-card">
          <h3>${t("tr.items")}</h3>
          <ul class="co-items">${o.items.map((i) => `<li><span class="ci-q">${i.qty}×</span><span class="ci-n">${esc(i.name)}</span><span>${m(i.price * i.qty)}</span></li>`).join("")}</ul>
          <dl class="totals">
            <div><dt>${t("cart.subtotal")}</dt><dd>${m(o.subtotal)}</dd></div>
            ${del ? `<div><dt>${t("co.delivery")}</dt><dd>${m(o.delivery)}</dd></div><div><dt>${t("co.tip")}</dt><dd>${m(o.tip)}</dd></div>` : ""}
            <div class="grand"><dt>${t("co.total")}</dt><dd>${m(o.total)}</dd></div>
            <div><dt>${t("co.s4")}</dt><dd>${esc(o.paymentName)}</dd></div>
          </dl>
        </section>
        <button type="button" class="btn btn-ghost btn-block" id="tr-new">${t("tr.new")}</button>
      </div>`;
    $("#tr-close").addEventListener("click", () => $("#track-dialog").close());
    $("#tr-new").addEventListener("click", () => { $("#track-dialog").close(); window.scrollTo({ top: 0, behavior: "smooth" }); });
    if (!$("#track-dialog").open) $("#track-dialog").showModal();
    renderActiveOrder();
  }
  function renderActiveOrder() {
    const o = state.lastOrder;
    const recent = o && Date.now() - new Date(o.createdAt).getTime() < 6 * 3600 * 1000;
    $("#active-order-btn").classList.toggle("hidden", !recent);
  }
  $("#active-order-btn").addEventListener("click", openTrack);

  // ---------- toast ----------
  let toastTimer;
  function toast(msg) {
    const el = $("#toast"); el.textContent = msg; el.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 1600);
  }

  // ---------- language ----------
  $("#lang-toggle").addEventListener("click", () => {
    lang = lang === "en" ? "es" : "en"; ls.set("st-lang", lang); renderAll();
    if ($("#checkout-dialog").open) openCheckout();
    if ($("#track-dialog").open) openTrack();
  });

  // ---------- boot ----------
  function renderAll() {
    applyStatic(); renderMode(); renderCatbar(); renderShop(); observeShelves(); renderCartBadge(); renderActiveOrder();
    if ($("#cart-dialog").open) renderCart();
  }
  $("#wa-link").href = `https://wa.me/${STORE.whatsapp}`;
  $("#year").textContent = new Date().getFullYear();
  renderAll();
})();
