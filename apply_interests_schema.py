#!/usr/bin/env python3
"""
Apply user interests schema to Supabase
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def apply_interests_schema():
    # Initialize Supabase client
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        return False
    
    supabase = create_client(url, key)
    
    # Read schema file
    try:
        with open('schema_user_interests.sql', 'r') as f:
            schema_sql = f.read()
    except FileNotFoundError:
        print("Error: schema_user_interests.sql file not found")
        return False
    
    print("Applying user interests schema...")
    
    try:
        # Execute the schema SQL
        result = supabase.rpc('exec_sql', {'sql': schema_sql}).execute()
        print("✅ User interests schema applied successfully!")
        return True
    except Exception as e:
        print(f"❌ Error applying schema: {e}")
        print("🔧 Please run the schema_user_interests.sql file manually in your Supabase SQL editor")
        return False

if __name__ == "__main__":
    apply_interests_schema() 