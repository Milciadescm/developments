-- Move the permission helpers out of the public API schema (policies keep working: they reference the functions directly).
create schema if not exists st_private;
grant usage on schema st_private to anon, authenticated;
alter function public.st_is_staff() set schema st_private;
alter function public.st_my_role() set schema st_private;
revoke all on function st_private.st_is_staff() from public;
revoke all on function st_private.st_my_role() from public;
grant execute on function st_private.st_is_staff() to anon, authenticated;
grant execute on function st_private.st_my_role() to authenticated;
