-- Add completed_at column to conversations table
-- This allows tracking when conversations are manually completed via the "End Conversation" button

ALTER TABLE conversations 
ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- Add an index for efficient querying of completed conversations
CREATE INDEX idx_conversations_completed_at ON conversations(completed_at) WHERE completed_at IS NOT NULL;

-- Add a comment to document the column purpose
COMMENT ON COLUMN conversations.completed_at IS 'Timestamp when conversation was manually completed via End Conversation button'; 