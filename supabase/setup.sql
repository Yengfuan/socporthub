-- One-time Supabase setup for Social Port Hub. Paste into the Supabase SQL editor.
-- Safe to re-run: every statement replaces what it created before.
--
-- Before running, replace the two placeholders in section 2:
--   <APP_URL>      the deployed app, e.g. https://socporthub.vercel.app (no trailing slash)
--   <CRON_SECRET>  the same value as the CRON_SECRET environment variable on Vercel

-- 1. Storage: one private bucket for posters and return photos. The app hands out
--    short-lived signed URLs; the bucket enforces the size and type limits too.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('uploads', 'uploads', false, 10485760,
        array['image/jpeg', 'image/png', 'image/webp', 'application/pdf'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- 2. Secrets the scheduled jobs need, kept in Supabase Vault rather than in job text.
create extension if not exists supabase_vault;
do $$
begin
  perform vault.update_secret(id, '<APP_URL>') from vault.secrets where name = 'socporthub_app_url';
  if not found then perform vault.create_secret('<APP_URL>', 'socporthub_app_url'); end if;
  perform vault.update_secret(id, '<CRON_SECRET>') from vault.secrets where name = 'socporthub_cron_secret';
  if not found then perform vault.create_secret('<CRON_SECRET>', 'socporthub_cron_secret'); end if;
end $$;

-- 3. Scheduler: pg_cron fires, pg_net makes the HTTPS call to /api/cron/<job>.
create extension if not exists pg_cron;
create extension if not exists pg_net;

create or replace function public.socporthub_call_job(job text)
returns bigint
language sql
security definer
set search_path = ''
as $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'socporthub_app_url') || '/api/cron/' || job,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'socporthub_cron_secret')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 30000
  );
$$;
-- Only the scheduler (running as postgres) may call it; RLS-style lockdown for the API roles.
revoke all on function public.socporthub_call_job(text) from public, anon, authenticated;

-- Same cadence as the old in-process loops. Jobs check the local hour themselves.
select cron.schedule('socporthub-grading',           '* * * * *',    $$select public.socporthub_call_job('grading')$$);
select cron.schedule('socporthub-reminder-nudges',   '* * * * *',    $$select public.socporthub_call_job('reminder-nudges')$$);
select cron.schedule('socporthub-collection-digest', '*/10 * * * *', $$select public.socporthub_call_job('collection-digest')$$);
select cron.schedule('socporthub-borrow-reminders',  '*/10 * * * *', $$select public.socporthub_call_job('borrow-reminders')$$);

-- Check it is working (a minute or two after running):
--   select jobname, schedule, active from cron.job where jobname like 'socporthub-%';
--   select status_code, left(content, 120), created from net._http_response order by created desc limit 10;
--
-- Pause everything (e.g. during cutover):
--   update cron.job set active = false where jobname like 'socporthub-%';
