# Lesson Progress Tracking Implementation

## Overview
This system tracks user progress through conversation-based lessons using a turn-counting mechanism with completion thresholds based on lesson difficulty.

## Key Features

### 1. Turn-Based Progress Tracking
- **Turn Definition**: 1 turn = user message + AI response
- **Real-time Tracking**: Progress updates sent to frontend via WebSocket
- **Difficulty-Based Thresholds**:
  - Easy: 7 turns (14 total messages)
  - Medium: 9 turns (18 total messages)  
  - Challenging: 11 turns (22 total messages)

### 2. Database Schema

#### `lesson_progress` Table
```sql
- id: UUID (primary key)
- user_id: UUID (references auth.users)
- lesson_id: UUID (references lesson_templates - nullable)
- custom_lesson_id: UUID (references custom_lesson_templates - nullable)
- curriculum_id: UUID (required)
- status: VARCHAR(20) ('not_started', 'in_progress', 'completed')
- conversation_id: UUID (which conversation completed the lesson)
- turns_completed: INTEGER (current turn count)
- required_turns: INTEGER (based on lesson difficulty)
- started_at: TIMESTAMPTZ
- completed_at: TIMESTAMPTZ
- created_at: TIMESTAMPTZ
- updated_at: TIMESTAMPTZ
```

#### Enhanced `conversations` Table
- Added `curriculum_id` and `lesson_id` columns for lesson tracking
- Existing `custom_lesson_id` column for custom lessons

### 3. API Endpoints

#### Progress Tracking
- `GET /api/lesson_progress/{progress_id}` - Get specific progress details
- `GET /api/curriculums/{curriculum_id}/progress` - Get all progress for curriculum
- `GET /api/lessons/{lesson_id}/progress` - Get progress for specific lesson
- `GET /api/custom_lessons/{custom_lesson_id}/progress` - Get progress for custom lesson

#### Lesson Completion
- `POST /api/lesson_progress/complete` - Mark lesson as completed
  - Validates minimum turn requirement
  - Updates status to 'completed'
  - Sets completion timestamp

### 4. WebSocket Integration

#### Real-time Progress Updates
```javascript
{
  "type": "lesson.progress",
  "turns": 5,
  "required": 7,
  "can_complete": false,
  "lesson_id": "uuid",
  "custom_lesson_id": "uuid",
  "progress_id": "uuid"
}
```

#### Turn Counting Logic
- Increments on `response.audio_transcript.done` events
- Creates/updates progress records automatically
- Sends progress updates to frontend in real-time

### 5. Frontend Integration Points

#### Progress Display
```javascript
// Progress indicator
Progress: {turns}/{required} turns completed
[✓ Mark lesson complete] ← enabled when turns >= required
```

#### Completion Flow
1. User completes minimum turns
2. Checkbox becomes enabled
3. User clicks to mark complete
4. API call to `/api/lesson_progress/complete`
5. WebSocket disconnection
6. Redirect to lesson list

### 6. Status Flow

```
not_started → in_progress → completed
     ↑           ↑             ↑
   (default)  (auto when    (manual when
              conversation  min turns +
              starts)       user clicks)
```

### 7. Database Functions

#### Difficulty Mapping Function
```sql
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
```

## Usage Examples

### Starting a Lesson Conversation
1. User selects lesson from curriculum
2. Frontend calls existing lesson start endpoints
3. WebSocket connection established with lesson_id in conversation
4. Progress record auto-created on first user message
5. Turn counting begins automatically

### Monitoring Progress
1. Frontend subscribes to `lesson.progress` WebSocket events
2. Real-time updates show current turns vs required
3. Completion checkbox enabled when threshold met

### Completing a Lesson
1. User clicks completion checkbox (when enabled)
2. Frontend calls `POST /api/lesson_progress/complete`
3. Server validates turn requirement
4. Status updated to 'completed' with timestamp
5. WebSocket connection closed
6. User redirected to lesson overview

## Security Features

### Row Level Security (RLS)
- Users can only access their own progress records
- Enforced at database level with auth.uid() policies

### Validation
- Minimum turn requirements enforced
- User ownership verified for all operations
- Curriculum access validated

## Testing

Run `python test_lesson_progress.py` to verify:
- Database tables exist
- Required columns present
- Difficulty mapping works correctly

## Migration Applied

The schema has been successfully applied to your Supabase database using the migration in `schema_lesson_progress.sql`.

## Next Steps

1. Update frontend to handle `lesson.progress` WebSocket events
2. Add progress indicators to lesson lists
3. Implement completion UI with checkbox
4. Test end-to-end lesson completion flow
5. Add progress analytics/reporting features 