#!/usr/bin/env python3

import os
from supabase import create_client
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def debug_knowledge_system():
    print("=== Debugging Knowledge Update System ===\n")
    
    # 1. Check user_knowledge table structure
    print("1. Checking user_knowledge table:")
    try:
        knowledge_records = supabase.table('user_knowledge').select('*').limit(3).execute()
        if knowledge_records.data:
            print(f"   Found {len(knowledge_records.data)} knowledge records")
            sample = knowledge_records.data[0]
            print(f"   Sample record keys: {list(sample.keys())}")
            
            # Check if analyzed_conversations field exists
            if 'analyzed_conversations' in sample:
                analyzed = sample.get('analyzed_conversations', [])
                print(f"   Analyzed conversations: {len(analyzed)} conversations")
            else:
                print("   ❌ 'analyzed_conversations' field missing!")
        else:
            print("   No knowledge records found")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. Check recent lesson progress completions
    print("\n2. Checking recent lesson completions:")
    try:
        recent_completions = supabase.table('lesson_progress').select('*').eq('status', 'completed').order('completed_at', desc=True).limit(5).execute()
        if recent_completions.data:
            print(f"   Found {len(recent_completions.data)} recent completions")
            for completion in recent_completions.data:
                print(f"   - User: {completion['user_id']}, Completed: {completion.get('completed_at', 'N/A')}")
        else:
            print("   No completed lessons found")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Check conversations for a user
    print("\n3. Checking conversations for analysis:")
    try:
        # Get a user who has completed lessons
        recent_completions = supabase.table('lesson_progress').select('user_id, curriculum_id').eq('status', 'completed').limit(1).execute()
        if recent_completions.data:
            user_id = recent_completions.data[0]['user_id']
            curriculum_id = recent_completions.data[0]['curriculum_id']
            
            # Get curriculum language
            curriculum = supabase.table('curriculums').select('language').eq('id', curriculum_id).execute()
            language = curriculum.data[0]['language'] if curriculum.data else 'en'
            
            print(f"   Checking user {user_id} for language {language}")
            
            # Get conversations
            conversations = supabase.table('conversations').select('id, created_at').eq('user_id', user_id).eq('language', language).execute()
            print(f"   Total conversations: {len(conversations.data)}")
            
            # Get knowledge record
            knowledge = supabase.table('user_knowledge').select('*').eq('user_id', user_id).eq('language', language).execute()
            if knowledge.data:
                analyzed = knowledge.data[0].get('analyzed_conversations', [])
                print(f"   Analyzed conversations: {len(analyzed)}")
                unanalyzed = len(conversations.data) - len(analyzed)
                print(f"   Unanalyzed conversations: {unanalyzed}")
            else:
                print("   No knowledge record found for this user")
                
        else:
            print("   No completed lessons to check")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 4. Test manual knowledge update
    print("\n4. Testing manual knowledge update:")
    try:
        # Try to call the knowledge update function directly
        print("   This would require importing server functions...")
        print("   Recommendation: Use the API endpoint to test")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n=== Debug Complete ===")
    print("\n🔧 Possible issues:")
    print("   1. Database schema missing 'analyzed_conversations' field")
    print("   2. Knowledge update not being triggered on lesson completion")
    print("   3. Frontend not refreshing the knowledge display")
    print("   4. OpenAI API errors during analysis")
    
    print("\n💡 Next steps:")
    print("   1. Check server logs for any errors")
    print("   2. Test the manual knowledge update API endpoint")
    print("   3. Verify the frontend refreshes after lesson completion")

if __name__ == "__main__":
    debug_knowledge_system() 