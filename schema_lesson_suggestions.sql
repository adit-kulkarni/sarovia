-- Create lesson suggestions tracking table
CREATE TABLE lesson_suggestions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  curriculum_id UUID NOT NULL,
  suggestion_data JSONB NOT NULL, -- Store the weakness patterns that triggered suggestions
  generated_lessons JSONB, -- Store the generated lesson previews  
  status VARCHAR(20) DEFAULT 'pending', -- pending, viewed, dismissed, used
  suggestions_count INT DEFAULT 0, -- How many suggestions were generated
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  FOREIGN KEY (curriculum_id) REFERENCES curriculums(id) ON DELETE CASCADE
);

-- Create index for efficient querying
CREATE INDEX idx_lesson_suggestions_user_curriculum ON lesson_suggestions(user_id, curriculum_id);
CREATE INDEX idx_lesson_suggestions_status ON lesson_suggestions(status);
CREATE INDEX idx_lesson_suggestions_created_at ON lesson_suggestions(created_at);

-- Row Level Security
ALTER TABLE lesson_suggestions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own lesson suggestions" ON lesson_suggestions
  FOR ALL USING (auth.uid()::text = user_id::text);

-- Track daily suggestion generation limit
CREATE TABLE user_suggestion_limits (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  suggestions_generated INT DEFAULT 0,
  UNIQUE(user_id, date)
);

CREATE INDEX idx_user_suggestion_limits_user_date ON user_suggestion_limits(user_id, date);

ALTER TABLE user_suggestion_limits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own suggestion limits" ON user_suggestion_limits
  FOR ALL USING (auth.uid()::text = user_id::text); 