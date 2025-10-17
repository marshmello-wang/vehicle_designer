-- Supabase schema for Vehicle Designer backend (MVP)

-- project table
create table if not exists public.project (
  id uuid primary key default gen_random_uuid(),
  name text null,
  created_at timestamptz not null default now()
);

-- version table
create table if not exists public.version (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.project(id) on delete cascade,
  parent_version_id uuid null references public.version(id) on delete set null,
  index int not null,
  interface_name text not null,
  image_mime text not null,
  image_base64 text not null,
  created_at timestamptz not null default now(),
  constraint version_index_unique unique (project_id, index)
);

create index if not exists idx_version_project_index on public.version(project_id, index asc);

