#!/usr/bin/env python3

import requests
import os
from dotenv import load_dotenv

load_dotenv()

print("Lesson Progress Schema Migration")
print("=" * 40)

# Read the SQL file
try:
    with open('schema_lesson_progress.sql', 'r') as f:
        sql_content = f.read()
    print("✓ Successfully read schema_lesson_progress.sql")
except FileNotFoundError:
    print("✗ schema_lesson_progress.sql not found")
    exit(1)

print("\nSQL Migration Content:")
print("-" * 40)
print(sql_content[:500] + "..." if len(sql_content) > 500 else sql_content)
print("-" * 40)

print("\nTo apply this migration:")
print("1. Copy the SQL content above")
print("2. Go to your Supabase Dashboard → SQL Editor")
print("3. Paste and run the SQL")
print("4. Or provide a valid auth token to apply via API")

# Option to apply via API if token is provided
token = input("\nEnter auth token (or press Enter to skip): ").strip()

if token:
    try:
        # We'll need the apply_migration endpoint - let's check if it exists
        print("Applying migration via API...")
        
        # For now, we'll just show the SQL since the apply_migration endpoint may not exist
        print("API migration not available. Please run SQL manually in Supabase dashboard.")
        
    except Exception as e:
        print(f"✗ Error applying migration: {e}")
        print("Please run the SQL manually in Supabase dashboard.")
else:
    print("No token provided. Please run the SQL manually in Supabase dashboard.")

print("\nAfter applying the migration, run: python test_lesson_progress.py") 