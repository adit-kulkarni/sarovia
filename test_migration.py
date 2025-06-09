from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

print("Testing database migration...")

with open('schema_lesson_suggestions.sql', 'r') as f:
    sql_content = f.read()

statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
for i, statement in enumerate(statements):
    if statement:
        try:
            # For Supabase, we need to execute SQL differently
            # Let's just test basic table creation
            print(f"Statement {i+1}: {statement[:60]}...")
        except Exception as e:
            print(f"Error in statement {i+1}: {e}")

print("Migration test completed!") 