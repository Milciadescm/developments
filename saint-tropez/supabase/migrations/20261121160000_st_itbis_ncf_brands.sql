-- Brands & origin, ITBIS included in prices, fiscal invoices (NCF).

-- ---------- products ----------
alter table public.st_products
  add column if not exists brand text not null default '',
  add column if not exists origin text not null default 'DO',
  add column if not exists itbis_rate numeric(5,2) not null default 18 check (itbis_rate >= 0 and itbis_rate <= 100);
comment on column public.st_products.price is 'Shelf price in RD$, ITBIS included';
comment on column public.st_zones.fee is 'Delivery fee in RD$, ITBIS included';

-- ---------- orders: invoice data ----------
alter table public.st_orders
  add column if not exists invoice_type text not null default 'consumo' check (invoice_type in ('consumo','credito_fiscal')),
  add column if not exists customer_rnc text,
  add column if not exists customer_legal_name text,
  add column if not exists itbis_total numeric(10,2) not null default 0,
  add column if not exists ncf text unique,
  add column if not exists ncf_type text,
  add column if not exists ncf_expires_on date,
  add column if not exists invoiced_at timestamptz;

-- ---------- NCF sequences authorised by DGII ----------
-- One row per comprobante type the store is authorised to issue.
--   B02 = Factura de consumo (consumidor final), B01 = Factura de crédito fiscal.
-- Load each authorised range: next_number = first number of the range, last_number = last, expires_on = due date.
create table if not exists public.st_ncf_sequences (
  ncf_type text primary key check (ncf_type ~ '^[A-Z][0-9]{2}$'),
  description text not null,
  next_number bigint not null check (next_number > 0),
  last_number bigint not null,
  expires_on date,
  active boolean not null default true,
  updated_at timestamptz not null default now()
);
alter table public.st_ncf_sequences enable row level security;
create policy "staff read ncf" on public.st_ncf_sequences for select to authenticated using ((select st_private.st_is_staff()));
create policy "admin manages ncf" on public.st_ncf_sequences for all to authenticated
  using ((select st_private.st_my_role()) = 'admin') with check ((select st_private.st_my_role()) = 'admin');

-- Assigns the next NCF to an order (idempotent: an order keeps its first NCF).
create or replace function st_private.st_assign_ncf(p_order uuid) returns text
language plpgsql security definer set search_path = '' as $$
declare
  o public.st_orders;
  s public.st_ncf_sequences;
  v_type text;
  v_ncf text;
begin
  select * into o from public.st_orders where id = p_order for update;
  if not found then raise exception 'order not found'; end if;
  if o.ncf is not null then return o.ncf; end if;
  if o.status = 'cancelled' then raise exception 'cancelled orders get no NCF'; end if;
  v_type := case when o.invoice_type = 'credito_fiscal' then 'B01' else 'B02' end;
  select * into s from public.st_ncf_sequences where ncf_type = v_type and active for update;
  if not found then return null; end if;                       -- no range loaded yet: invoice stays pending
  if s.next_number > s.last_number then raise exception 'NCF range % exhausted', v_type; end if;
  if s.expires_on is not null and s.expires_on < current_date then raise exception 'NCF range % expired', v_type; end if;
  v_ncf := v_type || lpad(s.next_number::text, 8, '0');
  update public.st_ncf_sequences set next_number = next_number + 1, updated_at = now() where ncf_type = v_type;
  update public.st_orders set ncf = v_ncf, ncf_type = v_type, ncf_expires_on = s.expires_on, invoiced_at = now() where id = p_order;
  return v_ncf;
end $$;
revoke all on function st_private.st_assign_ncf(uuid) from public, anon, authenticated;

-- Staff button "Emitir comprobante"
create or replace function public.st_issue_invoice(p_order uuid) returns text
language plpgsql security definer set search_path = '' as $$
begin
  if not st_private.st_is_staff() then raise exception 'not allowed'; end if;
  return st_private.st_assign_ncf(p_order);
end $$;
revoke all on function public.st_issue_invoice(uuid) from public, anon;
grant execute on function public.st_issue_invoice(uuid) to authenticated;

-- Issue automatically when the sale is completed (delivered / picked up)
create or replace function public.st_orders_after_status() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.status = 'delivered' and old.status is distinct from 'delivered' and new.ncf is null then
    perform st_private.st_assign_ncf(new.id);
  end if;
  return null;
end $$;
drop trigger if exists st_orders_au_ncf on public.st_orders;
create trigger st_orders_au_ncf after update of status on public.st_orders for each row execute function public.st_orders_after_status();
revoke all on function public.st_orders_after_status() from public, anon, authenticated;

-- the dashboard must not overwrite fiscal fields either
create or replace function public.st_orders_before_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  if new.status is distinct from old.status then
    new.status_times := coalesce(old.status_times, '{}'::jsonb) || jsonb_build_object(new.status, now());
  end if;
  new.items := old.items; new.subtotal := old.subtotal; new.total := old.total; new.itbis_total := old.itbis_total;
  new.delivery_fee := old.delivery_fee; new.tip := old.tip;
  new.track_token := old.track_token; new.code := old.code;
  new.invoice_type := old.invoice_type; new.customer_rnc := old.customer_rnc; new.customer_legal_name := old.customer_legal_name;
  if old.ncf is not null then
    new.ncf := old.ncf; new.ncf_type := old.ncf_type; new.ncf_expires_on := old.ncf_expires_on; new.invoiced_at := old.invoiced_at;
  end if;
  return new;
end $$;

-- ---------- place order: per-line ITBIS, invoice type ----------
create or replace function public.st_place_order(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  v_mode text := p->>'mode';
  v_zone public.st_zones;
  v_items jsonb := '[]'::jsonb;
  v_line jsonb;
  v_prod public.st_products;
  v_qty int;
  v_line_total numeric;
  v_line_itbis numeric;
  v_sub numeric := 0;
  v_itbis numeric := 0;
  v_fee numeric := 0;
  v_tip_pct numeric := least(greatest(coalesce((p->>'tip_pct')::numeric, 0), 0), 30);
  v_tip numeric := 0;
  v_alcohol boolean := false;
  v_min numeric := 590;
  v_inv text := case when p->>'invoice_type' = 'credito_fiscal' then 'credito_fiscal' else 'consumo' end;
  v_rnc text := regexp_replace(coalesce(p->>'customer_rnc',''), '\D', '', 'g');
  v_order public.st_orders;
begin
  if v_mode not in ('delivery','pickup') then raise exception 'invalid mode'; end if;
  if jsonb_typeof(p->'items') <> 'array' or jsonb_array_length(p->'items') = 0 or jsonb_array_length(p->'items') > 60 then
    raise exception 'invalid items';
  end if;
  if length(coalesce(trim(p->>'customer_name'),'')) = 0 or length(regexp_replace(coalesce(p->>'customer_phone',''), '\D', '', 'g')) < 7 then
    raise exception 'missing contact';
  end if;
  if v_inv = 'credito_fiscal' then
    if length(v_rnc) not in (9, 11) then raise exception 'invalid rnc'; end if;
    if length(coalesce(trim(p->>'customer_legal_name'),'')) = 0 then raise exception 'missing legal name'; end if;
  end if;

  for v_line in select * from jsonb_array_elements(p->'items') loop
    select * into v_prod from public.st_products where id = v_line->>'id' and active;
    if not found then raise exception 'unknown product %', v_line->>'id'; end if;
    v_qty := (v_line->>'qty')::int;
    if v_qty is null or v_qty < 1 or v_qty > 99 then raise exception 'invalid quantity'; end if;
    v_line_total := v_prod.price * v_qty;
    v_line_itbis := round(v_line_total * v_prod.itbis_rate / (100 + v_prod.itbis_rate), 2);
    v_sub := v_sub + v_line_total;
    v_itbis := v_itbis + v_line_itbis;
    v_alcohol := v_alcohol or v_prod.alcohol;
    v_items := v_items || jsonb_build_object(
      'id', v_prod.id, 'brand', v_prod.brand, 'name_es', v_prod.name_es, 'name_en', v_prod.name_en, 'unit', v_prod.unit,
      'price', v_prod.price, 'qty', v_qty, 'itbis_rate', v_prod.itbis_rate, 'itbis', v_line_itbis, 'total', v_line_total,
      'notes', left(coalesce(v_line->>'notes',''), 140), 'emoji', v_prod.emoji);
  end loop;

  if v_alcohol and coalesce((p->>'age_confirmed')::boolean, false) is not true then raise exception 'age confirmation required'; end if;

  if v_mode = 'delivery' then
    select * into v_zone from public.st_zones where id = p->>'zone_id' and active;
    if not found then raise exception 'invalid zone'; end if;
    if length(coalesce(trim(p->>'place'),'')) = 0 then raise exception 'missing place'; end if;
    if v_sub < v_min then raise exception 'below minimum'; end if;
    v_fee := v_zone.fee;
    v_itbis := v_itbis + round(v_fee * 18 / 118, 2);           -- delivery is a taxed service, ITBIS included
    v_tip := round(v_sub * v_tip_pct / 100);                   -- tips are not subject to ITBIS
  end if;

  insert into public.st_orders (mode, lang, zone_id, zone_name, place, room, driver_notes, dest_lat, dest_lng, scheduled_for,
    customer_name, customer_phone, payment, cash_for, items, subtotal, delivery_fee, tip, total, itbis_total, age_confirmed, status_times,
    invoice_type, customer_rnc, customer_legal_name)
  values (v_mode, case when p->>'lang' = 'en' then 'en' else 'es' end,
    case when v_mode = 'delivery' then v_zone.id end,
    case when v_mode = 'delivery' then case when p->>'lang' = 'en' then v_zone.name_en else v_zone.name_es end end,
    left(p->>'place', 200), left(p->>'room', 40), left(p->>'driver_notes', 200),
    case when (p->>'dest_lat') ~ '^-?[0-9.]+$' then (p->>'dest_lat')::double precision end,
    case when (p->>'dest_lng') ~ '^-?[0-9.]+$' then (p->>'dest_lng')::double precision end,
    case when nullif(p->>'scheduled_for','') is not null then (p->>'scheduled_for')::timestamptz end,
    left(trim(p->>'customer_name'), 80), left(p->>'customer_phone', 30),
    left(coalesce(p->>'payment','cash'), 20), left(p->>'cash_for', 40),
    v_items, v_sub, v_fee, v_tip, v_sub + v_fee + v_tip, v_itbis,
    case when v_alcohol then true end,
    jsonb_build_object('pending', now()),
    v_inv, case when v_inv = 'credito_fiscal' then v_rnc end,
    case when v_inv = 'credito_fiscal' then left(trim(p->>'customer_legal_name'), 120) end)
  returning * into v_order;

  return jsonb_build_object('code', v_order.code, 'track_token', v_order.track_token,
    'subtotal', v_order.subtotal, 'delivery_fee', v_order.delivery_fee, 'tip', v_order.tip,
    'itbis_total', v_order.itbis_total, 'total', v_order.total);
end $$;

-- ---------- tracking / invoice view ----------
create or replace function public.st_track(p_token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'code', o.code, 'status', o.status, 'status_times', o.status_times, 'mode', o.mode, 'lang', o.lang,
    'zone_id', o.zone_id, 'zone_name', o.zone_name, 'place', o.place, 'room', o.room,
    'dest_lat', o.dest_lat, 'dest_lng', o.dest_lng, 'scheduled_for', o.scheduled_for,
    'customer_name', o.customer_name, 'payment', o.payment, 'items', o.items,
    'subtotal', o.subtotal, 'delivery_fee', o.delivery_fee, 'tip', o.tip, 'total', o.total, 'itbis_total', o.itbis_total,
    'invoice_type', o.invoice_type, 'customer_rnc', o.customer_rnc, 'customer_legal_name', o.customer_legal_name,
    'ncf', o.ncf, 'ncf_type', o.ncf_type, 'ncf_expires_on', o.ncf_expires_on, 'invoiced_at', o.invoiced_at,
    'driver_name', o.driver_name, 'driver_lat', o.driver_lat, 'driver_lng', o.driver_lng,
    'driver_heading', o.driver_heading, 'driver_updated_at', o.driver_updated_at,
    'eta', (select z.eta from public.st_zones z where z.id = o.zone_id),
    'created_at', o.created_at)
  from public.st_orders o where o.track_token = p_token;
$$;

-- live payload for the customer's tracking page now also says when the invoice has its NCF
create or replace function public.st_orders_broadcast() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform realtime.send(
    jsonb_build_object(
      'status', new.status, 'status_times', new.status_times,
      'driver_name', new.driver_name, 'driver_lat', new.driver_lat, 'driver_lng', new.driver_lng,
      'driver_heading', new.driver_heading, 'driver_updated_at', new.driver_updated_at,
      'ncf', new.ncf, 'ncf_type', new.ncf_type, 'ncf_expires_on', new.ncf_expires_on, 'invoiced_at', new.invoiced_at),
    'order_update', 'st-order-' || new.track_token::text, false);
  return null;
end $$;
