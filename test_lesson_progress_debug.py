#!/usr/bin/env python3

import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def debug_lesson_progress():
    print("=== Lesson Progress Debug ===\n")
    
    # 1. Check lesson_progress table structure
    print("1. Checking lesson_progress table:")
    try:
        progress_records = supabase.table('lesson_progress').select('*').limit(5).execute()
        print(f"   Found {len(progress_records.data)} progress records:")
        for record in progress_records.data:
            print(f"   - ID: {record['id']}, User: {record['user_id']}")
            print(f"     Lesson ID: {record.get('lesson_id')}, Custom Lesson ID: {record.get('custom_lesson_id')}")
            print(f"     Status: {record['status']}, Turns: {record['turns_completed']}/{record['required_turns']}")
            print(f"     Created: {record['created_at']}")
            print()
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. Check lesson_templates table
    print("2. Checking lesson_templates table (first 3):")
    try:
        lesson_templates = supabase.table('lesson_templates').select('*').limit(3).execute()
        for lesson in lesson_templates.data:
            print(f"   - ID: {lesson['id']} (type: {type(lesson['id'])})")
            print(f"     Title: {lesson.get('title')}")
            print(f"     Difficulty: {lesson.get('difficulty')}")
            print()
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Check conversations table for lesson conversations
    print("3. Checking conversations table for lesson conversations:")
    try:
        conversations = supabase.table('conversations').select('*').limit(5).execute()
        lesson_conversations = [c for c in conversations.data if 
                              c.get('lesson_id') or 
                              c.get('custom_lesson_id') or 
                              (c.get('context') and ('Lesson:' in c['context'] or 'Custom Lesson:' in c['context']))]
        
        print(f"   Found {len(lesson_conversations)} lesson conversations:")
        for conv in lesson_conversations:
            print(f"   - ID: {conv['id']}")
            print(f"     Context: {conv.get('context')}")
            print(f"     Lesson ID: {conv.get('lesson_id')}, Custom Lesson ID: {conv.get('custom_lesson_id')}")
            print(f"     Created: {conv['created_at']}")
            print()
    except Exception as e:
        print(f"   Error: {e}")
    
    # 4. Check if lesson_id column type matches
    print("4. Checking lesson_progress lesson_id data types:")
    try:
        # Get a progress record with lesson_id
        progress_with_lesson = supabase.table('lesson_progress').select('*').not_.is_('lesson_id', 'null').limit(1).execute()
        if progress_with_lesson.data:
            lesson_id_in_progress = progress_with_lesson.data[0]['lesson_id']
            print(f"   lesson_progress.lesson_id: {lesson_id_in_progress} (type: {type(lesson_id_in_progress)})")
            
            # Get a lesson template ID
            template = supabase.table('lesson_templates').select('id').limit(1).execute()
            if template.data:
                template_id = template.data[0]['id']
                print(f"   lesson_templates.id: {template_id} (type: {type(template_id)})")
                
                # Check if they match
                if str(lesson_id_in_progress) == str(template_id):
                    print("   ✅ Types appear compatible")
                else:
                    print("   ❌ Type mismatch detected!")
        else:
            print("   No lesson progress records with lesson_id found")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    debug_lesson_progress() 