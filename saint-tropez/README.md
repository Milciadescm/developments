# Saint Tropez Market 24/7 — online ordering website

**More than a Market… A Lifestyle.** Downtown Punta Cana, open 24/7.

A static website (HTML/CSS/JS, no build step, no server needed) where customers browse products and order for **delivery** (hotel, villa, Airbnb, yacht) or **pickup**, in a delivery-app style layout. Open `index.html` in a browser, or upload the `saint-tropez/` folder to any static host (Vercel, Netlify, GitHub Pages).

## How ordering works
1. Customer chooses **Delivery** or **Pickup** and their delivery area (fee and time depend on the area).
2. Browses by category or searches, taps **+** to add, or opens a product for quantity and special instructions.
3. Cart → **Checkout**: hotel/villa/address, room, *share my location* (adds a Google Maps pin), ASAP or a scheduled time, name and WhatsApp, payment method (cash, card on delivery, transfer), tip.
4. **Place order** sends the full, formatted order to the store's WhatsApp, and the customer sees an order-status screen (sent → confirmed → preparing → on the way → delivered).
5. Staff confirm and update the customer on WhatsApp.

Checks built in: delivery minimum, required fields, and an 18+ confirmation when the cart has alcohol.

## Set up before going live (`catalog.js`)
- `STORE.whatsapp` / `STORE.phone` — the number that **receives orders**.
- `STORE.zones` — delivery areas, fees (RD$) and times.
- `STORE.minOrder`, `STORE.usdRate`, `STORE.payments`.
- `PRODUCTS` — real products and prices. Add a photo with `img: "images/products/name.webp"`; otherwise the emoji tile is shown.
- `STORE.orderEndpoint` (optional) — a URL that receives each order as JSON, for a future order dashboard (e.g. Supabase, Google Sheets, Zapier).

Also in `index.html`: street/unit, phone, social links (look for `[…]`).

## Files
- `index.html` — page structure · `styles.css` — design (dark green + gold brand) · `app.js` — cart, checkout, order sending
- `catalog.js` — store settings and products · `i18n.js` — Spanish/English text (follows the visitor's browser; ES/EN switch in the header)
- `images/` — `emblem.svg` (vector logo emblem, also the favicon), storefront photos
- `images/concepts/` — earlier concept images and the brand board, not used on the page

Images are AI-generated illustrations — replace them with real photos of the store.

## Not included yet
Online card payment and a live staff dashboard need a backend (payment provider + database). The `orderEndpoint` hook is where that plugs in.
