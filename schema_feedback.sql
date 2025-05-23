-- Create message_feedback table
create table message_feedback (
    id uuid default gen_random_uuid() primary key,
    message_id uuid references messages(id) on delete cascade,
    original_message text not null,
    mistakes jsonb not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Add index for better query performance
create index message_feedback_message_id_idx on message_feedback(message_id);

-- Add RLS policy
alter table message_feedback enable row level security;

create policy "Users can view feedback from their messages"
    on message_feedback for select
    using (
        exists (
            select 1 from messages
            join conversations on conversations.id = messages.conversation_id
            where messages.id = message_feedback.message_id
            and conversations.user_id = auth.uid()
        )
    ); 