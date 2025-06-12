#!/usr/bin/env python3

import os
import json
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def count_knowledge_elements(knowledge_json):
    """Count different types of knowledge elements from JSON data"""
    if not knowledge_json:
        return {
            'verbs_count': 0,
            'verbs_with_tenses_count': 0,
            'nouns_count': 0,
            'adjectives_count': 0,
            'pronouns_count': 0,
            'adverbs_count': 0,
            'prepositions_count': 0,
            'conjunctions_count': 0,
            'articles_count': 0,
            'interjections_count': 0
        }
    
    counts = {
        'verbs_count': 0,
        'verbs_with_tenses_count': 0,
        'nouns_count': 0,
        'adjectives_count': 0,
        'pronouns_count': 0,
        'adverbs_count': 0,
        'prepositions_count': 0,
        'conjunctions_count': 0,
        'articles_count': 0,
        'interjections_count': 0
    }
    
    # Count verbs (can be object or array)
    if 'verbs' in knowledge_json:
        verbs = knowledge_json['verbs']
        if isinstance(verbs, dict):
            counts['verbs_count'] = len(verbs)
            # Count verbs with multiple tenses/conjugations
            counts['verbs_with_tenses_count'] = sum(
                1 for verb_data in verbs.values() 
                if isinstance(verb_data, dict) and len(verb_data) > 1
            )
        elif isinstance(verbs, list):
            counts['verbs_count'] = len(verbs)
    
    # Count other parts of speech (arrays)
    for part in ['nouns', 'adjectives', 'pronouns', 'adverbs', 
                 'prepositions', 'conjunctions', 'articles', 'interjections']:
        if part in knowledge_json and isinstance(knowledge_json[part], list):
            counts[f'{part}_count'] = len(knowledge_json[part])
    
    return counts

def update_knowledge_snapshot_for_conversation(conversation_id):
    """Create/update knowledge snapshot after a conversation"""
    try:
        # Get conversation details
        conversation = supabase.table('conversations').select('*').eq('id', conversation_id).single().execute()
        if not conversation.data:
            print(f"❌ Conversation {conversation_id} not found")
            return False
        
        conv_data = conversation.data
        user_id = conv_data['user_id']
        language = conv_data['language']
        curriculum_id = conv_data['curriculum_id']
        
        print(f"🔄 Updating knowledge snapshot for conversation {conversation_id}")
        
        # Get the most recent verb knowledge snapshot for this user
        recent_verb_snapshot = supabase.table('verb_knowledge_snapshots').select('*').eq(
            'user_id', user_id
        ).eq('language', language).order('snapshot_at', desc=True).limit(1).execute()
        
        if not recent_verb_snapshot.data:
            print(f"❌ No verb knowledge found for user {user_id}")
            return False
        
        verb_knowledge = recent_verb_snapshot.data[0]['verb_knowledge']
        
        # Get the latest comprehensive user knowledge
        user_knowledge = supabase.table('user_knowledge').select('*').eq(
            'user_id', user_id
        ).eq('language', language).single().execute()
        
        # Combine verb knowledge with user knowledge
        if user_knowledge.data and user_knowledge.data.get('knowledge_json'):
            detailed_knowledge = user_knowledge.data['knowledge_json'].copy()
            # Ensure verbs section is up to date
            detailed_knowledge['verbs'] = verb_knowledge
        else:
            detailed_knowledge = {
                'verbs': verb_knowledge,
                'nouns': [],
                'adjectives': [],
                'pronouns': [],
                'adverbs': [],
                'prepositions': [],
                'conjunctions': [],
                'articles': [],
                'interjections': []
            }
        
        # Count elements
        counts = count_knowledge_elements(detailed_knowledge)
        
        # Create snapshot timestamp (current time)
        snapshot_time = datetime.utcnow().isoformat() + 'Z'
        
        # Check if snapshot already exists for this conversation
        existing = supabase.table('knowledge_snapshots').select('id').eq(
            'conversation_id', conversation_id
        ).execute()
        
        if existing.data:
            # Update existing snapshot
            snapshot_id = existing.data[0]['id']
            update_data = {
                'detailed_knowledge': detailed_knowledge,
                'snapshot_at': snapshot_time,
                **counts
            }
            supabase.table('knowledge_snapshots').update(update_data).eq('id', snapshot_id).execute()
            print(f"  ✅ Updated existing snapshot {snapshot_id}")
        else:
            # Create new snapshot
            new_snapshot = {
                'user_id': user_id,
                'language': language,
                'curriculum_id': curriculum_id,
                'conversation_id': conversation_id,
                'lesson_progress_id': None,
                'snapshot_reason': 'conversation_end',
                'snapshot_at': snapshot_time,
                'detailed_knowledge': detailed_knowledge,
                **counts
            }
            
            result = supabase.table('knowledge_snapshots').insert(new_snapshot).execute()
            print(f"  ✅ Created new snapshot {result.data[0]['id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating knowledge snapshot: {e}")
        return False

def update_knowledge_snapshot_for_lesson_completion(lesson_progress_id):
    """Create/update knowledge snapshot after lesson completion"""
    try:
        # Get lesson progress details
        lesson_progress = supabase.table('lesson_progress').select('*').eq('id', lesson_progress_id).single().execute()
        if not lesson_progress.data:
            print(f"❌ Lesson progress {lesson_progress_id} not found")
            return False
        
        progress_data = lesson_progress.data
        user_id = progress_data['user_id']
        curriculum_id = progress_data['curriculum_id']
        conversation_id = progress_data.get('conversation_id')
        
        print(f"🔄 Updating knowledge snapshot for lesson completion {lesson_progress_id}")
        
        # Get user's curriculum language
        curriculum = supabase.table('curriculums').select('language').eq('id', curriculum_id).single().execute()
        if not curriculum.data:
            print(f"❌ Curriculum {curriculum_id} not found")
            return False
        
        language = curriculum.data['language']
        
        # Get the most recent verb knowledge snapshot for this user
        recent_verb_snapshot = supabase.table('verb_knowledge_snapshots').select('*').eq(
            'lesson_progress_id', lesson_progress_id
        ).order('snapshot_at', desc=True).limit(1).execute()
        
        if not recent_verb_snapshot.data:
            # Fallback to user's most recent verb knowledge
            recent_verb_snapshot = supabase.table('verb_knowledge_snapshots').select('*').eq(
                'user_id', user_id
            ).eq('language', language).order('snapshot_at', desc=True).limit(1).execute()
        
        if not recent_verb_snapshot.data:
            print(f"❌ No verb knowledge found for user {user_id}")
            return False
        
        verb_knowledge = recent_verb_snapshot.data[0]['verb_knowledge']
        
        # Get the latest comprehensive user knowledge
        user_knowledge = supabase.table('user_knowledge').select('*').eq(
            'user_id', user_id
        ).eq('language', language).single().execute()
        
        # Combine verb knowledge with user knowledge
        if user_knowledge.data and user_knowledge.data.get('knowledge_json'):
            detailed_knowledge = user_knowledge.data['knowledge_json'].copy()
            # Ensure verbs section is up to date
            detailed_knowledge['verbs'] = verb_knowledge
        else:
            detailed_knowledge = {
                'verbs': verb_knowledge,
                'nouns': [],
                'adjectives': [],
                'pronouns': [],
                'adverbs': [],
                'prepositions': [],
                'conjunctions': [],
                'articles': [],
                'interjections': []
            }
        
        # Count elements
        counts = count_knowledge_elements(detailed_knowledge)
        
        # Use lesson completion time
        snapshot_time = progress_data.get('completed_at') or datetime.utcnow().isoformat() + 'Z'
        
        # Check if snapshot already exists for this lesson
        existing = supabase.table('knowledge_snapshots').select('id').eq(
            'lesson_progress_id', lesson_progress_id
        ).execute()
        
        if existing.data:
            # Update existing snapshot
            snapshot_id = existing.data[0]['id']
            update_data = {
                'detailed_knowledge': detailed_knowledge,
                'snapshot_at': snapshot_time,
                **counts
            }
            supabase.table('knowledge_snapshots').update(update_data).eq('id', snapshot_id).execute()
            print(f"  ✅ Updated existing lesson snapshot {snapshot_id}")
        else:
            # Create new snapshot
            new_snapshot = {
                'user_id': user_id,
                'language': language,
                'curriculum_id': curriculum_id,
                'conversation_id': conversation_id,
                'lesson_progress_id': lesson_progress_id,
                'snapshot_reason': 'lesson_completion',
                'snapshot_at': snapshot_time,
                'detailed_knowledge': detailed_knowledge,
                **counts
            }
            
            result = supabase.table('knowledge_snapshots').insert(new_snapshot).execute()
            print(f"  ✅ Created new lesson snapshot {result.data[0]['id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating lesson knowledge snapshot: {e}")
        return False

def get_knowledge_snapshots(user_id, language, limit=50):
    """Get knowledge snapshots for timeline visualization"""
    try:
        snapshots = supabase.table('knowledge_snapshots').select(
            'snapshot_at, verbs_count, nouns_count, adjectives_count, '
            'verbs_with_tenses_count, snapshot_reason'
        ).eq('user_id', user_id).eq('language', language).order(
            'snapshot_at'
        ).limit(limit).execute()
        
        return snapshots.data
    except Exception as e:
        print(f"❌ Error fetching knowledge snapshots: {e}")
        return []

def main():
    """Test the incremental update functionality"""
    print("🧪 Testing Knowledge Snapshot Updates")
    print("=" * 40)
    
    # Get a recent conversation to test with
    recent_conv = supabase.table('conversations').select('id').order('created_at', desc=True).limit(1).execute()
    
    if recent_conv.data:
        conv_id = recent_conv.data[0]['id']
        print(f"Testing with conversation {conv_id}")
        success = update_knowledge_snapshot_for_conversation(conv_id)
        if success:
            print("✅ Conversation snapshot update successful")
        else:
            print("❌ Conversation snapshot update failed")
    
    # Test getting snapshots for visualization
    print("\n📊 Testing snapshot retrieval...")
    snapshots = get_knowledge_snapshots('119c618c-0e1c-4984-94ad-0e15f70b7c31', 'es', 10)
    print(f"Found {len(snapshots)} snapshots for visualization")
    
    for snapshot in snapshots[:5]:
        print(f"  {snapshot['snapshot_at'][:10]} | "
              f"V:{snapshot['verbs_count']} N:{snapshot['nouns_count']} A:{snapshot['adjectives_count']} | "
              f"{snapshot['snapshot_reason']}")

if __name__ == "__main__":
    main() 