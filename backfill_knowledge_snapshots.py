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

def backfill_verb_snapshots():
    """Convert existing verb_knowledge_snapshots to comprehensive knowledge_snapshots"""
    print("🔄 Backfilling from verb_knowledge_snapshots...")
    
    try:
        # Get all verb knowledge snapshots
        verb_snapshots = supabase.table('verb_knowledge_snapshots').select('*').order('snapshot_at').execute()
        
        print(f"Found {len(verb_snapshots.data)} verb snapshots to convert")
        
        for snapshot in verb_snapshots.data:
            # Check if already converted
            existing = supabase.table('knowledge_snapshots').select('id').eq(
                'user_id', snapshot['user_id']
            ).eq('snapshot_at', snapshot['snapshot_at']).execute()
            
            if existing.data:
                print(f"  ⏭️  Skipping {snapshot['snapshot_at']} - already exists")
                continue
            
            # Create comprehensive knowledge from verb data
            verb_knowledge = snapshot['verb_knowledge']
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
            
            # Insert comprehensive snapshot
            new_snapshot = {
                'user_id': snapshot['user_id'],
                'language': snapshot['language'],
                'curriculum_id': snapshot['curriculum_id'],
                'conversation_id': snapshot['conversation_id'],
                'lesson_progress_id': snapshot['lesson_progress_id'],
                'snapshot_reason': snapshot['snapshot_reason'],
                'snapshot_at': snapshot['snapshot_at'],
                'detailed_knowledge': detailed_knowledge,
                **counts
            }
            
            supabase.table('knowledge_snapshots').insert(new_snapshot).execute()
            print(f"  ✅ Converted snapshot from {snapshot['snapshot_at']}")
            
    except Exception as e:
        print(f"❌ Error backfilling verb snapshots: {e}")

def backfill_user_knowledge():
    """Create daily snapshots from user_knowledge table for historical data"""
    print("🔄 Backfilling from user_knowledge...")
    
    try:
        # Get all user knowledge records
        user_knowledge = supabase.table('user_knowledge').select('*').execute()
        
        print(f"Found {len(user_knowledge.data)} user knowledge records")
        
        for knowledge in user_knowledge.data:
            # Get the most recent verb snapshot for this user as reference point
            recent_verb_snapshot = supabase.table('verb_knowledge_snapshots').select(
                'snapshot_at, curriculum_id'
            ).eq('user_id', knowledge['user_id']).eq(
                'language', knowledge['language']
            ).order('snapshot_at', desc=True).limit(1).execute()
            
            if not recent_verb_snapshot.data:
                print(f"  ⏭️  No verb snapshots found for user {knowledge['user_id']}")
                continue
                
            # Use the updated_at time or created_at as snapshot time
            snapshot_time = knowledge.get('updated_at') or knowledge.get('created_at')
            if not snapshot_time:
                print(f"  ⏭️  No timestamp for user knowledge {knowledge['id']}")
                continue
            
            # Check if snapshot already exists
            existing = supabase.table('knowledge_snapshots').select('id').eq(
                'user_id', knowledge['user_id']
            ).eq('language', knowledge['language']).eq(
                'snapshot_reason', 'knowledge_analysis'
            ).execute()
            
            if existing.data:
                print(f"  ⏭️  Knowledge snapshot already exists for user")
                continue
            
            # Count elements from knowledge JSON
            counts = count_knowledge_elements(knowledge['knowledge_json'])
            
            # Create comprehensive snapshot
            new_snapshot = {
                'user_id': knowledge['user_id'],
                'language': knowledge['language'],
                'curriculum_id': recent_verb_snapshot.data[0]['curriculum_id'],
                'conversation_id': None,
                'lesson_progress_id': None,
                'snapshot_reason': 'knowledge_analysis',
                'snapshot_at': snapshot_time,
                'detailed_knowledge': knowledge['knowledge_json'],
                **counts
            }
            
            supabase.table('knowledge_snapshots').insert(new_snapshot).execute()
            print(f"  ✅ Created knowledge snapshot for user {knowledge['user_id']}")
            
    except Exception as e:
        print(f"❌ Error backfilling user knowledge: {e}")

def create_daily_conversation_snapshots():
    """Create daily knowledge snapshots from conversation history"""
    print("🔄 Creating daily snapshots from conversation history...")
    
    try:
        # Get conversation history grouped by date
        conversations = supabase.table('conversations').select(
            'id, user_id, language, curriculum_id, created_at'
        ).order('created_at').execute()
        
        # Group by user and date
        daily_groups = {}
        for conv in conversations.data:
            user_id = conv['user_id']
            date = conv['created_at'][:10]  # Get YYYY-MM-DD
            
            key = f"{user_id}_{date}_{conv['language']}"
            if key not in daily_groups:
                daily_groups[key] = {
                    'user_id': user_id,
                    'language': conv['language'],
                    'curriculum_id': conv['curriculum_id'],
                    'date': date,
                    'conversations': []
                }
            daily_groups[key]['conversations'].append(conv)
        
        print(f"Found {len(daily_groups)} daily conversation groups")
        
        for group_key, group in daily_groups.items():
            # Check if daily snapshot already exists
            existing = supabase.table('knowledge_snapshots').select('id').eq(
                'user_id', group['user_id']
            ).eq('language', group['language']).gte(
                'snapshot_at', f"{group['date']} 00:00:00"
            ).lt('snapshot_at', f"{group['date']} 23:59:59").execute()
            
            if existing.data:
                continue
            
            # Get the most recent verb knowledge for this user/date
            recent_verb = supabase.table('verb_knowledge_snapshots').select('*').eq(
                'user_id', group['user_id']
            ).eq('language', group['language']).lte(
                'snapshot_at', f"{group['date']} 23:59:59"
            ).order('snapshot_at', desc=True).limit(1).execute()
            
            if not recent_verb.data:
                print(f"  ⏭️  No verb data for {group_key}")
                continue
            
            # Use verb knowledge as base
            verb_knowledge = recent_verb.data[0]['verb_knowledge']
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
            
            counts = count_knowledge_elements(detailed_knowledge)
            
            # Create snapshot at end of day
            snapshot_time = f"{group['date']} 23:59:59+00:00"
            
            new_snapshot = {
                'user_id': group['user_id'],
                'language': group['language'],
                'curriculum_id': group['curriculum_id'],
                'conversation_id': group['conversations'][-1]['id'],
                'lesson_progress_id': None,
                'snapshot_reason': 'daily_summary',
                'snapshot_at': snapshot_time,
                'detailed_knowledge': detailed_knowledge,
                **counts
            }
            
            supabase.table('knowledge_snapshots').insert(new_snapshot).execute()
            print(f"  ✅ Created daily snapshot for {group['date']}")
            
    except Exception as e:
        print(f"❌ Error creating daily snapshots: {e}")

def main():
    print("🚀 Starting Knowledge Snapshots Backfill")
    print("=" * 50)
    
    # Step 1: Convert existing verb snapshots
    backfill_verb_snapshots()
    
    # Step 2: Create snapshots from user knowledge analysis
    backfill_user_knowledge()
    
    # Step 3: Create daily snapshots from conversation history
    create_daily_conversation_snapshots()
    
    # Show summary
    total_snapshots = supabase.table('knowledge_snapshots').select('id').execute()
    print("\n" + "=" * 50)
    print(f"✅ Backfill complete! Total snapshots: {len(total_snapshots.data)}")
    
    # Show sample data
    recent_snapshots = supabase.table('knowledge_snapshots').select(
        'user_id, language, snapshot_at, verbs_count, nouns_count, adjectives_count, snapshot_reason'
    ).order('snapshot_at', desc=True).limit(5).execute()
    
    print("\n📊 Recent snapshots:")
    for snapshot in recent_snapshots.data:
        print(f"  {snapshot['snapshot_at'][:10]} | "
              f"V:{snapshot['verbs_count']} N:{snapshot['nouns_count']} A:{snapshot['adjectives_count']} | "
              f"{snapshot['snapshot_reason']}")

if __name__ == "__main__":
    main() 