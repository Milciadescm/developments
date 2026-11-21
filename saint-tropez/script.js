// ===== Store configuration — edit these values =====
const STORE = {
  whatsapp: "000000000000", // international format, digits only (e.g. 595981123456)
  currency: "$",
  // 0 = Sunday … 6 = Saturday. Times in 24h "HH:MM".
  hours: [
    { day: "Sunday",    open: "08:00", close: "13:00" },
    { day: "Monday",    open: "07:00", close: "21:00" },
    { day: "Tuesday",   open: "07:00", close: "21:00" },
    { day: "Wednesday", open: "07:00", close: "21:00" },
    { day: "Thursday",  open: "07:00", close: "21:00" },
    { day: "Friday",    open: "07:00", close: "21:30" },
    { day: "Saturday",  open: "07:00", close: "21:30" },
  ],
};

// Example offers — replace weekly.
const OFFERS = [
  { name: "Tomatoes",          unit: "per kg",       now: 1.49, was: 2.10, icon: "🍅", cat: "fresh" },
  { name: "Fresh baguette",    unit: "each",         now: 0.89, was: 1.20, icon: "🥖", cat: "fresh" },
  { name: "Beef sirloin",      unit: "per kg",       now: 9.90, was: 12.50, icon: "🥩", cat: "fresh" },
  { name: "Brie cheese",       unit: "200 g",        now: 2.99, was: 3.80, icon: "🧀", cat: "fresh" },
  { name: "Extra virgin olive oil", unit: "1 L",     now: 6.49, was: 8.20, icon: "🫒", cat: "pantry" },
  { name: "Spaghetti",         unit: "500 g",        now: 0.99, was: 1.35, icon: "🍝", cat: "pantry" },
  { name: "Rosé wine",         unit: "750 ml",       now: 7.90, was: 9.90, icon: "🍷", cat: "drinks" },
  { name: "Orange juice",      unit: "1 L",          now: 1.79, was: 2.40, icon: "🧃", cat: "drinks" },
];

// ===== Mobile menu =====
const toggle = document.querySelector(".nav-toggle");
const menu = document.getElementById("menu");
toggle.addEventListener("click", () => {
  const open = menu.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});
menu.addEventListener("click", (e) => {
  if (e.target.tagName === "A") {
    menu.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  }
});

// ===== Opening hours =====
const toMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
const now = new Date();
const todayIdx = now.getDay();
const tbody = document.querySelector("#hours-table tbody");
// Show Monday first
[1, 2, 3, 4, 5, 6, 0].forEach((i) => {
  const h = STORE.hours[i];
  const tr = document.createElement("tr");
  if (i === todayIdx) tr.className = "today";
  tr.innerHTML = `<td>${h.day}${i === todayIdx ? " (today)" : ""}</td><td>${h.open} – ${h.close}</td>`;
  tbody.appendChild(tr);
});
const t = STORE.hours[todayIdx];
const mins = now.getHours() * 60 + now.getMinutes();
const isOpen = mins >= toMin(t.open) && mins < toMin(t.close);
document.getElementById("today-status").textContent = isOpen
  ? `Open now · until ${t.close}`
  : `Closed now · opens ${mins < toMin(t.open) ? t.open : STORE.hours[(todayIdx + 1) % 7].open}`;

// ===== Offers =====
const grid = document.getElementById("offer-grid");
const fmt = (n) => STORE.currency + n.toFixed(2);
function renderOffers(filter = "all") {
  grid.innerHTML = OFFERS.filter((o) => filter === "all" || o.cat === filter)
    .map((o) => {
      const pct = Math.round((1 - o.now / o.was) * 100);
      return `<article class="offer">
        <div class="offer-img" aria-hidden="true"><span class="badge">-${pct}%</span>${o.icon}</div>
        <div class="offer-body">
          <h3>${o.name}</h3>
          <p class="unit">${o.unit}</p>
          <p class="price"><span class="now">${fmt(o.now)}</span><span class="was">${fmt(o.was)}</span></p>
        </div>
      </article>`;
    }).join("");
}
renderOffers();
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((c) => {
      c.classList.toggle("active", c === chip);
      c.setAttribute("aria-selected", String(c === chip));
    });
    renderOffers(chip.dataset.filter);
  });
});

// Offer validity: current Monday – Sunday
const monday = new Date(now); monday.setDate(now.getDate() - ((todayIdx + 6) % 7));
const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6);
const d = (x) => x.toLocaleDateString(undefined, { day: "numeric", month: "short" });
document.getElementById("offer-dates").textContent = `${d(monday)} – ${d(sunday)}`;

// ===== WhatsApp links =====
const waText = encodeURIComponent("Hello Saint Tropez! I'd like to place an order:\n");
const waUrl = `https://wa.me/${STORE.whatsapp}?text=${waText}`;
["whatsapp-link", "whatsapp-link-2"].forEach((id) => { document.getElementById(id).href = waUrl; });

// ===== Contact form (sends via WhatsApp until a backend/email service is connected) =====
document.getElementById("contact-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.target;
  let ok = true;
  form.querySelectorAll("[required]").forEach((f) => {
    const bad = !f.value.trim();
    f.classList.toggle("invalid", bad);
    if (bad) ok = false;
  });
  const note = document.getElementById("form-note");
  if (!ok) { note.textContent = "Please fill in all fields."; return; }
  const msg = `Name: ${form.name.value}\nContact: ${form.reach.value}\n\n${form.message.value}`;
  window.open(`https://wa.me/${STORE.whatsapp}?text=${encodeURIComponent(msg)}`, "_blank", "noopener");
  note.textContent = "Thanks! Your message is ready to send in WhatsApp.";
  form.reset();
});

document.getElementById("year").textContent = now.getFullYear();
