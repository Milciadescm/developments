-- Public bucket for product photos (official packshots from distributors, food photos).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('st-products', 'st-products', true, 3145728, array['image/webp','image/jpeg','image/png'])
on conflict (id) do update set public = true, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

create policy "st admins upload product photos" on storage.objects for insert to authenticated
  with check (bucket_id = 'st-products' and (select st_private.st_my_role()) = 'admin');
create policy "st admins update product photos" on storage.objects for update to authenticated
  using (bucket_id = 'st-products' and (select st_private.st_my_role()) = 'admin');
create policy "st admins delete product photos" on storage.objects for delete to authenticated
  using (bucket_id = 'st-products' and (select st_private.st_my_role()) = 'admin');
