-- How to give someone access to the staff or driver screen:
-- 1. Supabase dashboard → Authentication → Users → "Add user" → enter their email and a password
--    (tick "Auto Confirm User").
-- 2. Run this in the SQL editor, with their email, display name and role ('admin', 'staff' or 'driver'):

insert into public.st_staff (user_id, name, role)
select id, 'Carlos', 'driver' from auth.users where email = 'carlos@example.com'
on conflict (user_id) do update set name = excluded.name, role = excluded.role, active = true;

-- To remove access: update public.st_staff set active = false where user_id = (select id from auth.users where email = '...');
