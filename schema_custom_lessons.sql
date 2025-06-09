-- Create custom_lesson_templates table for AI-generated lessons targeting user weaknesses
create table custom_lesson_templates (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    curriculum_id uuid references curriculums(id) on delete cascade,
    title text not null,
    language text not null,
    difficulty text not null,
    objectives text not null,
    content text not null,
    cultural_element text not null,
    practice_activity text not null,
    targeted_weaknesses jsonb not null default '[]',
    order_num integer default 999,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Add index for better query performance
create index custom_lesson_templates_user_id_idx on custom_lesson_templates(user_id);
create index custom_lesson_templates_curriculum_id_idx on custom_lesson_templates(curriculum_id);
create index custom_lesson_templates_language_idx on custom_lesson_templates(language);

-- Add RLS policy
alter table custom_lesson_templates enable row level security;

create policy "Users can view their own custom lessons"
    on custom_lesson_templates for select
    using (auth.uid() = user_id);

create policy "Users can insert their own custom lessons"
    on custom_lesson_templates for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own custom lessons"
    on custom_lesson_templates for update
    using (auth.uid() = user_id);

create policy "Users can delete their own custom lessons"
    on custom_lesson_templates for delete
    using (auth.uid() = user_id);

-- Add custom_lesson_id column to conversations table to track custom lesson conversations
alter table conversations add column custom_lesson_id uuid references custom_lesson_templates(id) on delete set null;

-- Add index for custom lesson conversations
create index conversations_custom_lesson_id_idx on conversations(custom_lesson_id); 