/* Thin wrapper around Supabase used by the shop, tracking, staff and driver pages.
   window.ST_API is null-safe: if the backend isn't reachable the shop falls back to WhatsApp ordering. */
(() => {
  const cfg = window.ST_CONFIG || {};
  const lib = window.supabase;
  const client = lib && cfg.supabaseUrl && cfg.supabaseKey
    ? lib.createClient(cfg.supabaseUrl, cfg.supabaseKey, { auth: { persistSession: true, storageKey: "st-auth" } })
    : null;

  const must = () => { if (!client) throw new Error("backend unavailable"); return client; };
  const unwrap = ({ data, error }) => { if (error) throw error; return data; };

  window.ST_API = {
    available: !!client,
    client,

    // ---------- customer ----------
    async catalog() {
      const c = must();
      const [p, z] = await Promise.all([
        c.from("st_products").select("*").eq("active", true).order("sort"),
        c.from("st_zones").select("*").eq("active", true).order("sort"),
      ]);
      return { products: unwrap(p), zones: unwrap(z) };
    },
    placeOrder: async (payload) => unwrap(await must().rpc("st_place_order", { p: payload })),
    track: async (token) => unwrap(await must().rpc("st_track", { p_token: token })),
    subscribeOrder(token, onUpdate, onStatus) {
      const ch = must().channel(`st-order-${token}`)
        .on("broadcast", { event: "order_update" }, (msg) => onUpdate(msg.payload))
        .subscribe((status) => onStatus && onStatus(status));
      return () => client.removeChannel(ch);
    },

    // ---------- staff & drivers ----------
    async signIn(email, password) { return unwrap(await must().auth.signInWithPassword({ email, password })); },
    async signOut() { await must().auth.signOut(); },
    async session() { return (await must().auth.getSession()).data.session; },
    async me() {
      const s = await this.session(); if (!s) return null;
      const rows = unwrap(await client.from("st_staff").select("*").eq("user_id", s.user.id).eq("active", true));
      return rows[0] ? { ...rows[0], email: s.user.email } : null;
    },
    async orders({ since } = {}) {
      let q = must().from("st_orders").select("*").order("created_at", { ascending: false }).limit(200);
      if (since) q = q.gte("created_at", since);
      return unwrap(await q);
    },
    issueInvoice: async (id) => unwrap(await must().rpc("st_issue_invoice", { p_order: id })),
    // only succeeds while nobody else has taken the delivery
    async claimOrder(id, patch) {
      const rows = unwrap(await must().from("st_orders").update(patch).eq("id", id).is("driver_id", null).select());
      if (!rows.length) throw new Error("taken");
      return rows[0];
    },
    async updateOrder(id, patch) { return unwrap(await must().from("st_orders").update(patch).eq("id", id).select().single()); },
    onOrdersChange(cb) {
      const ch = must().channel("st-staff-orders")
        .on("postgres_changes", { event: "*", schema: "public", table: "st_orders" }, (e) => cb(e))
        .subscribe();
      return () => client.removeChannel(ch);
    },
  };
})();
