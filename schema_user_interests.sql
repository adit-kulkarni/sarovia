-- Create user_interests table for storing hierarchical user interests
CREATE TABLE user_interests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    parent_interest TEXT NOT NULL, -- Main category like "Travel", "Cooking", etc.
    child_interest TEXT, -- Specific sub-interest like "south-east-asia", "hiking", etc.
    context TEXT NOT NULL, -- Description of the interest context
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, parent_interest, child_interest) -- Prevent duplicates
);

-- Create indexes for efficient querying
CREATE INDEX idx_user_interests_user_id ON user_interests(user_id);
CREATE INDEX idx_user_interests_parent ON user_interests(parent_interest);
CREATE INDEX idx_user_interests_user_parent ON user_interests(user_id, parent_interest);

-- Enable Row Level Security
ALTER TABLE user_interests ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own interests" ON user_interests
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own interests" ON user_interests
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own interests" ON user_interests
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own interests" ON user_interests
    FOR DELETE USING (auth.uid() = user_id);

-- Add comment for documentation
COMMENT ON TABLE user_interests IS 'Hierarchical user interests with parent categories and specific sub-interests for conversation personalization';
COMMENT ON COLUMN user_interests.parent_interest IS 'Main interest category (e.g., Travel, Cooking, Music)';
COMMENT ON COLUMN user_interests.child_interest IS 'Specific sub-interest under the parent category (e.g., south-east-asia under Travel)';
COMMENT ON COLUMN user_interests.context IS 'Contextual description of what this interest means (e.g., "traveling to south-east-asia")'; 