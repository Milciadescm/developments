// ===== Store settings — edit these =====
const STORE = {
  name: "Saint Tropez Market 24/7",
  whatsapp: "18090000000",      // digits only, international format — orders are sent here
  phone: "+18090000000",
  currency: "RD$",
  usdRate: 59,                  // RD$ per US$, for the "≈ US$" hint at checkout
  minOrder: 500,                // RD$, delivery only
  pickupMinutes: "10–15",
  // Optional: URL that receives each order as JSON (POST). Leave "" to use WhatsApp only.
  orderEndpoint: "",
  zones: [
    { id: "downtown", es: "Downtown Punta Cana / Los Corales", en: "Downtown Punta Cana / Los Corales", fee: 150, eta: "20–35" },
    { id: "bavaro",   es: "Bávaro / Arena Gorda",              en: "Bávaro / Arena Gorda",              fee: 200, eta: "25–40" },
    { id: "puntacana",es: "Punta Cana Village / Aeropuerto",   en: "Punta Cana Village / Airport",      fee: 300, eta: "35–50" },
    { id: "capcana",  es: "Cap Cana",                          en: "Cap Cana",                          fee: 400, eta: "40–60" },
    { id: "uvero",    es: "Uvero Alto / Macao",                en: "Uvero Alto / Macao",                fee: 550, eta: "50–75" },
  ],
  payments: [
    { id: "cash", es: "Efectivo al recibir (RD$ o US$)", en: "Cash on delivery (RD$ or US$)" },
    { id: "card", es: "Tarjeta al recibir (POS)",         en: "Card on delivery (POS terminal)" },
    { id: "transfer", es: "Transferencia bancaria",       en: "Bank transfer" },
  ],
};

// ===== Categories =====
const CATEGORIES = [
  { id: "offers",  es: "Ofertas",               en: "Deals",               icon: "🏷️" },
  { id: "fruit",   es: "Frutas y vegetales",    en: "Fruit & vegetables",  icon: "🥭" },
  { id: "bakery",  es: "Panadería",             en: "Bakery",              icon: "🥐" },
  { id: "drinks",  es: "Bebidas",               en: "Drinks",              icon: "🥤" },
  { id: "alcohol", es: "Cervezas, vinos y ron", en: "Beer, wine & rum",    icon: "🍾" },
  { id: "chilled", es: "Lácteos y refrigerados",en: "Dairy & chilled",     icon: "🧀" },
  { id: "snacks",  es: "Snacks y dulces",       en: "Snacks & sweets",     icon: "🍫" },
  { id: "pantry",  es: "Despensa gourmet",      en: "Gourmet pantry",      icon: "🫒" },
  { id: "beach",   es: "Playa y cuidado",       en: "Beach & care",        icon: "🧴" },
  { id: "home",    es: "Esenciales",            en: "Essentials",          icon: "🧻" },
];

// ===== Products (example catalogue — replace with real items & prices) =====
// img: optional path to a product photo (e.g. "images/products/agua.webp"); emoji is used when missing.
const PRODUCTS = [
  // Deals
  { id: "p01", cat: "offers", es: "Agua Planeta Azul 6-pack", en: "Bottled water 6-pack", unit: "6 × 600 ml", price: 210, was: 270, emoji: "💧", popular: true },
  { id: "p02", cat: "offers", es: "Cerveza Presidente (6-pack)", en: "Presidente beer (6-pack)", unit: "6 × 355 ml", price: 540, was: 650, emoji: "🍺", alcohol: true, popular: true },
  { id: "p03", cat: "offers", es: "Vino rosado de Provenza", en: "Provence rosé wine", unit: "750 ml", price: 1290, was: 1550, emoji: "🍷", alcohol: true },
  { id: "p04", cat: "offers", es: "Piña dorada", en: "Golden pineapple", unit: "1 u", price: 120, was: 160, emoji: "🍍", popular: true },
  // Fruit
  { id: "p10", cat: "fruit", es: "Mangos", en: "Mangoes", unit: "1 lb", price: 65, emoji: "🥭", popular: true },
  { id: "p11", cat: "fruit", es: "Guineos maduros", en: "Bananas", unit: "1 lb", price: 35, emoji: "🍌" },
  { id: "p12", cat: "fruit", es: "Aguacate", en: "Avocado", unit: "1 u", price: 70, emoji: "🥑" },
  { id: "p13", cat: "fruit", es: "Limones", en: "Limes", unit: "6 u", price: 60, emoji: "🍋" },
  { id: "p14", cat: "fruit", es: "Tomates", en: "Tomatoes", unit: "1 lb", price: 55, emoji: "🍅" },
  { id: "p15", cat: "fruit", es: "Fresas", en: "Strawberries", unit: "250 g", price: 245, emoji: "🍓" },
  { id: "p16", cat: "fruit", es: "Coco frío", en: "Chilled coconut", unit: "1 u", price: 100, emoji: "🥥" },
  // Bakery
  { id: "p20", cat: "bakery", es: "Baguette recién horneado", en: "Fresh baguette", unit: "1 u", price: 95, emoji: "🥖", popular: true },
  { id: "p21", cat: "bakery", es: "Croissant de mantequilla", en: "Butter croissant", unit: "1 u", price: 85, emoji: "🥐" },
  { id: "p22", cat: "bakery", es: "Pan de molde integral", en: "Whole-wheat sliced bread", unit: "600 g", price: 165, emoji: "🍞" },
  { id: "p23", cat: "bakery", es: "Sándwich jamón y queso", en: "Ham & cheese sandwich", unit: "1 u", price: 260, emoji: "🥪" },
  // Drinks
  { id: "p30", cat: "drinks", es: "Agua 1.5 L", en: "Water 1.5 L", unit: "1.5 L", price: 70, emoji: "💧" },
  { id: "p31", cat: "drinks", es: "Jugo de naranja natural", en: "Fresh orange juice", unit: "1 L", price: 210, emoji: "🧃" },
  { id: "p32", cat: "drinks", es: "Refresco de cola", en: "Cola soft drink", unit: "2 L", price: 120, emoji: "🥤" },
  { id: "p33", cat: "drinks", es: "Bebida energizante", en: "Energy drink", unit: "473 ml", price: 145, emoji: "⚡" },
  { id: "p34", cat: "drinks", es: "Bolsa de hielo", en: "Bag of ice", unit: "10 lb", price: 120, emoji: "🧊", popular: true },
  { id: "p35", cat: "drinks", es: "Café frío", en: "Iced coffee", unit: "300 ml", price: 175, emoji: "☕" },
  // Alcohol
  { id: "p40", cat: "alcohol", es: "Cerveza Presidente", en: "Presidente beer", unit: "650 ml", price: 175, emoji: "🍺", alcohol: true },
  { id: "p41", cat: "alcohol", es: "Ron añejo dominicano", en: "Aged Dominican rum", unit: "700 ml", price: 1150, emoji: "🥃", alcohol: true, popular: true },
  { id: "p42", cat: "alcohol", es: "Champán brut", en: "Brut champagne", unit: "750 ml", price: 4950, emoji: "🍾", alcohol: true },
  { id: "p43", cat: "alcohol", es: "Vino tinto Malbec", en: "Malbec red wine", unit: "750 ml", price: 980, emoji: "🍷", alcohol: true },
  { id: "p44", cat: "alcohol", es: "Vino blanco Sauvignon Blanc", en: "Sauvignon Blanc white wine", unit: "750 ml", price: 920, emoji: "🥂", alcohol: true },
  // Chilled
  { id: "p50", cat: "chilled", es: "Leche entera", en: "Whole milk", unit: "1 L", price: 95, emoji: "🥛" },
  { id: "p51", cat: "chilled", es: "Huevos", en: "Eggs", unit: "12 u", price: 210, emoji: "🥚" },
  { id: "p52", cat: "chilled", es: "Queso brie", en: "Brie cheese", unit: "200 g", price: 395, emoji: "🧀" },
  { id: "p53", cat: "chilled", es: "Yogur griego", en: "Greek yogurt", unit: "500 g", price: 230, emoji: "🥣" },
  { id: "p54", cat: "chilled", es: "Jamón serrano", en: "Serrano ham", unit: "100 g", price: 325, emoji: "🥓" },
  // Snacks
  { id: "p60", cat: "snacks", es: "Papitas fritas", en: "Potato chips", unit: "150 g", price: 135, emoji: "🥔" },
  { id: "p61", cat: "snacks", es: "Chocolate oscuro 70%", en: "Dark chocolate 70%", unit: "100 g", price: 190, emoji: "🍫" },
  { id: "p62", cat: "snacks", es: "Maní tostado", en: "Roasted peanuts", unit: "200 g", price: 110, emoji: "🥜" },
  { id: "p63", cat: "snacks", es: "Helado de vainilla", en: "Vanilla ice cream", unit: "1 pt", price: 395, emoji: "🍨" },
  // Pantry
  { id: "p70", cat: "pantry", es: "Aceite de oliva extra virgen", en: "Extra virgin olive oil", unit: "500 ml", price: 520, emoji: "🫒" },
  { id: "p71", cat: "pantry", es: "Pasta spaghetti", en: "Spaghetti", unit: "500 g", price: 89, emoji: "🍝" },
  { id: "p72", cat: "pantry", es: "Café dominicano molido", en: "Dominican ground coffee", unit: "454 g", price: 395, emoji: "☕", popular: true },
  { id: "p73", cat: "pantry", es: "Arroz selecto", en: "Premium rice", unit: "5 lb", price: 240, emoji: "🍚" },
  // Beach & care
  { id: "p80", cat: "beach", es: "Protector solar FPS 50", en: "Sunscreen SPF 50", unit: "200 ml", price: 890, emoji: "🧴", popular: true },
  { id: "p81", cat: "beach", es: "Repelente de mosquitos", en: "Insect repellent", unit: "120 ml", price: 450, emoji: "🦟" },
  { id: "p82", cat: "beach", es: "Gel de aloe vera", en: "Aloe vera gel", unit: "250 ml", price: 420, emoji: "🌿" },
  { id: "p83", cat: "beach", es: "Cepillo + pasta dental", en: "Toothbrush + toothpaste", unit: "kit", price: 260, emoji: "🪥" },
  // Essentials
  { id: "p90", cat: "home", es: "Papel higiénico", en: "Toilet paper", unit: "4 rollos", price: 175, emoji: "🧻" },
  { id: "p91", cat: "home", es: "Vasos desechables", en: "Disposable cups", unit: "25 u", price: 120, emoji: "🥤" },
  { id: "p92", cat: "home", es: "Carbón para BBQ", en: "BBQ charcoal", unit: "8 lb", price: 330, emoji: "🔥" },
  { id: "p93", cat: "home", es: "Pilas AA", en: "AA batteries", unit: "4 u", price: 290, emoji: "🔋" },
];
