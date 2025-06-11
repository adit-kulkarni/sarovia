#!/usr/bin/env python3
"""
Apply cached insights schema to Supabase
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def apply_cached_insights_schema():
    # Initialize Supabase client
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        return False
    
    supabase = create_client(url, key)
    
    # Read schema file
    try:
        with open('schema_cached_insights.sql', 'r') as f:
            schema_sql = f.read()
    except FileNotFoundError:
        print("Error: schema_cached_insights.sql file not found")
        return False
    
    print("Applying cached insights schema...")
    
    try:
        # Execute the schema SQL
        result = supabase.rpc('exec_sql', {'sql': schema_sql}).execute()
        print("✅ Cached insights schema applied successfully!")
        return True
    except Exception as e:
        print(f"❌ Error applying schema: {e}")
        
        # Try alternative method if exec_sql doesn't work
        print("Trying alternative method...")
        try:
            # Split the SQL into individual statements and execute them
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            for i, stmt in enumerate(statements):
                if stmt:
                    print(f"Executing statement {i+1}/{len(statements)}...")
                    # Note: This might not work with all SQL statements
                    # You may need to run the schema manually in Supabase SQL editor
                    pass
            
            print("⚠️  Please run the schema_cached_insights.sql file manually in your Supabase SQL editor")
            print("   The schema file contains the necessary SQL statements")
            return False
            
        except Exception as e2:
            print(f"❌ Alternative method also failed: {e2}")
            print("🔧 Please run the schema_cached_insights.sql file manually in your Supabase SQL editor")
            return False

if __name__ == "__main__":
    print("🚀 Applying cached insights schema...")
    success = apply_cached_insights_schema()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("🔄 AI insights will now be cached automatically")
        print("📊 Insights will only regenerate when new feedback data is available")
    else:
        print("\n⚠️  Manual step required:")
        print("1. Go to your Supabase project dashboard")
        print("2. Navigate to SQL Editor")
        print("3. Copy and paste the contents of schema_cached_insights.sql")
        print("4. Execute the SQL statements") 