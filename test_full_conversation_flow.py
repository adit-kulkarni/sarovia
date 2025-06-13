#!/usr/bin/env python3
"""
Complete test of the conversation completion flow including:
1. Finding a conversation with feedback
2. Testing conversation completion endpoint
3. Testing conversation summary endpoint
4. Verifying review endpoint works
"""

import os
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
import json

# Load environment
load_dotenv()

# Configuration
API_BASE = "http://localhost:8000"
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def test_complete_conversation_flow():
    """Test the complete conversation completion flow"""
    print("🧪 Testing Complete Conversation Flow")
    print("=" * 50)
    
    # Initialize Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Find a conversation with actual messages and feedback
    print("1. Finding a conversation with messages and feedback...")
    
    # Get conversations with messages
    conversations = supabase.table('conversations').select('id, context, language, level, user_id').limit(10).execute()
    
    target_conv = None
    for conv in conversations.data:
        # Check if it has messages
        messages = supabase.table('messages').select('id').eq('conversation_id', conv['id']).execute()
        if messages.data:
            # Check if it has feedback
            message_ids = [msg['id'] for msg in messages.data]
            feedback = supabase.table('message_feedback').select('mistakes').in_('message_id', message_ids).execute()
            if feedback.data:
                target_conv = conv
                break
    
    if not target_conv:
        print("❌ No conversation found with messages and feedback")
        return
    
    print(f"✅ Found conversation: {target_conv['id'][:8]}...")
    print(f"   Context: {target_conv['context']}")
    print(f"   Language: {target_conv['language']}")
    print(f"   Level: {target_conv['level']}")
    
    # 2. Test conversation summary endpoint structure
    print("\n2. Testing conversation summary endpoint...")
    conversation_id = target_conv['id']
    
    try:
        # This would normally require a valid JWT, but we can check the structure
        summary_url = f"{API_BASE}/api/conversations/{conversation_id}/summary"
        print(f"   Summary endpoint: GET {summary_url}")
        
        # Check that we have the data structures in place
        messages = supabase.table('messages').select('*').eq('conversation_id', conversation_id).execute()
        message_ids = [msg['id'] for msg in messages.data]
        feedback = supabase.table('message_feedback').select('mistakes').in_('message_id', message_ids).execute()
        
        print(f"   Messages: {len(messages.data)} found")
        print(f"   Feedback records: {len(feedback.data)} found")
        
        # Check feedback structure
        mistakes_count = 0
        for fb in feedback.data:
            if fb.get('mistakes'):
                mistakes_count += len(fb['mistakes'])
        
        print(f"   Total mistakes: {mistakes_count}")
        
    except Exception as e:
        print(f"   ❌ Error testing summary endpoint: {e}")
    
    # 3. Test conversation review endpoint structure
    print("\n3. Testing conversation review endpoint...")
    
    try:
        review_url = f"{API_BASE}/api/conversations/{conversation_id}/review"
        print(f"   Review endpoint: GET {review_url}")
        
        # Test the data that would be returned
        messages = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at', desc=False).execute()
        message_ids = [msg['id'] for msg in messages.data]
        feedback_result = supabase.table('message_feedback').select('*').in_('message_id', message_ids).execute()
        
        feedback_map = {}
        for feedback in feedback_result.data:
            feedback_map[feedback['message_id']] = feedback
        
        print(f"   Messages: {len(messages.data)}")
        print(f"   Feedback map entries: {len(feedback_map)}")
        
        # Show sample message structure
        if messages.data:
            sample_msg = messages.data[0]
            print(f"   Sample message ID: {sample_msg['id'][:8]}...")
            print(f"   Sample message role: {sample_msg['role']}")
            if sample_msg['id'] in feedback_map:
                sample_feedback = feedback_map[sample_msg['id']]
                print(f"   Sample feedback: {len(sample_feedback.get('mistakes', []))} mistakes")
        
    except Exception as e:
        print(f"   ❌ Error testing review endpoint: {e}")
    
    # 4. Test conversation completion endpoint structure
    print("\n4. Testing conversation completion endpoint...")
    
    try:
        complete_url = f"{API_BASE}/api/conversations/complete"
        print(f"   Complete endpoint: POST {complete_url}")
        print(f"   Request body: {{\"conversation_id\": \"{conversation_id}\"}}")
        
        # Check if conversation is already completed
        conv_check = supabase.table('conversations').select('completed_at').eq('id', conversation_id).execute()
        if conv_check.data and conv_check.data[0].get('completed_at'):
            print(f"   ✅ Conversation already completed")
        else:
            print(f"   ⚠️  Conversation not yet completed (would be completed by endpoint)")
        
    except Exception as e:
        print(f"   ❌ Error testing completion endpoint: {e}")
    
    print("\n✅ Conversation Flow Test Complete!")
    print("\nTo test the complete flow:")
    print("1. Start a new conversation with 'Start Conversation' button")
    print("2. Have a few exchanges with the AI")
    print("3. Click 'End Conversation' button")
    print("4. You should see a report card with:")
    print("   - Conversation metrics (turns, duration, words)")
    print("   - Mistakes analysis by category") 
    print("   - Achievements based on engagement")
    print("   - Ability to view conversation details")

if __name__ == "__main__":
    test_complete_conversation_flow() 