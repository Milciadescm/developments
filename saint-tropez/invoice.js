/* Invoice / fiscal receipt: every item with unit price, ITBIS and total; NCF when issued. */
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const API = window.ST_API?.available ? window.ST_API : null;
  const params = new URLSearchParams(location.search);
  const token = params.get("t");
  const lsGet = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };
  let lang = lsGet("st-lang") || ((navigator.language || "es").startsWith("en") ? "en" : "es");
  const t = (k, ...a) => { const v = T[lang][k] ?? T.es[k] ?? k; return typeof v === "function" ? v(...a) : v; };
  const m2 = (n) => `${STORE.currency} ${(+n || 0).toLocaleString(t("locale"), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const r2 = (n) => Math.round(n * 100) / 100;
  let order = null;

  function applyStatic() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { const v = T[lang][el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
    $("#lang-toggle").textContent = lang === "en" ? "ES" : "EN";
    $("#inv-back").href = token ? `track.html?t=${encodeURIComponent(token)}` : "index.html";
  }
  $("#lang-toggle").addEventListener("click", () => { lang = lang === "en" ? "es" : "en"; lsSet("st-lang", lang); applyStatic(); if (order) render(); });
  $("#inv-print").addEventListener("click", () => window.print());

  const payName = (id) => { const p = STORE.payments.find((x) => x.id === id); return p ? (lang === "en" ? p.en : p.es) : id; };
  const itemName = (i) => [i.brand, (lang === "en" ? i.name_en : i.name_es) || i.name_es].filter(Boolean).join(" · ");

  function render() {
    const o = order;
    const L = STORE.legal || {};
    const credit = o.invoice_type === "credito_fiscal";
    const issued = !!o.ncf;
    const fee = +o.delivery_fee || 0, tip = +o.tip || 0;
    const rate = STORE.itbisRate ?? 18;
    const feeItbis = r2((fee * rate) / (100 + rate));
    const lines = (o.items || []).map((i) => {
      const total = i.total != null ? +i.total : +i.price * i.qty;
      const r = i.itbis_rate != null ? +i.itbis_rate : rate;
      const itbis = i.itbis != null ? +i.itbis : r2((total * r) / (100 + r));
      return { ...i, total, itbis, rate: r, unitNet: r2((+i.price * 100) / (100 + r)) };
    });
    const itbisTotal = o.itbis_total != null && +o.itbis_total > 0 ? +o.itbis_total : r2(lines.reduce((n, l) => n + l.itbis, 0) + feeItbis);
    const goodsTotal = lines.reduce((n, l) => n + l.total, 0);
    const taxable = r2(goodsTotal + fee - itbisTotal);
    const date = new Date(o.invoiced_at || o.created_at);
    const title = issued
      ? (credit ? t("inv.titleCredit") : t("inv.titleConsumer"))
      : t("inv.titleDraft");

    $("#invoice").innerHTML = `
      <header class="inv-head">
        <div class="inv-brand">
          <img src="images/emblem.svg" alt="" width="96" height="45">
          <div>
            <strong>${esc(L.name || "Saint Tropez Market 24/7")}</strong>
            <span>RNC: ${esc(L.rnc || "—")}</span>
            <span>${esc(L.address || "")}</span>
            <span>${esc(L.phone || "")}</span>
          </div>
        </div>
        <div class="inv-doc">
          <h1>${title}</h1>
          ${issued
            ? `<dl>
                 <div><dt>NCF</dt><dd class="ncf">${esc(o.ncf)}</dd></div>
                 ${o.ncf_expires_on ? `<div><dt>${t("inv.validUntil")}</dt><dd>${new Date(o.ncf_expires_on + "T12:00:00").toLocaleDateString(t("locale"))}</dd></div>` : ""}
               </dl>`
            : `<p class="inv-pending">${t("inv.pending")}</p>`}
          <dl>
            <div><dt>${t("inv.date")}</dt><dd>${date.toLocaleString(t("locale"), { dateStyle: "medium", timeStyle: "short" })}</dd></div>
            <div><dt>${t("inv.order")}</dt><dd>${esc(o.code)}</dd></div>
          </dl>
        </div>
      </header>

      <section class="inv-client">
        <h2>${t("inv.client")}</h2>
        ${credit
          ? `<p><strong>${esc(o.customer_legal_name || "")}</strong><br>RNC / Cédula: ${esc(o.customer_rnc || "")}</p>
             <p class="muted">${t("inv.attn")}: ${esc(o.customer_name || "")}</p>`
          : `<p><strong>${esc(o.customer_name || t("inv.finalConsumer"))}</strong><br>${t("inv.finalConsumer")}</p>`}
        <p class="muted">${o.mode === "delivery" ? `${t("lt.deliverTo")}: ${esc(o.place || "")}${o.room ? ` · ${esc(o.room)}` : ""} — ${esc(o.zone_name || "")}` : t("tr.pickup")}</p>
      </section>

      <div class="inv-table-wrap">
        <table class="inv-table">
          <thead>
            <tr><th class="num">${t("inv.qty")}</th><th>${t("inv.desc")}</th><th class="num">${t("inv.unit")}</th><th class="num">ITBIS</th><th class="num">${t("inv.amount")}</th></tr>
          </thead>
          <tbody>
            ${lines.map((l) => `
              <tr>
                <td class="num">${l.qty}</td>
                <td>${esc(itemName(l))}<small>${esc(l.unit || "")}${l.rate !== rate ? ` · ITBIS ${l.rate}%` : ""}${l.notes ? ` · “${esc(l.notes)}”` : ""}</small></td>
                <td class="num">${m2(l.price)}</td>
                <td class="num">${m2(l.itbis)}</td>
                <td class="num">${m2(l.total)}</td>
              </tr>`).join("")}
            ${fee ? `
              <tr class="svc">
                <td class="num">1</td><td>${t("inv.delivery")}<small>${esc(o.zone_name || "")}</small></td>
                <td class="num">${m2(fee)}</td><td class="num">${m2(feeItbis)}</td><td class="num">${m2(fee)}</td>
              </tr>` : ""}
          </tbody>
        </table>
      </div>

      <section class="inv-totals">
        <dl>
          <div><dt>${t("inv.taxable")}</dt><dd>${m2(taxable)}</dd></div>
          <div><dt>ITBIS (${rate}%)</dt><dd>${m2(itbisTotal)}</dd></div>
          <div class="sub"><dt>${t("inv.totalWithTax")}</dt><dd>${m2(goodsTotal + fee)}</dd></div>
          ${tip ? `<div><dt>${t("inv.tip")}</dt><dd>${m2(tip)}</dd></div>` : ""}
          <div class="grand"><dt>${t("inv.total")}</dt><dd>${m2(o.total)}</dd></div>
        </dl>
        <p class="muted">${t("inv.pricesIncl")}</p>
        <p class="muted">${t("inv.payment")}: ${esc(payName(o.payment))}</p>
      </section>

      <footer class="inv-foot">
        <p class="sig">More than a Market… A Lifestyle</p>
        <p class="muted">${issued ? t("inv.validNote") : t("inv.draftNote")}</p>
      </footer>`;
    document.title = `${title} ${o.ncf || o.code} · Saint Tropez Market 24/7`;
  }

  async function load() {
    applyStatic();
    if (!token || !API) { $("#inv-loading").textContent = API ? t("lt.notFound") : t("ops.offline"); return; }
    try {
      order = await API.track(token);
      if (!order) throw new Error("not found");
      render();
      if (!order.ncf) {
        try { API.subscribeOrder(token, (patch) => { order = { ...order, ...patch }; render(); }); } catch { /* ignore */ }
      }
    } catch { $("#inv-loading").textContent = t("lt.notFound"); }
  }
  load();
})();
