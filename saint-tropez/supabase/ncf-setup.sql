-- Load the NCF ranges authorised by the DGII (Oficina Virtual → Solicitud de comprobantes).
-- Run once per authorised range in the Supabase SQL editor. Replace the numbers and dates.
--   B02 = Factura de consumo (consumidor final)    B01 = Factura de crédito fiscal (empresas con RNC)
-- next_number = first number of the range, last_number = last number, expires_on = fecha de vencimiento.

insert into public.st_ncf_sequences (ncf_type, description, next_number, last_number, expires_on) values
  ('B02', 'Factura de consumo',        1, 5000, '2027-12-31'),
  ('B01', 'Factura de crédito fiscal', 1, 1000, '2027-12-31')
on conflict (ncf_type) do update
  set next_number = excluded.next_number, last_number = excluded.last_number, expires_on = excluded.expires_on, active = true, updated_at = now();

-- See how many are left:
-- select ncf_type, next_number, last_number, last_number - next_number + 1 as remaining, expires_on from public.st_ncf_sequences;

-- Note: if the business is in the DGII electronic invoicing regime (e-CF, types E31/E32), NCFs come from a
-- certified e-CF provider instead; connect that provider to st_issue_invoice before using it.
