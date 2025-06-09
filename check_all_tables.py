from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL') 
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

print("Checking existing tables...")

tables_to_check = [
    'conversations',
    'messages', 
    'message_feedback',
    'custom_lesson_templates',
    'lesson_suggestions',
    'user_suggestion_limits'
]

for table in tables_to_check:
    try:
        result = supabase.table(table).select('*').limit(1).execute()
        print(f'✓ {table} exists')
    except Exception as e:
        if 'does not exist' in str(e):
            print(f'✗ {table} missing')
        else:
            print(f'? {table} error: {e}') 