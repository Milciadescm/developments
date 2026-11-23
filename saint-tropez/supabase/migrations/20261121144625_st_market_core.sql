-- Saint Tropez Market 24/7: online orders + live delivery tracking. All objects prefixed st_.

create table public.st_staff (
  user_id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  role text not null default 'staff' check (role in ('admin','staff','driver')),
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.st_zones (
  id text primary key,
  name_es text not null,
  name_en text not null,
  fee numeric(10,2) not null check (fee >= 0),
  eta text not null,
  sort int not null default 0,
  active boolean not null default true
);

create table public.st_products (
  id text primary key,
  cat text not null,
  name_es text not null,
  name_en text not null,
  unit text not null default '',
  price numeric(10,2) not null check (price >= 0),
  was numeric(10,2),
  emoji text,
  img text,
  alcohol boolean not null default false,
  popular boolean not null default false,
  sort int not null default 0,
  active boolean not null default true,
  updated_at timestamptz not null default now()
);

create sequence public.st_order_seq start 1001;

create table public.st_orders (
  id uuid primary key default gen_random_uuid(),
  code text not null unique default ('ST-' || nextval('public.st_order_seq')),
  track_token uuid not null unique default gen_random_uuid(),
  status text not null default 'pending'
    check (status in ('pending','confirmed','preparing','on_the_way','ready','delivered','cancelled')),
  status_times jsonb not null default '{}'::jsonb,
  mode text not null check (mode in ('delivery','pickup')),
  lang text not null default 'es',
  zone_id text references public.st_zones(id),
  zone_name text,
  place text,
  room text,
  driver_notes text,
  dest_lat double precision,
  dest_lng double precision,
  scheduled_for timestamptz,
  customer_name text not null,
  customer_phone text not null,
  payment text not null,
  cash_for text,
  items jsonb not null,
  subtotal numeric(10,2) not null,
  delivery_fee numeric(10,2) not null default 0,
  tip numeric(10,2) not null default 0,
  total numeric(10,2) not null,
  age_confirmed boolean,
  driver_id uuid references auth.users(id),
  driver_name text,
  driver_lat double precision,
  driver_lng double precision,
  driver_heading double precision,
  driver_updated_at timestamptz,
  staff_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index st_orders_status_idx on public.st_orders (status, created_at desc);
create index st_orders_driver_idx on public.st_orders (driver_id) where driver_id is not null;

-- ---------- helpers ----------
create or replace function public.st_is_staff() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.st_staff s where s.user_id = auth.uid() and s.active);
$$;

create or replace function public.st_my_role() returns text
language sql stable security definer set search_path = '' as $$
  select s.role from public.st_staff s where s.user_id = auth.uid() and s.active;
$$;

-- ---------- RLS ----------
alter table public.st_staff enable row level security;
alter table public.st_zones enable row level security;
alter table public.st_products enable row level security;
alter table public.st_orders enable row level security;

create policy "staff read staff" on public.st_staff for select to authenticated using ((select public.st_is_staff()));

create policy "anyone reads active zones" on public.st_zones for select to anon, authenticated using (active or (select public.st_is_staff()));
create policy "admin manages zones" on public.st_zones for all to authenticated
  using ((select public.st_my_role()) = 'admin') with check ((select public.st_my_role()) = 'admin');

create policy "anyone reads active products" on public.st_products for select to anon, authenticated using (active or (select public.st_is_staff()));
create policy "admin manages products" on public.st_products for all to authenticated
  using ((select public.st_my_role()) = 'admin') with check ((select public.st_my_role()) = 'admin');

create policy "staff read orders" on public.st_orders for select to authenticated using ((select public.st_is_staff()));
create policy "staff update orders" on public.st_orders for update to authenticated
  using ((select public.st_is_staff())) with check ((select public.st_is_staff()));
-- no insert/delete policies: customers create orders only through st_place_order()

-- ---------- triggers ----------
create or replace function public.st_orders_before_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  if new.status is distinct from old.status then
    new.status_times := coalesce(old.status_times, '{}'::jsonb) || jsonb_build_object(new.status, now());
  end if;
  -- customers' details and money can't be edited from the dashboard
  new.items := old.items; new.subtotal := old.subtotal; new.total := old.total;
  new.track_token := old.track_token; new.code := old.code;
  return new;
end $$;
create trigger st_orders_bu before update on public.st_orders for each row execute function public.st_orders_before_update();

-- push a small public payload to the customer's private tracking channel
create or replace function public.st_orders_broadcast() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform realtime.send(
    jsonb_build_object(
      'status', new.status, 'status_times', new.status_times,
      'driver_name', new.driver_name, 'driver_lat', new.driver_lat, 'driver_lng', new.driver_lng,
      'driver_heading', new.driver_heading, 'driver_updated_at', new.driver_updated_at),
    'order_update', 'st-order-' || new.track_token::text, false);
  return null;
end $$;
create trigger st_orders_au after update on public.st_orders for each row execute function public.st_orders_broadcast();

-- ---------- customer API ----------
create or replace function public.st_place_order(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  v_mode text := p->>'mode';
  v_zone public.st_zones;
  v_items jsonb := '[]'::jsonb;
  v_line jsonb;
  v_prod public.st_products;
  v_qty int;
  v_sub numeric := 0;
  v_fee numeric := 0;
  v_tip_pct numeric := least(greatest(coalesce((p->>'tip_pct')::numeric, 0), 0), 30);
  v_tip numeric := 0;
  v_alcohol boolean := false;
  v_min numeric := 500;
  v_order public.st_orders;
begin
  if v_mode not in ('delivery','pickup') then raise exception 'invalid mode'; end if;
  if jsonb_typeof(p->'items') <> 'array' or jsonb_array_length(p->'items') = 0 or jsonb_array_length(p->'items') > 60 then
    raise exception 'invalid items';
  end if;
  if length(coalesce(trim(p->>'customer_name'),'')) = 0 or length(regexp_replace(coalesce(p->>'customer_phone',''), '\D', '', 'g')) < 7 then
    raise exception 'missing contact';
  end if;

  for v_line in select * from jsonb_array_elements(p->'items') loop
    select * into v_prod from public.st_products where id = v_line->>'id' and active;
    if not found then raise exception 'unknown product %', v_line->>'id'; end if;
    v_qty := (v_line->>'qty')::int;
    if v_qty is null or v_qty < 1 or v_qty > 99 then raise exception 'invalid quantity'; end if;
    v_sub := v_sub + v_prod.price * v_qty;
    v_alcohol := v_alcohol or v_prod.alcohol;
    v_items := v_items || jsonb_build_object(
      'id', v_prod.id, 'name_es', v_prod.name_es, 'name_en', v_prod.name_en, 'unit', v_prod.unit,
      'price', v_prod.price, 'qty', v_qty, 'notes', left(coalesce(v_line->>'notes',''), 140), 'emoji', v_prod.emoji);
  end loop;

  if v_alcohol and coalesce((p->>'age_confirmed')::boolean, false) is not true then raise exception 'age confirmation required'; end if;

  if v_mode = 'delivery' then
    select * into v_zone from public.st_zones where id = p->>'zone_id' and active;
    if not found then raise exception 'invalid zone'; end if;
    if length(coalesce(trim(p->>'place'),'')) = 0 then raise exception 'missing place'; end if;
    if v_sub < v_min then raise exception 'below minimum'; end if;
    v_fee := v_zone.fee;
    v_tip := round(v_sub * v_tip_pct / 100);
  end if;

  insert into public.st_orders (mode, lang, zone_id, zone_name, place, room, driver_notes, dest_lat, dest_lng, scheduled_for,
    customer_name, customer_phone, payment, cash_for, items, subtotal, delivery_fee, tip, total, age_confirmed, status_times)
  values (v_mode, case when p->>'lang' = 'en' then 'en' else 'es' end,
    case when v_mode = 'delivery' then v_zone.id end,
    case when v_mode = 'delivery' then case when p->>'lang' = 'en' then v_zone.name_en else v_zone.name_es end end,
    left(p->>'place', 200), left(p->>'room', 40), left(p->>'driver_notes', 200),
    case when (p->>'dest_lat') ~ '^-?[0-9.]+$' then (p->>'dest_lat')::double precision end,
    case when (p->>'dest_lng') ~ '^-?[0-9.]+$' then (p->>'dest_lng')::double precision end,
    case when nullif(p->>'scheduled_for','') is not null then (p->>'scheduled_for')::timestamptz end,
    left(trim(p->>'customer_name'), 80), left(p->>'customer_phone', 30),
    left(coalesce(p->>'payment','cash'), 20), left(p->>'cash_for', 40),
    v_items, v_sub, v_fee, v_tip, v_sub + v_fee + v_tip,
    case when v_alcohol then true end,
    jsonb_build_object('pending', now()))
  returning * into v_order;

  return jsonb_build_object('code', v_order.code, 'track_token', v_order.track_token,
    'subtotal', v_order.subtotal, 'delivery_fee', v_order.delivery_fee, 'tip', v_order.tip, 'total', v_order.total);
end $$;

create or replace function public.st_track(p_token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'code', o.code, 'status', o.status, 'status_times', o.status_times, 'mode', o.mode, 'lang', o.lang,
    'zone_id', o.zone_id, 'zone_name', o.zone_name, 'place', o.place, 'room', o.room,
    'dest_lat', o.dest_lat, 'dest_lng', o.dest_lng, 'scheduled_for', o.scheduled_for,
    'customer_name', o.customer_name, 'payment', o.payment, 'items', o.items,
    'subtotal', o.subtotal, 'delivery_fee', o.delivery_fee, 'tip', o.tip, 'total', o.total,
    'driver_name', o.driver_name, 'driver_lat', o.driver_lat, 'driver_lng', o.driver_lng,
    'driver_heading', o.driver_heading, 'driver_updated_at', o.driver_updated_at,
    'eta', (select z.eta from public.st_zones z where z.id = o.zone_id),
    'created_at', o.created_at)
  from public.st_orders o where o.track_token = p_token;
$$;

revoke all on function public.st_place_order(jsonb) from public;
revoke all on function public.st_track(uuid) from public;
grant execute on function public.st_place_order(jsonb) to anon, authenticated;
grant execute on function public.st_track(uuid) to anon, authenticated;
revoke all on function public.st_orders_broadcast() from public, anon, authenticated;

-- staff dashboard receives row changes (RLS limits them to staff)
alter publication supabase_realtime add table public.st_orders;
