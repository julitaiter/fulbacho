create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.groups (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) > 0),
  code char(6) not null unique,
  created_by uuid not null references public.profiles (id),
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.group_members (
  group_id uuid not null references public.groups (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  role text not null check (role in ('admin', 'member')),
  joined_at timestamptz not null default timezone('utc', now()),
  primary key (group_id, user_id)
);

create table if not exists public.players (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.groups (id) on delete cascade,
  name text not null check (char_length(trim(name)) > 0),
  linked_user_id uuid references public.profiles (id) on delete set null,
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.matches (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.groups (id) on delete cascade,
  played_at timestamptz not null default timezone('utc', now()),
  modality text not null check (modality in ('futbol5', 'futbol6')),
  location text,
  team_a_name text not null check (char_length(trim(team_a_name)) > 0),
  team_b_name text not null check (char_length(trim(team_b_name)) > 0),
  score_a integer not null check (score_a >= 0),
  score_b integer not null check (score_b >= 0),
  created_by uuid not null references public.profiles (id),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.match_players (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches (id) on delete cascade,
  player_id uuid not null references public.players (id),
  team text not null check (team in ('A', 'B')),
  created_at timestamptz not null default timezone('utc', now()),
  unique (match_id, player_id)
);

create table if not exists public.goals (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches (id) on delete cascade,
  player_id uuid references public.players (id),
  own_goal boolean not null default false,
  team_scored_for text not null check (team_scored_for in ('A', 'B')),
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_group_members_user on public.group_members (user_id);
create index if not exists idx_players_group on public.players (group_id, active);
create index if not exists idx_matches_group_played_at on public.matches (group_id, played_at desc);
create index if not exists idx_match_players_match on public.match_players (match_id);
create index if not exists idx_goals_match on public.goals (match_id);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    coalesce(
      new.raw_user_meta_data ->> 'full_name',
      split_part(new.email, '@', 1),
      'Jugador'
    )
  )
  on conflict (id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_new_user();

create or replace function public.generate_group_code()
returns char(6)
language plpgsql
as $$
declare
  alphabet constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  candidate text;
  already_exists boolean;
begin
  loop
    candidate := '';

    for i in 1..6 loop
      candidate := candidate || substr(alphabet, 1 + floor(random() * length(alphabet))::integer, 1);
    end loop;

    select exists (
      select 1
      from public.groups
      where code = candidate
    )
    into already_exists;

    exit when not already_exists;
  end loop;

  return candidate::char(6);
end;
$$;

create or replace function public.assign_group_code()
returns trigger
language plpgsql
as $$
begin
  if new.code is null or trim(new.code::text) = '' then
    new.code = public.generate_group_code();
  else
    new.code = upper(new.code::text)::char(6);
  end if;

  return new;
end;
$$;

drop trigger if exists trg_groups_assign_code on public.groups;
create trigger trg_groups_assign_code
before insert on public.groups
for each row
execute function public.assign_group_code();

drop trigger if exists trg_matches_set_updated_at on public.matches;
create trigger trg_matches_set_updated_at
before update on public.matches
for each row
execute function public.set_updated_at();

create or replace function public.is_group_member(target_group_id uuid, target_user_id uuid default auth.uid())
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.group_members gm
    where gm.group_id = target_group_id
      and gm.user_id = coalesce(target_user_id, auth.uid())
  );
$$;

create or replace function public.is_group_admin(target_group_id uuid, target_user_id uuid default auth.uid())
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.group_members gm
    where gm.group_id = target_group_id
      and gm.user_id = coalesce(target_user_id, auth.uid())
      and gm.role = 'admin'
  );
$$;

create or replace function public.match_is_editable(target_match_id uuid)
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.matches m
    where m.id = target_match_id
      and m.created_at >= timezone('utc', now()) - interval '24 hours'
  );
$$;

create or replace function public.validate_match_player_group_consistency()
returns trigger
language plpgsql
as $$
declare
  match_group_id uuid;
  player_group_id uuid;
begin
  select group_id into match_group_id
  from public.matches
  where id = new.match_id;

  select group_id into player_group_id
  from public.players
  where id = new.player_id;

  if match_group_id is null then
    raise exception 'El partido no existe.';
  end if;

  if player_group_id is null then
    raise exception 'El jugador no existe.';
  end if;

  if match_group_id <> player_group_id then
    raise exception 'El jugador no pertenece al mismo grupo que el partido.';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_match_players_validate_group on public.match_players;
create trigger trg_match_players_validate_group
before insert or update on public.match_players
for each row
execute function public.validate_match_player_group_consistency();

create or replace function public.sync_goal_team_and_validate_player()
returns trigger
language plpgsql
as $$
declare
  player_team text;
  expected_team text;
begin
  if new.player_id is null then
    return new;
  end if;

  select mp.team
  into player_team
  from public.match_players mp
  where mp.match_id = new.match_id
    and mp.player_id = new.player_id;

  if player_team is null then
    raise exception 'El jugador debe estar asignado al partido antes de registrar un gol.';
  end if;

  expected_team := case
    when new.own_goal then case when player_team = 'A' then 'B' else 'A' end
    else player_team
  end;

  if new.team_scored_for <> expected_team then
    raise exception 'El equipo beneficiado por el gol no coincide con la lógica del partido.';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_goals_sync_team on public.goals;
create trigger trg_goals_sync_team
before insert or update on public.goals
for each row
execute function public.sync_goal_team_and_validate_player();

create or replace function public.check_match_goal_totals()
returns trigger
language plpgsql
as $$
declare
  target_match_id uuid;
  target_score_a integer;
  target_score_b integer;
  goals_for_a integer;
  goals_for_b integer;
begin
  target_match_id := coalesce(new.match_id, old.match_id);

  select m.score_a, m.score_b
  into target_score_a, target_score_b
  from public.matches m
  where m.id = target_match_id;

  select
    count(*) filter (where g.team_scored_for = 'A'),
    count(*) filter (where g.team_scored_for = 'B')
  into goals_for_a, goals_for_b
  from public.goals g
  where g.match_id = target_match_id;

  if coalesce(goals_for_a, 0) > target_score_a or coalesce(goals_for_b, 0) > target_score_b then
    raise exception 'Los goles registrados no pueden superar el marcador final.';
  end if;

  return coalesce(new, old);
end;
$$;

drop trigger if exists trg_goals_check_totals on public.goals;
create trigger trg_goals_check_totals
after insert or update or delete on public.goals
for each row
execute function public.check_match_goal_totals();

create or replace function public.ensure_match_editable()
returns trigger
language plpgsql
as $$
declare
  target_match_id uuid;
begin
  if tg_table_name = 'matches' then
    target_match_id := old.id;
  else
    target_match_id := coalesce(new.match_id, old.match_id);
  end if;

  if not public.match_is_editable(target_match_id) then
    raise exception 'El partido ya no puede editarse después de 24 horas.';
  end if;

  return coalesce(new, old);
end;
$$;

drop trigger if exists trg_matches_editable on public.matches;
create trigger trg_matches_editable
before update or delete on public.matches
for each row
execute function public.ensure_match_editable();

drop trigger if exists trg_match_players_editable on public.match_players;
create trigger trg_match_players_editable
before insert or update or delete on public.match_players
for each row
execute function public.ensure_match_editable();

drop trigger if exists trg_goals_editable on public.goals;
create trigger trg_goals_editable
before insert or update or delete on public.goals
for each row
execute function public.ensure_match_editable();

create or replace function public.create_group(p_name text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_group_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Usuario no autenticado.';
  end if;

  insert into public.groups (name, created_by)
  values (trim(p_name), auth.uid())
  returning id into new_group_id;

  insert into public.group_members (group_id, user_id, role)
  values (new_group_id, auth.uid(), 'admin')
  on conflict (group_id, user_id) do nothing;

  return new_group_id;
end;
$$;

create or replace function public.join_group_by_code(p_code text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  normalized_code char(6);
  target_group_id uuid;
begin
  if auth.uid() is null then
    raise exception 'Usuario no autenticado.';
  end if;

  normalized_code := upper(trim(p_code))::char(6);

  select g.id
  into target_group_id
  from public.groups g
  where g.code = normalized_code;

  if target_group_id is null then
    raise exception 'No existe un grupo con ese código.';
  end if;

  insert into public.group_members (group_id, user_id, role)
  values (target_group_id, auth.uid(), 'member')
  on conflict (group_id, user_id) do nothing;

  return target_group_id;
end;
$$;

create or replace view public.group_stats as
select
  g.id as group_id,
  g.name as group_name,
  count(m.id) as total_matches,
  coalesce(sum(goal_counts.goals_for), 0) as total_goals,
  case
    when count(m.id) = 0 then 0::numeric
    else round(coalesce(sum(goal_counts.goals_for), 0)::numeric / count(m.id)::numeric, 2)
  end as average_goals_per_match,
  max(m.played_at) as last_match_at
from public.groups g
left join public.matches m on m.group_id = g.id
left join lateral (
  select count(*) filter (where own_goal = false) as goals_for
  from public.goals gg
  where gg.match_id = m.id
) goal_counts on true
group by g.id, g.name;

create or replace view public.player_stats as
with player_results as (
  select
    p.group_id,
    p.id as player_id,
    m.id as match_id,
    case
      when m.score_a = m.score_b then 'draw'
      when (mp.team = 'A' and m.score_a > m.score_b) or (mp.team = 'B' and m.score_b > m.score_a) then 'win'
      else 'loss'
    end as result
  from public.players p
  join public.match_players mp on mp.player_id = p.id
  join public.matches m on m.id = mp.match_id
),
goal_totals as (
  select
    m.group_id,
    g.player_id,
    count(*) filter (where g.own_goal = false and g.player_id is not null) as goals_for,
    count(*) filter (where g.own_goal = true and g.player_id is not null) as own_goals
  from public.goals g
  join public.matches m on m.id = g.match_id
  where g.player_id is not null
  group by m.group_id, g.player_id
)
select
  p.group_id,
  p.id as player_id,
  p.name,
  p.active,
  count(pr.match_id) as matches_played,
  count(*) filter (where pr.result = 'win') as wins,
  count(*) filter (where pr.result = 'loss') as losses,
  count(*) filter (where pr.result = 'draw') as draws,
  coalesce(gt.goals_for, 0) as goals_for,
  coalesce(gt.own_goals, 0) as own_goals,
  coalesce(gt.goals_for, 0) - coalesce(gt.own_goals, 0) as net_goals,
  case
    when count(pr.match_id) = 0 then 0::numeric
    else round(
      (count(*) filter (where pr.result = 'win'))::numeric / count(pr.match_id)::numeric * 100,
      2
    )
  end as win_percentage,
  case
    when count(pr.match_id) = 0 then 0::numeric
    else round(coalesce(gt.goals_for, 0)::numeric / count(pr.match_id)::numeric, 2)
  end as goals_per_match
from public.players p
left join player_results pr
  on pr.player_id = p.id
 and pr.group_id = p.group_id
left join goal_totals gt
  on gt.player_id = p.id
 and gt.group_id = p.group_id
group by
  p.group_id,
  p.id,
  p.name,
  p.active,
  gt.goals_for,
  gt.own_goals;

alter table public.profiles enable row level security;
alter table public.groups enable row level security;
alter table public.group_members enable row level security;
alter table public.players enable row level security;
alter table public.matches enable row level security;
alter table public.match_players enable row level security;
alter table public.goals enable row level security;

drop policy if exists "profiles_select_self" on public.profiles;
create policy "profiles_select_self"
on public.profiles
for select
using (auth.uid() = id);

drop policy if exists "profiles_update_self" on public.profiles;
create policy "profiles_update_self"
on public.profiles
for update
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists "groups_select_member" on public.groups;
create policy "groups_select_member"
on public.groups
for select
using (public.is_group_member(id));

drop policy if exists "groups_insert_creator" on public.groups;
create policy "groups_insert_creator"
on public.groups
for insert
with check (auth.uid() = created_by);

drop policy if exists "groups_update_admin" on public.groups;
create policy "groups_update_admin"
on public.groups
for update
using (public.is_group_admin(id))
with check (public.is_group_admin(id));

drop policy if exists "groups_delete_admin" on public.groups;
create policy "groups_delete_admin"
on public.groups
for delete
using (public.is_group_admin(id));

drop policy if exists "group_members_select_member" on public.group_members;
create policy "group_members_select_member"
on public.group_members
for select
using (public.is_group_member(group_id));

drop policy if exists "group_members_manage_admin" on public.group_members;
create policy "group_members_manage_admin"
on public.group_members
for update
using (public.is_group_admin(group_id))
with check (public.is_group_admin(group_id));

drop policy if exists "group_members_delete_admin" on public.group_members;
create policy "group_members_delete_admin"
on public.group_members
for delete
using (public.is_group_admin(group_id));

drop policy if exists "players_select_member" on public.players;
create policy "players_select_member"
on public.players
for select
using (public.is_group_member(group_id));

drop policy if exists "players_insert_member" on public.players;
create policy "players_insert_member"
on public.players
for insert
with check (public.is_group_member(group_id));

drop policy if exists "players_update_member" on public.players;
create policy "players_update_member"
on public.players
for update
using (public.is_group_member(group_id))
with check (public.is_group_member(group_id));

drop policy if exists "matches_select_member" on public.matches;
create policy "matches_select_member"
on public.matches
for select
using (public.is_group_member(group_id));

drop policy if exists "matches_insert_member" on public.matches;
create policy "matches_insert_member"
on public.matches
for insert
with check (public.is_group_member(group_id));

drop policy if exists "matches_update_member" on public.matches;
create policy "matches_update_member"
on public.matches
for update
using (public.is_group_member(group_id))
with check (public.is_group_member(group_id));

drop policy if exists "matches_delete_member" on public.matches;
create policy "matches_delete_member"
on public.matches
for delete
using (public.is_group_member(group_id));

drop policy if exists "match_players_select_member" on public.match_players;
create policy "match_players_select_member"
on public.match_players
for select
using (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "match_players_insert_member" on public.match_players;
create policy "match_players_insert_member"
on public.match_players
for insert
with check (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "match_players_update_member" on public.match_players;
create policy "match_players_update_member"
on public.match_players
for update
using (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
)
with check (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "match_players_delete_member" on public.match_players;
create policy "match_players_delete_member"
on public.match_players
for delete
using (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "goals_select_member" on public.goals;
create policy "goals_select_member"
on public.goals
for select
using (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "goals_insert_member" on public.goals;
create policy "goals_insert_member"
on public.goals
for insert
with check (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "goals_update_member" on public.goals;
create policy "goals_update_member"
on public.goals
for update
using (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
)
with check (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

drop policy if exists "goals_delete_member" on public.goals;
create policy "goals_delete_member"
on public.goals
for delete
using (
  exists (
    select 1
    from public.matches m
    where m.id = match_id
      and public.is_group_member(m.group_id)
  )
);

grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant execute on function public.create_group(text) to authenticated;
grant execute on function public.join_group_by_code(text) to authenticated;
