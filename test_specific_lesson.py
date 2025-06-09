#!/usr/bin/env python3

import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def test_specific_lesson():
    print("=== Testing Specific Lesson with 11 Turns ===\n")
    
    # Get the conversation with lesson progress
    conversation_id = "b22a60ab-b3fb-41f2-b02e-a1f7b9876352"
    
    print(f"1. Checking conversation {conversation_id}:")
    conversation = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
    if conversation.data:
        conv = conversation.data[0]
        print(f"   Context: {conv['context']}")
        print(f"   Lesson ID: {conv['lesson_id']}")
        print(f"   User ID: {conv['user_id']}")
        print(f"   Curriculum ID: {conv['curriculum_id']}")
        print()
    
    print("2. Checking progress record:")
    progress = supabase.table('lesson_progress').select('*').eq('user_id', conv['user_id']).eq('lesson_id', conv['lesson_id']).execute()
    if progress.data:
        prog = progress.data[0]
        print(f"   Progress ID: {prog['id']}")
        print(f"   Status: {prog['status']}")
        print(f"   Turns: {prog['turns_completed']}/{prog['required_turns']}")
        print(f"   Can complete: {prog['turns_completed'] >= prog['required_turns']}")
        print()
        
        # Test the completion logic
        if prog['turns_completed'] >= prog['required_turns']:
            print("3. This lesson SHOULD be completable!")
            print(f"   Lesson has {prog['turns_completed']} turns, requires {prog['required_turns']}")
            print(f"   Progress ID for completion: {prog['id']}")
            
            # Let's manually test the completion API endpoint format
            print("\n4. API endpoint info:")
            print(f"   GET /api/lessons/{conv['lesson_id']}/progress?curriculum_id={conv['curriculum_id']}&token=<token>")
            print(f"   POST /api/lesson_progress/complete with progress_id: {prog['id']}")
        else:
            print("3. Lesson not yet completable")
    else:
        print("   No progress record found!")

if __name__ == "__main__":
    test_specific_lesson() 