# Saint Tropez Supermarket — Downtown Punta Cana

Static website (HTML/CSS/JS, no build step). Open `index.html` in a browser, or deploy the `saint-tropez/` folder to any static host (Vercel, Netlify, GitHub Pages).

**Look:** black & gold luxury boutique (crystal chandeliers, gourmet deli), set in the Downtown Punta Cana nightlife plaza.
**Languages:** Spanish (default) and English — follows the visitor's browser language, with an ES/EN switch in the header.

## Sections
Hero (night storefront) · Experience (deli, wine, cold drinks, ready-to-eat) · Weekly offers (filterable, RD$) · Delivery to hotels/villas via WhatsApp · Day & night storefront · Hours & map · Contact (form opens WhatsApp) · Footer

## To customize
- `script.js` → `STORE` (WhatsApp number, currency, opening hours) and `OFFERS` (weekly deals, ES + EN names).
- `index.html` → bracketed placeholders: street/local, phone, email, delivery hours, minimum order, social links.
- `i18n.js` → English text. Spanish text lives directly in `index.html`.
- `styles.css` → colours and fonts in `:root`.

## Images
`images/` holds AI-generated concept images (Figma AI): storefront by day, at dusk and at night; deli; wine cellar; drinks wall; ready-to-eat aisle. Each comes as `.webp` (web), `-sm.webp` (mobile) and `.jpg` (for social media/print). They are illustrations — replace them with real photos of the store once it is open.
