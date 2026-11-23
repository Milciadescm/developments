// ===== Backend + map settings =====
// The publishable key is meant to be public: access is enforced by the database's row-level security.
window.ST_CONFIG = {
  supabaseUrl: "https://nwzcezwlszozicifmile.supabase.co",
  supabaseKey: "sb_publishable_74IHtHphKK6iisL71lu2fQ_szE_nLRD",
  // Store position on the map (Downtown Punta Cana) — set the exact spot of the container.
  storeLocation: { lat: 18.6812, lng: -68.4119 },
  // Map centre per delivery zone, used to place the pin at checkout.
  zoneCenters: {
    downtown: { lat: 18.6812, lng: -68.4119 },
    bavaro: { lat: 18.6936, lng: -68.4469 },
    puntacana: { lat: 18.5734, lng: -68.3729 },
    capcana: { lat: 18.4577, lng: -68.4053 },
    uvero: { lat: 18.8015, lng: -68.5810 },
  },
  tiles: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  tilesAttribution: "© OpenStreetMap",
  driverPingSeconds: 5, // how often the driver's phone sends its position
};
