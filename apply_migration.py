import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Get the API token from environment or manually set it
# We'll need a valid user token to call the migration endpoint
print("To apply the migration, we need to use the apply_migration API endpoint.")
print("This requires a user authentication token.")
print("\nYou can get a token by:")
print("1. Going to the frontend app")
print("2. Opening browser developer tools")
print("3. Looking at network requests to see the token parameter")
print("4. Or using the Supabase dashboard to run the SQL directly")

# Read the SQL file
with open('schema_lesson_suggestions.sql', 'r') as f:
    sql_content = f.read()

print(f"\nSQL to execute:")
print("=" * 50)
print(sql_content)
print("=" * 50)

print("\nOption 1: Copy the SQL above and run it manually in Supabase dashboard")
print("Option 2: Provide a valid token to run via API")

token = input("\nEnter auth token (or press Enter to skip): ").strip()

if token:
    try:
        response = requests.post(
            'http://localhost:8000/api/lesson_suggestions/apply_migration',
            params={'token': token},
            json={'sql': sql_content, 'name': 'create_lesson_suggestions_tables'}
        )
        if response.ok:
            print("✓ Migration applied successfully!")
        else:
            print(f"✗ Migration failed: {response.status_code} {response.text}")
    except Exception as e:
        print(f"✗ Error applying migration: {e}")
        print("You can run the SQL manually in Supabase dashboard instead.")
else:
    print("No token provided. Please run the SQL manually in Supabase dashboard.") 