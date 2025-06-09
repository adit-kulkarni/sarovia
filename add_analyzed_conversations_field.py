#!/usr/bin/env python3

import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def add_analyzed_conversations_field():
    """Add analyzed_conversations field to user_knowledge table"""
    print("=== Adding analyzed_conversations field ===\n")
    
    try:
        # Check current table structure
        print("1. Checking current user_knowledge table structure...")
        existing_records = supabase.table('user_knowledge').select('*').limit(1).execute()
        
        if existing_records.data:
            sample_record = existing_records.data[0]
            print(f"   Current fields: {list(sample_record.keys())}")
            
            if 'analyzed_conversations' in sample_record:
                print("   ✅ analyzed_conversations field already exists!")
                return True
            else:
                print("   ❌ analyzed_conversations field missing")
        
        # Note: We can't directly add columns via Supabase client
        # We need to update existing records to include the new field
        print("\n2. Updating existing records with analyzed_conversations field...")
        
        all_records = supabase.table('user_knowledge').select('*').execute()
        
        for record in all_records.data:
            # Add empty analyzed_conversations array to each record
            supabase.table('user_knowledge').update({
                'analyzed_conversations': []
            }).eq('id', record['id']).execute()
        
        print(f"   ✅ Updated {len(all_records.data)} records with analyzed_conversations field")
        
        # Verify the update
        print("\n3. Verifying the update...")
        updated_record = supabase.table('user_knowledge').select('*').limit(1).execute()
        if updated_record.data:
            sample = updated_record.data[0]
            if 'analyzed_conversations' in sample:
                print("   ✅ Field successfully added!")
                print(f"   Sample record: analyzed_conversations = {sample.get('analyzed_conversations', [])}")
                return True
            else:
                print("   ❌ Field still missing after update")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error adding field: {e}")
        return False

def test_knowledge_update():
    """Test the knowledge update system"""
    print("\n=== Testing Knowledge Update System ===\n")
    
    try:
        # Get a user with conversations
        recent_completions = supabase.table('lesson_progress').select('user_id, curriculum_id').limit(1).execute()
        if not recent_completions.data:
            print("❌ No lesson progress found to test with")
            return
        
        user_id = recent_completions.data[0]['user_id']
        curriculum_id = recent_completions.data[0]['curriculum_id']
        
        # Get curriculum language
        curriculum = supabase.table('curriculums').select('language').eq('id', curriculum_id).execute()
        language = curriculum.data[0]['language'] if curriculum.data else 'es'
        
        print(f"Testing with user {user_id}, language {language}")
        
        # Test the manual update endpoint
        print("You can now test the knowledge update by:")
        print(f"1. Going to: http://localhost:3000")
        print(f"2. Completing a lesson")
        print(f"3. Or manually calling: POST /api/user_knowledge/update?language={language}")
        
        # Show current state
        conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('language', language).execute()
        knowledge = supabase.table('user_knowledge').select('*').eq('user_id', user_id).eq('language', language).execute()
        
        print(f"\nCurrent state:")
        print(f"- Total conversations: {len(conversations.data)}")
        if knowledge.data:
            analyzed = knowledge.data[0].get('analyzed_conversations', [])
            print(f"- Analyzed conversations: {len(analyzed)}")
            print(f"- Unanalyzed conversations: {len(conversations.data) - len(analyzed)}")
        else:
            print("- No knowledge record exists yet")
        
    except Exception as e:
        print(f"❌ Error testing: {e}")

if __name__ == "__main__":
    success = add_analyzed_conversations_field()
    if success:
        test_knowledge_update()
    else:
        print("\n❌ Migration failed. Please check the errors above.") 