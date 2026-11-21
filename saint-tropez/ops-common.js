/* Shared bits for the staff and driver screens: language, login gate, helpers. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const lsGet = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };
  let lang = lsGet("st-ops-lang") || ((navigator.language || "es").startsWith("en") ? "en" : "es");

  const OPS = {
    $, lsGet, lsSet,
    get lang() { return lang; },
    t: (k, ...a) => { const v = T[lang][k] ?? T.es[k] ?? k; return typeof v === "function" ? v(...a) : v; },
    esc: (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
    money: (n) => `${STORE.currency} ${Math.round(n).toLocaleString(T[lang].locale)}`,
    time: (iso) => new Date(iso).toLocaleTimeString(T[lang].locale, { hour: "numeric", minute: "2-digit" }),
    itemName: (i) => (lang === "en" ? i.name_en : i.name_es) || i.name_es || i.name,
    waLink: (phone, text = "") => `https://wa.me/${String(phone).replace(/\D/g, "")}${text ? `?text=${encodeURIComponent(text)}` : ""}`,
    applyStatic() {
      document.documentElement.lang = lang;
      document.querySelectorAll("[data-i18n]").forEach((el) => { const v = T[lang][el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
      document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = OPS.t(el.dataset.i18nPh); });
      const b = $("#lang-toggle"); if (b) { b.textContent = lang === "en" ? "ES" : "EN"; b.setAttribute("aria-label", lang === "en" ? "Cambiar a español" : "Switch to English"); }
    },
    onLang(cb) {
      $("#lang-toggle")?.addEventListener("click", () => { lang = lang === "en" ? "es" : "en"; lsSet("st-ops-lang", lang); OPS.applyStatic(); cb(); });
    },

    /* Shows the login form until a valid staff member is signed in, then calls onReady(me). */
    async gate(onReady) {
      const API = window.ST_API?.available ? window.ST_API : null;
      const login = $("#login"), app = $("#app"), err = $("#login-error");
      OPS.applyStatic();
      if (!API) { login.classList.remove("hidden"); err.textContent = OPS.t("ops.offline"); return; }
      const enter = async () => {
        const me = await API.me().catch(() => null);
        if (!me) return false;
        login.classList.add("hidden"); app.classList.remove("hidden");
        $("#me-name").textContent = me.name;
        onReady(me);
        return true;
      };
      $("#signout")?.addEventListener("click", async () => { await API.signOut(); location.reload(); });
      if (await API.session().catch(() => null)) { if (await enter()) return; }
      login.classList.remove("hidden");
      $("#login-form").addEventListener("submit", async (e) => {
        e.preventDefault(); err.textContent = "";
        const btn = $("#login-form button"); btn.disabled = true;
        try {
          await API.signIn($("#login-email").value.trim(), $("#login-password").value);
          if (!(await enter())) { err.textContent = OPS.t("ops.notStaff"); await API.signOut(); }
        } catch (ex) {
          err.textContent = /fetch|network/i.test(String(ex?.message)) ? OPS.t("ops.offline") : OPS.t("ops.badLogin");
        } finally { btn.disabled = false; }
      });
    },
  };
  window.OPS = OPS;
})();
