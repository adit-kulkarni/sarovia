-- Migration: Add analyzed_conversations field to user_knowledge table
-- This enables incremental knowledge analysis

-- Add the analyzed_conversations column
ALTER TABLE user_knowledge 
ADD COLUMN analyzed_conversations JSONB DEFAULT '[]'::jsonb;

-- Update existing records to have empty arrays
UPDATE user_knowledge 
SET analyzed_conversations = '[]'::jsonb 
WHERE analyzed_conversations IS NULL;

-- Add a comment for documentation
COMMENT ON COLUMN user_knowledge.analyzed_conversations IS 'Array of conversation IDs that have been analyzed for this knowledge record';

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    column_default,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'user_knowledge' 
ORDER BY ordinal_position; 