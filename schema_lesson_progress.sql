-- Add missing columns to conversations table if they don't exist
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS curriculum_id UUID,
ADD COLUMN IF NOT EXISTS lesson_id UUID;

-- Create lesson_progress table for tracking user progress through lessons
CREATE TABLE lesson_progress (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    lesson_id UUID, -- References lesson_templates.id
    custom_lesson_id UUID, -- References custom_lesson_templates.id  
    curriculum_id UUID NOT NULL,
    status VARCHAR(20) DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed')),
    conversation_id UUID, -- Which conversation completed this lesson
    turns_completed INTEGER DEFAULT 0,
    required_turns INTEGER DEFAULT 7, -- Based on lesson difficulty
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, lesson_id, curriculum_id), -- One progress record per user per lesson
    UNIQUE(user_id, custom_lesson_id, curriculum_id) -- One progress record per user per custom lesson
);

-- Create indexes for efficient querying
CREATE INDEX idx_lesson_progress_user_curriculum ON lesson_progress(user_id, curriculum_id);
CREATE INDEX idx_lesson_progress_status ON lesson_progress(status);
CREATE INDEX idx_lesson_progress_lesson ON lesson_progress(lesson_id);
CREATE INDEX idx_lesson_progress_custom_lesson ON lesson_progress(custom_lesson_id);

-- Enable Row Level Security
ALTER TABLE lesson_progress ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own lesson progress" ON lesson_progress
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert their own lesson progress" ON lesson_progress
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update their own lesson progress" ON lesson_progress
    FOR UPDATE USING (auth.uid()::text = user_id::text);

-- Function to get required turns based on difficulty
CREATE OR REPLACE FUNCTION get_required_turns_for_lesson(lesson_difficulty TEXT)
RETURNS INTEGER AS $$
BEGIN
    CASE 
        WHEN LOWER(lesson_difficulty) = 'easy' THEN RETURN 7;
        WHEN LOWER(lesson_difficulty) = 'medium' THEN RETURN 9;
        WHEN LOWER(lesson_difficulty) = 'challenging' THEN RETURN 11;
        ELSE RETURN 7; -- Default to easy
    END CASE;
END;
$$ LANGUAGE plpgsql; 