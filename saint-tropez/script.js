// ===== Store configuration — edit these values =====
const STORE = {
  whatsapp: "18090000000", // international format, digits only
  currency: "RD$",
  // 0 = Sunday … 6 = Saturday. 24h "HH:MM". Use "24:00" for midnight.
  hours: [
    { open: "08:00", close: "24:00" }, // Sunday
    { open: "07:00", close: "23:00" }, // Monday
    { open: "07:00", close: "23:00" },
    { open: "07:00", close: "23:00" },
    { open: "07:00", close: "24:00" },
    { open: "07:00", close: "24:00" }, // Friday
    { open: "08:00", close: "24:00" }, // Saturday
  ],
};

// Example offers — replace weekly.
const OFFERS = [
  { es: "Tomates",                  en: "Tomatoes",             unit: "lb",     now: 75,   was: 95,   icon: "🍅", cat: "fresh" },
  { es: "Baguette recién horneado", en: "Fresh baguette",       unit: "1 u",    now: 95,   was: 125,  icon: "🥖", cat: "fresh" },
  { es: "Queso brie",               en: "Brie cheese",          unit: "200 g",  now: 395,  was: 495,  icon: "🧀", cat: "fresh" },
  { es: "Jamón serrano",            en: "Serrano ham",          unit: "100 g",  now: 325,  was: 410,  icon: "🥓", cat: "fresh" },
  { es: "Aceite de oliva extra virgen", en: "Extra virgin olive oil", unit: "1 L", now: 690, was: 850, icon: "🫒", cat: "pantry" },
  { es: "Pasta spaghetti",          en: "Spaghetti",            unit: "500 g",  now: 89,   was: 115,  icon: "🍝", cat: "pantry" },
  { es: "Vino rosado",              en: "Rosé wine",            unit: "750 ml", now: 895,  was: 1150, icon: "🍷", cat: "drinks" },
  { es: "Cerveza nacional (6 pack)", en: "Local beer (6-pack)", unit: "6 × 355 ml", now: 540, was: 650, icon: "🍺", cat: "drinks" },
];

// ===== Language =====
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};
const ES = {}; // Spanish originals captured from the HTML
document.querySelectorAll("[data-i18n]").forEach((el) => { ES[el.dataset.i18n] = el.textContent; });
document.querySelectorAll("[data-i18n-alt]").forEach((el) => { ES[el.dataset.i18nAlt] = el.alt; });
document.querySelectorAll("[data-i18n-aria]").forEach((el) => { ES[el.dataset.i18nAria] = el.getAttribute("aria-label"); });

let lang = store.get("st-lang") || (navigator.language || "es").slice(0, 2);
if (lang !== "en") lang = "es";
const L = () => UI[lang];
const now = new Date();

function applyLang() {
  const dict = lang === "en" ? EN : ES;
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { const v = dict[el.dataset.i18n]; if (v) el.textContent = v; });
  document.querySelectorAll("[data-i18n-alt]").forEach((el) => { const v = dict[el.dataset.i18nAlt]; if (v) el.alt = v; });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => { const v = dict[el.dataset.i18nAria]; if (v) el.setAttribute("aria-label", v); });
  const btn = document.getElementById("lang-toggle");
  btn.textContent = lang === "en" ? "ES" : "EN";
  btn.setAttribute("aria-label", lang === "en" ? "Cambiar a español" : "Switch to English");
  renderHours(); renderOffers(currentFilter); renderDates(); setWhatsApp();
}
document.getElementById("lang-toggle").addEventListener("click", () => {
  lang = lang === "en" ? "es" : "en"; store.set("st-lang", lang); applyLang();
});

// ===== Mobile menu =====
const toggle = document.querySelector(".nav-toggle");
const menu = document.getElementById("menu");
toggle.addEventListener("click", () => {
  const open = menu.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});
menu.addEventListener("click", (e) => {
  if (e.target.closest("a")) { menu.classList.remove("open"); toggle.setAttribute("aria-expanded", "false"); }
});

// ===== Header style on scroll =====
const header = document.querySelector(".site-header");
const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 40);
window.addEventListener("scroll", onScroll, { passive: true }); onScroll();

// ===== Opening hours =====
const toMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
const show = (t) => (t === "24:00" ? "12:00 am" : t);
function renderHours() {
  const todayIdx = now.getDay();
  const tbody = document.querySelector("#hours-table tbody");
  tbody.innerHTML = "";
  [1, 2, 3, 4, 5, 6, 0].forEach((i) => {
    const h = STORE.hours[i];
    const tr = document.createElement("tr");
    if (i === todayIdx) tr.className = "today";
    tr.innerHTML = `<td>${L().days[i]}${i === todayIdx ? ` <em>(${L().today})</em>` : ""}</td><td>${h.open} – ${show(h.close)}</td>`;
    tbody.appendChild(tr);
  });
  const t = STORE.hours[todayIdx];
  const mins = now.getHours() * 60 + now.getMinutes();
  const open = mins >= toMin(t.open) && mins < toMin(t.close);
  document.getElementById("today-status").textContent = open
    ? L().openUntil(show(t.close))
    : L().closedOpens(mins < toMin(t.open) ? t.open : STORE.hours[(todayIdx + 1) % 7].open);
}

// ===== Offers =====
let currentFilter = "all";
const grid = document.getElementById("offer-grid");
const fmt = (n) => `${STORE.currency} ${n.toLocaleString(L().locale)}`;
function renderOffers(filter = "all") {
  currentFilter = filter;
  grid.innerHTML = OFFERS.filter((o) => filter === "all" || o.cat === filter).map((o) => {
    const pct = Math.round((1 - o.now / o.was) * 100);
    return `<article class="offer">
      <div class="offer-img" aria-hidden="true"><span class="badge">-${pct}%</span>${o.icon}</div>
      <div class="offer-body">
        <h3>${o[lang]}</h3>
        <p class="unit">${o.unit}</p>
        <p class="price"><span class="now">${fmt(o.now)}</span><span class="was">${fmt(o.was)}</span></p>
      </div>
    </article>`;
  }).join("");
}
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((c) => {
      c.classList.toggle("active", c === chip);
      c.setAttribute("aria-selected", String(c === chip));
    });
    renderOffers(chip.dataset.filter);
  });
});
function renderDates() {
  const monday = new Date(now); monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6);
  const d = (x) => x.toLocaleDateString(L().locale, { day: "numeric", month: "short" });
  document.getElementById("offer-dates").textContent = `${d(monday)} – ${d(sunday)}`;
}

// ===== WhatsApp =====
function setWhatsApp() {
  const url = `https://wa.me/${STORE.whatsapp}?text=${encodeURIComponent(L().wa)}`;
  ["whatsapp-link", "whatsapp-link-2"].forEach((id) => { document.getElementById(id).href = url; });
  document.querySelectorAll('.hero-actions a[href="#delivery"]').forEach((a) => { a.href = url; a.target = "_blank"; a.rel = "noopener"; });
}

// ===== Contact form → WhatsApp (until an email backend is connected) =====
document.getElementById("contact-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.target;
  let ok = true;
  form.querySelectorAll("[required]").forEach((f) => {
    const bad = !f.value.trim();
    f.classList.toggle("invalid", bad);
    f.setAttribute("aria-invalid", String(bad));
    if (bad) ok = false;
  });
  const note = document.getElementById("form-note");
  if (!ok) { note.textContent = L().fill; return; }
  const msg = `${L().name}: ${form.name.value}\n${L().contact}: ${form.reach.value}\n\n${form.message.value}`;
  window.open(`https://wa.me/${STORE.whatsapp}?text=${encodeURIComponent(msg)}`, "_blank", "noopener");
  note.textContent = L().sent;
  form.reset();
});

document.getElementById("year").textContent = now.getFullYear();
applyLang();
