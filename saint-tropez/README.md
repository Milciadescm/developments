# Saint Tropez Market 24/7 — online ordering + live delivery tracking

**More than a Market… A Lifestyle.** Downtown Punta Cana, open 24/7.

Static website (HTML/CSS/JS, no build step) backed by **Supabase** (database, logins, real-time updates).
Upload the `saint-tropez/` folder to any static host (Vercel, Netlify, GitHub Pages). Spanish and English throughout.

## The four screens
| Page | Who | What it does |
|---|---|---|
| `index.html` | Customers | Delivery-app style shop: categories, search, cart, checkout with a **map pin** for the exact villa/hotel door, delivery or pickup, time, payment, tip, 18+ check. |
| `track.html?t=…` | Customers | **Live tracking**: full-screen map with the store, the customer's pin and the **driver moving in real time**, arrival time in minutes, progress bar (sent → confirmed → preparing → on the way → delivered), driver card, call/WhatsApp buttons, shareable link. |
| `staff.html` | Store team (login) | Orders arrive instantly with a **sound alert** and browser notification. Buttons: Confirm → Start preparing → Ready (pickup) / Mark delivered; cancel. Call, WhatsApp, map and tracking links per order. |
| `driver.html` | Drivers (login, on their phone) | List of deliveries ready to go → **Take & go** → the phone shares its GPS every 5 s (screen kept awake) → Navigate (Google Maps), call customer, amount to collect → **Delivered**. Two drivers can't take the same order. |

## How the delivery follow-up works
1. Customer places the order → saved in the database (prices and totals are calculated **on the server** from `st_products`, so they can't be tampered with) → customer lands on their tracking page.
2. Staff confirm and prepare → the customer's page updates instantly.
3. A driver taps **Take & go** → their phone's location is written to the order every few seconds → Supabase pushes each update to that customer's tracking page, where the scooter glides along the map and the ETA counts down.
4. Driver taps **Delivered** → the customer sees "Delivered", the order moves to "Completed today".

Each tracking link contains a random, unguessable code; customers can only see their own order. Customers' phone numbers are never shown on the tracking page.
If the server can't be reached, the shop falls back to sending the order by WhatsApp.

## Supabase setup (already done in project `Cuetoandco`)
All objects are prefixed `st_` and kept separate from anything else in the project.
- Tables: `st_products`, `st_zones`, `st_orders`, `st_staff` — with row-level security.
- Functions: `st_place_order` (customers), `st_track` (tracking link). Live updates via Supabase Realtime.
- SQL is in `supabase/migrations/`, starting data in `supabase/seed.sql`.

### Before launch
1. **Create staff & driver accounts** — follow `supabase/add-staff.sql` (Authentication → Add user, then one SQL line per person).
2. **Products & prices** — edit them in the Supabase Table Editor (`st_products`, `st_zones`). The website reads them live; `catalog.js` is only the offline fallback.
3. **Store position** — set the exact container location in `config.js` → `storeLocation`.
4. **Contact** — WhatsApp/phone in `catalog.js` (`STORE.whatsapp`, `STORE.phone`) and `[…]` placeholders in `index.html`.
5. **Supabase Auth → URL configuration** — set the site URL to the live domain.

## Prices, ITBIS and fiscal invoices (NCF)
- **All prices include ITBIS (18%)** — products, delivery fees and the minimum order. The site says "ITBIS incluido" on product, cart, checkout, tracking and invoice. Tips carry no ITBIS.
- Per-product rate: `st_products.itbis_rate` (default 18). Set 0 for exempt items after confirming with your accountant.
- At checkout the customer chooses **Consumidor final (B02)** or **Crédito fiscal (B01)** with RNC (9 digits) or cédula (11) and razón social.
- `invoice.html?t=…` shows every item: quantity, description (brand + product), unit price, ITBIS, amount, delivery, taxable subtotal, ITBIS total, tip and total; printable / save as PDF. Linked from the tracking page and the staff board.
- **NCF numbers**: load your DGII-authorised ranges with `supabase/ncf-setup.sql`. The NCF is assigned automatically when an order is marked delivered (or with "Emitir comprobante" on the staff board). Until a range is loaded the invoice shows as a pro-forma.
- Business name, RNC and address printed on invoices: `catalog.js → STORE.legal`.

## Catalogue: Dominican identity + international brands
148 products with `brand` and `origin` (🇩🇴 made in DR or the import country): "Hecho en RD" and "Selección internacional" showcases, and a Todo / Dominicano / Importado filter. Product tiles show the brand name and an icon; add real photos with `img` (distributors usually provide them). Verify the origin of each presentation: some international brands are also made or packed locally.

## Files
`index.html` `app.js` (shop) · `track.html` `track.js` (live tracking) · `staff.html` `staff.js` · `driver.html` `driver.js` · `ops-common.js` (login for staff/drivers)
`api.js` (Supabase calls) · `map.js` (map, pins, ETA) · `config.js` (Supabase URL + public key, map settings) · `catalog.js` (store settings, fallback catalogue) · `i18n.js` (ES/EN text)
`styles.css` (brand, shop) · `ops.css` (tracking, staff, driver) · `images/` · `supabase/`

Maps: OpenStreetMap tiles via Leaflet (free; for heavy traffic switch `config.js → tiles` to a paid tile provider such as MapTiler or Stadia).

## Not included yet
Online card payments (needs a payment provider). ETA is an estimate from straight-line distance (no road routing).
