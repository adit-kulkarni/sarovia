-- Create conversations table
create table conversations (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    context text not null,
    language text not null,
    level text not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create messages table
create table messages (
    id uuid default gen_random_uuid() primary key,
    conversation_id uuid references conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create indexes for better query performance
create index conversations_user_id_idx on conversations(user_id);
create index messages_conversation_id_idx on messages(conversation_id);

-- Enable Row Level Security (RLS)
alter table conversations enable row level security;
alter table messages enable row level security;

-- Create policies
create policy "Users can view their own conversations"
    on conversations for select
    using (auth.uid() = user_id);

create policy "Users can insert their own conversations"
    on conversations for insert
    with check (auth.uid() = user_id);

create policy "Users can view messages from their conversations"
    on messages for select
    using (
        exists (
            select 1 from conversations
            where conversations.id = messages.conversation_id
            and conversations.user_id = auth.uid()
        )
    );

create policy "Users can insert messages to their conversations"
    on messages for insert
    with check (
        exists (
            select 1 from conversations
            where conversations.id = messages.conversation_id
            and conversations.user_id = auth.uid()
        )
    ); 