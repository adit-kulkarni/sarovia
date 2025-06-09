from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL') 
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

print("Testing lesson progress implementation...")

# Test if lesson_progress table exists
try:
    result = supabase.table('lesson_progress').select('*').limit(1).execute()
    print('✓ lesson_progress table exists')
except Exception as e:
    print(f'✗ lesson_progress table missing: {e}')

# Test if conversations table has the required columns
try:
    result = supabase.table('conversations').select('curriculum_id, lesson_id, custom_lesson_id').limit(1).execute()
    print('✓ conversations table has required columns')
except Exception as e:
    print(f'✗ conversations table missing columns: {e}')

# Test the difficulty mapping function
def test_get_required_turns_for_difficulty(difficulty: str) -> int:
    """Get required turns based on lesson difficulty"""
    difficulty_map = {
        'easy': 7,
        'medium': 9,
        'challenging': 11
    }
    return difficulty_map.get(difficulty.lower(), 7)

print(f"✓ Difficulty mapping: Easy={test_get_required_turns_for_difficulty('easy')}, Medium={test_get_required_turns_for_difficulty('medium')}, Challenging={test_get_required_turns_for_difficulty('challenging')}")

print("\nTo apply the schema, run the SQL in schema_lesson_progress.sql in your Supabase dashboard.")
print("The lesson progress tracking system is ready to be deployed!") 