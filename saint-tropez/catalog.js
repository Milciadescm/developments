// ===== Store settings — edit these =====
const STORE = {
  name: "Saint Tropez Market 24/7",
  whatsapp: "18090000000",      // digits only, international format — orders are sent here
  phone: "+18090000000",
  currency: "RD$",
  usdRate: 59,                  // RD$ per US$, for the "≈ US$" hint at checkout
  minOrder: 590,                // RD$ (ITBIS included), delivery only
  itbisRate: 18,                // % ITBIS included in every price unless a product says otherwise
  // Business details printed on invoices — replace with the real ones
  legal: { name: "Saint Tropez Market 24/7 Group, SRL", rnc: "[RNC]", address: "[Calle / local], Downtown Punta Cana, La Altagracia, República Dominicana", phone: "[+1 809 000 0000]" },
  pickupMinutes: "10–15",
  // Optional: URL that receives each order as JSON (POST). Leave "" to use WhatsApp only.
  orderEndpoint: "",
  zones: [
    { id: "downtown", es: "Downtown Punta Cana / Los Corales", en: "Downtown Punta Cana / Los Corales", fee: 175, eta: "20–35" },
    { id: "bavaro",   es: "Bávaro / Arena Gorda",              en: "Bávaro / Arena Gorda",              fee: 235, eta: "25–40" },
    { id: "puntacana",es: "Punta Cana Village / Aeropuerto",   en: "Punta Cana Village / Airport",      fee: 355, eta: "35–50" },
    { id: "capcana",  es: "Cap Cana",                          en: "Cap Cana",                          fee: 470, eta: "40–60" },
    { id: "uvero",    es: "Uvero Alto / Macao",                en: "Uvero Alto / Macao",                fee: 650, eta: "50–75" },
  ],
  payments: [
    { id: "cash", es: "Efectivo al recibir (RD$ o US$)", en: "Cash on delivery (RD$ or US$)" },
    { id: "card", es: "Tarjeta al recibir (POS)",         en: "Card on delivery (POS terminal)" },
    { id: "transfer", es: "Transferencia bancaria",       en: "Bank transfer" },
  ],
};

// ===== Categories =====
const CATEGORIES = [
  { id: "offers",  es: "Ofertas",                 en: "Deals",                  icon: "🏷️" },
  { id: "fruit",   es: "Frutas y vegetales",      en: "Fruit & vegetables",     icon: "🥭" },
  { id: "bakery",  es: "Panadería y repostería",  en: "Bakery & pastries",      icon: "🥐" },
  { id: "chilled", es: "Embutidos y lácteos",     en: "Deli & dairy",           icon: "🧀" },
  { id: "pantry",  es: "Despensa",                en: "Pantry",                 icon: "🫒" },
  { id: "snacks",  es: "Snacks y galletas",       en: "Snacks & cookies",       icon: "🥨" },
  { id: "sweets",  es: "Chocolates y dulces",     en: "Chocolates & sweets",    icon: "🍫" },
  { id: "drinks",  es: "Bebidas",                 en: "Drinks",                 icon: "🥤" },
  { id: "alcohol", es: "Cervezas, ron y vinos",   en: "Beer, rum & wine",       icon: "🍾" },
  { id: "care",    es: "Cuidado personal y playa",en: "Personal care & beach",  icon: "🧴" },
  { id: "home",    es: "Hogar y limpieza",        en: "Home & cleaning",        icon: "🧺" },
];

// Where a product comes from. "DO" = made in the Dominican Republic.
// Some international brands are also made or packed locally: check each presentation before marking it imported.
const ORIGINS = {
  DO: { flag: "🇩🇴", es: "Hecho en RD", en: "Made in DR" },
  US: { flag: "🇺🇸", es: "Estados Unidos", en: "United States" },
  IT: { flag: "🇮🇹", es: "Italia", en: "Italy" },
  ES: { flag: "🇪🇸", es: "España", en: "Spain" },
  FR: { flag: "🇫🇷", es: "Francia", en: "France" },
  CH: { flag: "🇨🇭", es: "Suiza", en: "Switzerland" },
  DE: { flag: "🇩🇪", es: "Alemania", en: "Germany" },
  GB: { flag: "🇬🇧", es: "Reino Unido", en: "United Kingdom" },
  BE: { flag: "🇧🇪", es: "Bélgica", en: "Belgium" },
  AT: { flag: "🇦🇹", es: "Austria", en: "Austria" },
  MX: { flag: "🇲🇽", es: "México", en: "Mexico" },
  FJ: { flag: "🇫🇯", es: "Fiyi", en: "Fiji" },
  AR: { flag: "🇦🇷", es: "Argentina", en: "Argentina" },
  NZ: { flag: "🇳🇿", es: "Nueva Zelanda", en: "New Zealand" },
  INT: { flag: "🌎", es: "Importado", en: "Imported" },
};

// ===== Products =====
// Prices are shelf prices in RD$ WITH ITBIS (18%) INCLUDED. They are estimates — replace with real prices.
// itbis: tax rate included in the price (default 18). Set itbis: 0 for exempt items (confirm with your accountant).
// brand: shown on the card; origin: key of ORIGINS; img: optional photo path (e.g. "images/products/oreo.webp").
const PRODUCTS = [
  // ---------- Deals ----------
  { id: "p01", cat: "offers", brand: "Planeta Azul", origin: "DO", es: "Agua 6-pack", en: "Water 6-pack", unit: "6 × 600 ml", price: 250, was: 320, emoji: "💧", popular: true },
  { id: "p02", cat: "offers", brand: "Presidente", origin: "DO", es: "Cerveza 6-pack", en: "Beer 6-pack", unit: "6 × 355 ml", price: 635, was: 765, emoji: "🍺", alcohol: true, popular: true },
  { id: "p03", cat: "offers", brand: "Côtes de Provence", origin: "FR", es: "Vino rosado", en: "Rosé wine", unit: "750 ml", price: 1520, was: 1830, emoji: "🍷", alcohol: true },
  { id: "p04", cat: "offers", brand: "", origin: "DO", es: "Piña dorada", en: "Golden pineapple", unit: "1 u", price: 140, was: 190, emoji: "🍍", popular: true },
  { id: "i101", cat: "offers", brand: "Pringles", origin: "US", es: "Papitas Original", en: "Original crisps", unit: "158 g", price: 290, was: 350, emoji: "🥫" },
  { id: "i201", cat: "offers", brand: "Ferrero Rocher", origin: "IT", es: "Bombones de avellana", en: "Hazelnut chocolates", unit: "16 u", price: 1055, was: 1240, emoji: "🍫" },

  // ---------- Fruit & vegetables (local, fresh) ----------
  { id: "p10", cat: "fruit", brand: "", origin: "DO", es: "Mangos", en: "Mangoes", unit: "1 lb", price: 75, emoji: "🥭", popular: true },
  { id: "p11", cat: "fruit", brand: "", origin: "DO", es: "Guineos maduros", en: "Bananas", unit: "1 lb", price: 40, emoji: "🍌" },
  { id: "p12", cat: "fruit", brand: "", origin: "DO", es: "Aguacate", en: "Avocado", unit: "1 u", price: 85, emoji: "🥑" },
  { id: "p13", cat: "fruit", brand: "", origin: "DO", es: "Limones", en: "Limes", unit: "6 u", price: 70, emoji: "🍋" },
  { id: "p14", cat: "fruit", brand: "", origin: "DO", es: "Tomates", en: "Tomatoes", unit: "1 lb", price: 65, emoji: "🍅" },
  { id: "p15", cat: "fruit", brand: "", origin: "INT", es: "Fresas", en: "Strawberries", unit: "250 g", price: 290, emoji: "🍓" },
  { id: "p16", cat: "fruit", brand: "", origin: "DO", es: "Coco frío", en: "Chilled coconut", unit: "1 u", price: 120, emoji: "🥥" },

  // ---------- Bakery & pastries ----------
  { id: "p20", cat: "bakery", brand: "", origin: "DO", es: "Baguette recién horneado", en: "Fresh baguette", unit: "1 u", price: 110, emoji: "🥖", popular: true },
  { id: "p21", cat: "bakery", brand: "", origin: "DO", es: "Croissant de mantequilla", en: "Butter croissant", unit: "1 u", price: 100, emoji: "🥐" },
  { id: "p22", cat: "bakery", brand: "", origin: "DO", es: "Pan de molde integral", en: "Whole-wheat sliced bread", unit: "600 g", price: 195, emoji: "🍞" },
  { id: "p23", cat: "bakery", brand: "", origin: "DO", es: "Sándwich jamón y queso", en: "Ham & cheese sandwich", unit: "1 u", price: 305, emoji: "🥪" },
  { id: "d301", cat: "bakery", brand: "Casabe Doña Mechi", origin: "DO", es: "Casabe tradicional", en: "Traditional cassava bread", unit: "1 paquete", price: 140, emoji: "🫓" },
  { id: "d302", cat: "bakery", brand: "Repostería Miguelina", origin: "DO", es: "Bizcocho dominicano (porción)", en: "Dominican cake (slice)", unit: "1 porción", price: 205, emoji: "🍰", popular: true },
  { id: "d303", cat: "bakery", brand: "Galletas Napolitanas", origin: "DO", es: "Galletas napolitanas", en: "Napolitana cookies", unit: "1 paquete", price: 110, emoji: "🍪" },

  // ---------- Deli & dairy ----------
  { id: "d101", cat: "chilled", brand: "Induveca", origin: "DO", es: "Salami súper especial", en: "Dominican salami", unit: "1 lb", price: 250, emoji: "🥓", popular: true },
  { id: "d102", cat: "chilled", brand: "Induveca", origin: "DO", es: "Jamón de pavo", en: "Turkey ham", unit: "1/2 lb", price: 230, emoji: "🍖" },
  { id: "d103", cat: "chilled", brand: "Induveca", origin: "DO", es: "Queso de freír", en: "Frying cheese", unit: "1 lb", price: 285, emoji: "🧀" },
  { id: "p50", cat: "chilled", brand: "Rica", origin: "DO", es: "Leche entera", en: "Whole milk", unit: "1 L", price: 110, emoji: "🥛" },
  { id: "p53", cat: "chilled", brand: "Rica", origin: "DO", es: "Yogur de fresa", en: "Strawberry yogurt", unit: "4 × 125 g", price: 250, emoji: "🥣" },
  { id: "p51", cat: "chilled", brand: "", origin: "DO", es: "Huevos", en: "Eggs", unit: "12 u", price: 250, emoji: "🥚" },
  { id: "p52", cat: "chilled", brand: "", origin: "FR", es: "Queso brie", en: "Brie cheese", unit: "200 g", price: 465, emoji: "🧀" },
  { id: "p54", cat: "chilled", brand: "", origin: "ES", es: "Jamón serrano", en: "Serrano ham", unit: "100 g", price: 385, emoji: "🥓" },
  { id: "p63", cat: "chilled", brand: "Helados Bon", origin: "DO", es: "Helado de vainilla", en: "Vanilla ice cream", unit: "1/2 galón", price: 465, emoji: "🍨", popular: true },
  { id: "d104", cat: "chilled", brand: "Helados Bon", origin: "DO", es: "Helado de chinola", en: "Passion-fruit ice cream", unit: "1 pinta", price: 265, emoji: "🍧" },

  // ---------- Pantry: Dominican ----------
  { id: "d201", cat: "pantry", brand: "La Famosa", origin: "DO", es: "Habichuelas rojas", en: "Red beans", unit: "15 oz", price: 100, emoji: "🫘" },
  { id: "d202", cat: "pantry", brand: "La Famosa", origin: "DO", es: "Vegetales mixtos", en: "Mixed vegetables", unit: "15 oz", price: 105, emoji: "🥫" },
  { id: "d203", cat: "pantry", brand: "Linda", origin: "DO", es: "Kétchup", en: "Ketchup", unit: "16 oz", price: 135, emoji: "🍅" },
  { id: "d204", cat: "pantry", brand: "Linda", origin: "DO", es: "Pasta de tomate", en: "Tomato paste", unit: "8 oz", price: 75, emoji: "🥫" },
  { id: "d205", cat: "pantry", brand: "Baldom", origin: "DO", es: "Sazón completo", en: "All-purpose seasoning", unit: "8 oz", price: 110, emoji: "🧂" },
  { id: "d206", cat: "pantry", brand: "Baldom", origin: "DO", es: "Salsa de ajo", en: "Garlic sauce", unit: "12 oz", price: 130, emoji: "🧄" },
  { id: "p71", cat: "pantry", brand: "Princesa", origin: "DO", es: "Espaguetis", en: "Spaghetti", unit: "1 lb", price: 75, emoji: "🍝" },
  { id: "d207", cat: "pantry", brand: "Del César", origin: "DO", es: "Coditos", en: "Elbow pasta", unit: "1 lb", price: 70, emoji: "🍝" },
  { id: "p73", cat: "pantry", brand: "La Garza", origin: "DO", es: "Arroz premium", en: "Premium rice", unit: "5 lb", price: 305, emoji: "🍚" },
  { id: "d208", cat: "pantry", brand: "Bisonó", origin: "DO", es: "Arroz", en: "Rice", unit: "5 lb", price: 285, emoji: "🍚" },
  { id: "d209", cat: "pantry", brand: "Pimco", origin: "DO", es: "Arroz selecto", en: "Select rice", unit: "5 lb", price: 290, emoji: "🍚" },
  { id: "d210", cat: "pantry", brand: "Crisol", origin: "DO", es: "Aceite de soya", en: "Soybean oil", unit: "32 oz", price: 270, emoji: "🫙" },
  { id: "d211", cat: "pantry", brand: "El Gallo", origin: "DO", es: "Aceite vegetal", en: "Vegetable oil", unit: "32 oz", price: 260, emoji: "🫙" },
  { id: "p72", cat: "pantry", brand: "Café Santo Domingo", origin: "DO", es: "Café molido", en: "Ground coffee", unit: "1 lb", price: 465, emoji: "☕", popular: true },
  { id: "d212", cat: "pantry", brand: "Cortés", origin: "DO", es: "Chocolate de taza", en: "Hot-chocolate bar", unit: "8 oz", price: 170, emoji: "🍫" },
  // ---------- Pantry: imported ----------
  { id: "i401", cat: "pantry", brand: "Barilla", origin: "IT", es: "Penne rigate", en: "Penne rigate", unit: "500 g", price: 205, emoji: "🍝" },
  { id: "i402", cat: "pantry", brand: "De Cecco", origin: "IT", es: "Spaghetti n.º 12", en: "Spaghetti no. 12", unit: "500 g", price: 290, emoji: "🍝" },
  { id: "i403", cat: "pantry", brand: "Mutti", origin: "IT", es: "Passata de tomate", en: "Tomato passata", unit: "700 g", price: 350, emoji: "🍅" },
  { id: "i404", cat: "pantry", brand: "Heinz", origin: "US", es: "Kétchup", en: "Ketchup", unit: "20 oz", price: 265, emoji: "🍅" },
  { id: "i405", cat: "pantry", brand: "Goya", origin: "US", es: "Frijoles negros", en: "Black beans", unit: "15.5 oz", price: 150, emoji: "🫘" },
  { id: "i406", cat: "pantry", brand: "Nutella", origin: "IT", es: "Crema de avellanas y cacao", en: "Hazelnut cocoa spread", unit: "350 g", price: 525, emoji: "🫙", popular: true },
  { id: "i407", cat: "pantry", brand: "Kellogg's", origin: "US", es: "Corn Flakes", en: "Corn Flakes", unit: "500 g", price: 405, emoji: "🥣" },
  { id: "i408", cat: "pantry", brand: "Quaker", origin: "US", es: "Avena tradicional", en: "Old-fashioned oats", unit: "510 g", price: 315, emoji: "🌾" },
  { id: "i409", cat: "pantry", brand: "McCormick", origin: "US", es: "Pimienta negra molida", en: "Ground black pepper", unit: "1.5 oz", price: 230, emoji: "🧂" },
  { id: "p70", cat: "pantry", brand: "La Española", origin: "ES", es: "Aceite de oliva extra virgen", en: "Extra virgin olive oil", unit: "500 ml", price: 615, emoji: "🫒" },
  { id: "i410", cat: "pantry", brand: "Bertolli", origin: "IT", es: "Salsa pesto", en: "Pesto sauce", unit: "185 g", price: 405, emoji: "🌿" },
  { id: "i411", cat: "pantry", brand: "Calvo", origin: "ES", es: "Atún en aceite de oliva", en: "Tuna in olive oil", unit: "3 × 80 g", price: 465, emoji: "🐟" },

  // ---------- Snacks & cookies ----------
  { id: "d401", cat: "snacks", brand: "Hatuey", origin: "DO", es: "Galletas de soda", en: "Soda crackers", unit: "1 paquete", price: 90, emoji: "🍘" },
  { id: "d402", cat: "snacks", brand: "Guarina", origin: "DO", es: "Galletas surtidas", en: "Assorted cookies", unit: "1 paquete", price: 100, emoji: "🍪" },
  { id: "d403", cat: "snacks", brand: "Copittas", origin: "DO", es: "Snack de maíz", en: "Corn snack", unit: "1 bolsa", price: 55, emoji: "🌽" },
  { id: "d404", cat: "snacks", brand: "Crachi", origin: "DO", es: "Chicharrones", en: "Pork-rind snack", unit: "1 bolsa", price: 65, emoji: "🥓" },
  { id: "d405", cat: "snacks", brand: "Forteza", origin: "DO", es: "Galletas", en: "Crackers", unit: "1 paquete", price: 75, emoji: "🍘" },
  { id: "p62", cat: "snacks", brand: "", origin: "DO", es: "Maní tostado", en: "Roasted peanuts", unit: "200 g", price: 130, emoji: "🥜" },
  { id: "p60", cat: "snacks", brand: "Lay's", origin: "US", es: "Papitas clásicas", en: "Classic chips", unit: "184 g", price: 275, emoji: "🥔", popular: true },
  { id: "i102", cat: "snacks", brand: "Oreo", origin: "US", es: "Galletas originales", en: "Original cookies", unit: "303 g", price: 265, emoji: "🍪", popular: true },
  { id: "i103", cat: "snacks", brand: "Doritos", origin: "US", es: "Nacho Cheese", en: "Nacho Cheese", unit: "262 g", price: 325, emoji: "🔺" },
  { id: "i104", cat: "snacks", brand: "Cheetos", origin: "US", es: "Crunchy", en: "Crunchy", unit: "226 g", price: 300, emoji: "🧀" },
  { id: "i105", cat: "snacks", brand: "Ritz", origin: "US", es: "Galletas saladas", en: "Crackers", unit: "388 g", price: 315, emoji: "🍘" },
  { id: "i106", cat: "snacks", brand: "Ruffles", origin: "US", es: "Papitas onduladas", en: "Ridged chips", unit: "184 g", price: 275, emoji: "🥔" },
  { id: "i107", cat: "snacks", brand: "Takis", origin: "MX", es: "Fuego", en: "Fuego", unit: "280 g", price: 325, emoji: "🌶️" },
  { id: "i108", cat: "snacks", brand: "Chips Ahoy!", origin: "US", es: "Galletas con chispas", en: "Chocolate chip cookies", unit: "368 g", price: 315, emoji: "🍪" },
  { id: "i109", cat: "snacks", brand: "Pepperidge Farm", origin: "US", es: "Galletas Milano", en: "Milano cookies", unit: "170 g", price: 405, emoji: "🍪" },
  { id: "i110", cat: "snacks", brand: "Walkers", origin: "GB", es: "Papitas sal y vinagre", en: "Salt & vinegar crisps", unit: "150 g", price: 290, emoji: "🥔" },
  { id: "i111", cat: "snacks", brand: "Tuc", origin: "BE", es: "Galletas originales", en: "Original crackers", unit: "100 g", price: 170, emoji: "🍘" },
  { id: "i112", cat: "snacks", brand: "Lotus Biscoff", origin: "BE", es: "Galletas caramelizadas", en: "Caramelised biscuits", unit: "250 g", price: 350, emoji: "🍪" },

  // ---------- Chocolates & sweets ----------
  { id: "p61", cat: "sweets", brand: "Kah Kow", origin: "DO", es: "Chocolate 70% cacao dominicano", en: "70% Dominican cacao chocolate", unit: "100 g", price: 340, emoji: "🍫", popular: true },
  { id: "d501", cat: "sweets", brand: "Dulces Yomisardys", origin: "DO", es: "Dulce de leche criollo", en: "Dominican milk fudge", unit: "1 paquete", price: 175, emoji: "🍮" },
  { id: "d502", cat: "sweets", brand: "", origin: "DO", es: "Nibs de cacao dominicano", en: "Dominican cacao nibs", unit: "200 g", price: 385, emoji: "🌰" },
  { id: "i202", cat: "sweets", brand: "Lindt", origin: "CH", es: "Lindor leche", en: "Lindor milk truffles", unit: "200 g", price: 940, emoji: "🍫" },
  { id: "i203", cat: "sweets", brand: "Hershey's", origin: "US", es: "Barra de chocolate con leche", en: "Milk chocolate bar", unit: "43 g", price: 110, emoji: "🍫" },
  { id: "i204", cat: "sweets", brand: "M&M's", origin: "US", es: "Chocolate con leche", en: "Milk chocolate", unit: "49 g", price: 110, emoji: "🔴" },
  { id: "i205", cat: "sweets", brand: "Kinder", origin: "IT", es: "Kinder Bueno", en: "Kinder Bueno", unit: "43 g", price: 130, emoji: "🍫" },
  { id: "i206", cat: "sweets", brand: "Haribo", origin: "DE", es: "Ositos de goma", en: "Gold-bears gummies", unit: "142 g", price: 205, emoji: "🧸" },
  { id: "i207", cat: "sweets", brand: "Reese's", origin: "US", es: "Copas de mantequilla de maní", en: "Peanut-butter cups", unit: "42 g", price: 110, emoji: "🥜" },
  { id: "i208", cat: "sweets", brand: "Snickers", origin: "US", es: "Barra", en: "Bar", unit: "52 g", price: 100, emoji: "🍫" },
  { id: "i209", cat: "sweets", brand: "Twix", origin: "US", es: "Barra", en: "Bar", unit: "50 g", price: 100, emoji: "🍫" },
  { id: "i210", cat: "sweets", brand: "Milka", origin: "DE", es: "Chocolate alpino", en: "Alpine milk chocolate", unit: "100 g", price: 220, emoji: "🍫" },
  { id: "i211", cat: "sweets", brand: "Toblerone", origin: "CH", es: "Chocolate con nougat", en: "Chocolate with nougat", unit: "100 g", price: 290, emoji: "🔺" },
  { id: "i212", cat: "sweets", brand: "KitKat", origin: "GB", es: "Barra 4 dedos", en: "4-finger bar", unit: "41.5 g", price: 100, emoji: "🍫" },

  // ---------- Drinks: Dominican ----------
  { id: "p34", cat: "drinks", brand: "", origin: "DO", es: "Bolsa de hielo", en: "Bag of ice", unit: "10 lb", price: 140, emoji: "🧊", popular: true },
  { id: "p30", cat: "drinks", brand: "Crystal", origin: "DO", es: "Agua", en: "Water", unit: "1.5 L", price: 85, emoji: "💧" },
  { id: "d601", cat: "drinks", brand: "Country Club", origin: "DO", es: "Refresco merengue", en: "Merengue soda", unit: "2 L", price: 130, emoji: "🥤" },
  { id: "d602", cat: "drinks", brand: "Country Club", origin: "DO", es: "Refresco de frambuesa", en: "Raspberry soda", unit: "2 L", price: 130, emoji: "🥤" },
  { id: "d603", cat: "drinks", brand: "Malta Morena", origin: "DO", es: "Malta", en: "Malt beverage", unit: "355 ml", price: 70, emoji: "🍺" },
  { id: "d604", cat: "drinks", brand: "Malta India", origin: "DO", es: "Malta", en: "Malt beverage", unit: "355 ml", price: 70, emoji: "🍺" },
  { id: "p31", cat: "drinks", brand: "Rica", origin: "DO", es: "Jugo de naranja", en: "Orange juice", unit: "1 L", price: 175, emoji: "🧃" },
  { id: "d605", cat: "drinks", brand: "Santal", origin: "DO", es: "Jugo de pera", en: "Pear juice", unit: "1 L", price: 165, emoji: "🧃" },
  // ---------- Drinks: imported ----------
  { id: "p33", cat: "drinks", brand: "Red Bull", origin: "AT", es: "Bebida energizante", en: "Energy drink", unit: "250 ml", price: 170, emoji: "⚡", popular: true },
  { id: "i301", cat: "drinks", brand: "Monster", origin: "US", es: "Energy original", en: "Energy original", unit: "473 ml", price: 195, emoji: "⚡" },
  { id: "i302", cat: "drinks", brand: "Arizona", origin: "US", es: "Té verde", en: "Green tea", unit: "680 ml", price: 150, emoji: "🍵" },
  { id: "i303", cat: "drinks", brand: "Evian", origin: "FR", es: "Agua natural de manantial", en: "Natural spring water", unit: "1 L", price: 205, emoji: "💧" },
  { id: "i304", cat: "drinks", brand: "San Pellegrino", origin: "IT", es: "Agua con gas", en: "Sparkling water", unit: "750 ml", price: 230, emoji: "🫧" },
  { id: "i305", cat: "drinks", brand: "Fiji Water", origin: "FJ", es: "Agua artesiana", en: "Artesian water", unit: "1 L", price: 255, emoji: "💧" },
  { id: "i306", cat: "drinks", brand: "Gatorade", origin: "US", es: "Lima-limón", en: "Lemon-lime", unit: "591 ml", price: 130, emoji: "🧴" },
  { id: "i307", cat: "drinks", brand: "Powerade", origin: "US", es: "Mountain Berry", en: "Mountain Berry", unit: "591 ml", price: 125, emoji: "🧴" },
  { id: "i308", cat: "drinks", brand: "Coca-Cola", origin: "US", es: "Coca-Cola importada (vidrio)", en: "Imported Coca-Cola (glass)", unit: "355 ml", price: 110, emoji: "🥤" },
  { id: "i309", cat: "drinks", brand: "Fanta", origin: "US", es: "Naranja importada", en: "Imported orange", unit: "355 ml", price: 100, emoji: "🍊" },
  { id: "i310", cat: "drinks", brand: "Dr Pepper", origin: "US", es: "Refresco", en: "Soda", unit: "355 ml", price: 100, emoji: "🥤" },
  { id: "i311", cat: "drinks", brand: "7UP", origin: "US", es: "Refresco lima-limón", en: "Lemon-lime soda", unit: "355 ml", price: 90, emoji: "🍋" },
  { id: "i312", cat: "drinks", brand: "Schweppes", origin: "GB", es: "Agua tónica", en: "Tonic water", unit: "355 ml", price: 105, emoji: "🫧" },
  { id: "i313", cat: "drinks", brand: "Perrier", origin: "FR", es: "Agua mineral con gas", en: "Sparkling mineral water", unit: "330 ml", price: 150, emoji: "🫧" },
  { id: "i314", cat: "drinks", brand: "Vitaminwater", origin: "US", es: "XXX açaí-blueberry", en: "XXX açaí-blueberry", unit: "591 ml", price: 170, emoji: "🧃" },
  { id: "p35", cat: "drinks", brand: "Starbucks", origin: "US", es: "Frappuccino listo para tomar", en: "Ready-to-drink Frappuccino", unit: "405 ml", price: 265, emoji: "☕" },

  // ---------- Beer, rum & wine (18+) ----------
  { id: "p40", cat: "alcohol", brand: "Presidente", origin: "DO", es: "Cerveza", en: "Beer", unit: "650 ml", price: 205, emoji: "🍺", alcohol: true },
  { id: "d701", cat: "alcohol", brand: "Bohemia", origin: "DO", es: "Cerveza", en: "Beer", unit: "355 ml", price: 130, emoji: "🍺", alcohol: true },
  { id: "p41", cat: "alcohol", brand: "Brugal", origin: "DO", es: "Ron Añejo", en: "Añejo rum", unit: "700 ml", price: 1355, emoji: "🥃", alcohol: true, popular: true },
  { id: "d702", cat: "alcohol", brand: "Brugal", origin: "DO", es: "Ron 1888", en: "1888 rum", unit: "700 ml", price: 4070, emoji: "🥃", alcohol: true },
  { id: "d703", cat: "alcohol", brand: "Barceló", origin: "DO", es: "Ron Imperial", en: "Imperial rum", unit: "700 ml", price: 2000, emoji: "🥃", alcohol: true },
  { id: "d704", cat: "alcohol", brand: "Bermúdez", origin: "DO", es: "Ron Aniversario", en: "Aniversario rum", unit: "700 ml", price: 2185, emoji: "🥃", alcohol: true },
  { id: "d705", cat: "alcohol", brand: "Macorix", origin: "DO", es: "Ron Gran Reserva", en: "Gran Reserva rum", unit: "700 ml", price: 1475, emoji: "🥃", alcohol: true },
  { id: "p42", cat: "alcohol", brand: "", origin: "FR", es: "Champán brut", en: "Brut champagne", unit: "750 ml", price: 5840, emoji: "🍾", alcohol: true },
  { id: "p43", cat: "alcohol", brand: "", origin: "AR", es: "Vino tinto Malbec", en: "Malbec red wine", unit: "750 ml", price: 1155, emoji: "🍷", alcohol: true },
  { id: "p44", cat: "alcohol", brand: "", origin: "NZ", es: "Vino blanco Sauvignon Blanc", en: "Sauvignon Blanc white wine", unit: "750 ml", price: 1085, emoji: "🥂", alcohol: true },

  // ---------- Personal care & beach ----------
  { id: "p80", cat: "care", brand: "", origin: "INT", es: "Protector solar FPS 50", en: "Sunscreen SPF 50", unit: "200 ml", price: 1050, emoji: "🧴", popular: true },
  { id: "p81", cat: "care", brand: "", origin: "INT", es: "Repelente de mosquitos", en: "Insect repellent", unit: "120 ml", price: 530, emoji: "🦟" },
  { id: "p82", cat: "care", brand: "", origin: "INT", es: "Gel de aloe vera", en: "Aloe vera gel", unit: "250 ml", price: 495, emoji: "🌿" },
  { id: "i501", cat: "care", brand: "Dove", origin: "INT", es: "Jabón en barra", en: "Beauty bar", unit: "2 × 106 g", price: 230, emoji: "🧼" },
  { id: "i502", cat: "care", brand: "Nivea", origin: "DE", es: "Crema hidratante", en: "Moisturising cream", unit: "150 ml", price: 430, emoji: "🧴" },
  { id: "p83", cat: "care", brand: "Colgate", origin: "INT", es: "Pasta dental Total", en: "Total toothpaste", unit: "75 ml", price: 205, emoji: "🪥" },
  { id: "i503", cat: "care", brand: "Oral-B", origin: "INT", es: "Cepillo de dientes", en: "Toothbrush", unit: "1 u", price: 170, emoji: "🪥" },
  { id: "i504", cat: "care", brand: "Pantene", origin: "INT", es: "Champú reparación", en: "Repair shampoo", unit: "400 ml", price: 405, emoji: "🧴" },
  { id: "i505", cat: "care", brand: "Head & Shoulders", origin: "INT", es: "Champú anticaspa", en: "Anti-dandruff shampoo", unit: "375 ml", price: 430, emoji: "🧴" },
  { id: "i506", cat: "care", brand: "Gillette", origin: "INT", es: "Máquinas de afeitar", en: "Disposable razors", unit: "3 u", price: 350, emoji: "🪒" },
  { id: "i507", cat: "care", brand: "Old Spice", origin: "US", es: "Desodorante", en: "Deodorant", unit: "85 g", price: 335, emoji: "🧴" },
  { id: "i508", cat: "care", brand: "Axe", origin: "INT", es: "Desodorante en spray", en: "Body spray", unit: "150 ml", price: 315, emoji: "🧴" },
  { id: "i509", cat: "care", brand: "Neutrogena", origin: "US", es: "Protector solar Ultra Sheer FPS 55", en: "Ultra Sheer sunscreen SPF 55", unit: "88 ml", price: 995, emoji: "☀️" },
  { id: "i510", cat: "care", brand: "L'Oréal", origin: "FR", es: "Acondicionador Elvive", en: "Elvive conditioner", unit: "370 ml", price: 405, emoji: "🧴" },
  { id: "i511", cat: "care", brand: "Garnier", origin: "FR", es: "Agua micelar", en: "Micellar water", unit: "400 ml", price: 465, emoji: "💧" },

  // ---------- Home & cleaning ----------
  { id: "p90", cat: "home", brand: "", origin: "DO", es: "Papel higiénico", en: "Toilet paper", unit: "4 rollos", price: 205, emoji: "🧻" },
  { id: "p91", cat: "home", brand: "", origin: "DO", es: "Vasos desechables", en: "Disposable cups", unit: "25 u", price: 140, emoji: "🥤" },
  { id: "p92", cat: "home", brand: "", origin: "DO", es: "Carbón para BBQ", en: "BBQ charcoal", unit: "8 lb", price: 390, emoji: "🔥" },
  { id: "p93", cat: "home", brand: "", origin: "INT", es: "Pilas AA", en: "AA batteries", unit: "4 u", price: 340, emoji: "🔋" },
  { id: "i601", cat: "home", brand: "Ariel", origin: "INT", es: "Detergente en polvo", en: "Laundry powder", unit: "1 kg", price: 405, emoji: "🧺" },
  { id: "i602", cat: "home", brand: "Tide", origin: "US", es: "Detergente líquido", en: "Liquid detergent", unit: "1.47 L", price: 700, emoji: "🧺" },
  { id: "i603", cat: "home", brand: "Downy", origin: "INT", es: "Suavizante", en: "Fabric softener", unit: "800 ml", price: 350, emoji: "🌸" },
  { id: "i604", cat: "home", brand: "Finish", origin: "INT", es: "Pastillas lavavajillas", en: "Dishwasher tablets", unit: "20 u", price: 760, emoji: "🍽️" },
  { id: "i605", cat: "home", brand: "Lysol", origin: "US", es: "Spray desinfectante", en: "Disinfectant spray", unit: "354 g", price: 525, emoji: "🧴" },
  { id: "i606", cat: "home", brand: "Febreze", origin: "US", es: "Ambientador", en: "Air freshener", unit: "250 g", price: 385, emoji: "🌬️" },
];

