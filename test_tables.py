from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL') 
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

print("Testing database tables...")

# Test if lesson_suggestions table exists
try:
    result = supabase.table('lesson_suggestions').select('*').limit(1).execute()
    print('✓ lesson_suggestions table exists')
except Exception as e:
    print(f'✗ lesson_suggestions table missing: {e}')

# Test if user_suggestion_limits table exists  
try:
    result = supabase.table('user_suggestion_limits').select('*').limit(1).execute()
    print('✓ user_suggestion_limits table exists')
except Exception as e:
    print(f'✗ user_suggestion_limits table missing: {e}') 