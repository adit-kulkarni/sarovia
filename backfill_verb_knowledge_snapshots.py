#!/usr/bin/env python3
"""
Backfill script to populate verb_knowledge_snapshots table with historical data.

This script analyzes completed lessons and reconstructs verb knowledge states
at the time of each lesson completion, creating snapshots that can be used
for fast report card generation.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
import sys

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client, Client
import aiohttp
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Use service key for admin operations

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI API Key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON from LLM response text"""
    import re
    
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*', '', text)
        text = text.strip('`\n')
    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except:
            pass
    
    try:
        return json.loads(text)
    except:
        return None

async def analyze_conversations_incrementally(user_id: str, language: str, conversation_ids: List[str]) -> Optional[dict]:
    """Analyze specific conversations and merge with existing knowledge"""
    try:
        if not conversation_ids:
            return None
        
        # Get messages from the specified conversations
        new_messages = []
        for conv_id in conversation_ids:
            messages = supabase.table('messages').select('content').eq('conversation_id', conv_id).eq('role', 'user').order('created_at', desc=False).execute()
            new_messages.extend([m['content'] for m in messages.data])
        
        if not new_messages:
            logger.info(f"[Knowledge Analysis] No new messages found in conversations")
            return None
        
        # Build prompt for new message analysis
        transcript = "\n".join(new_messages)
        prompt = f"""Analyze the following new {language} messages from a language learner. Extract vocabulary and grammar patterns they've used.

For each part of speech, provide a list of unique words/patterns the user has demonstrated:
- nouns: specific nouns they've used
- pronouns: pronouns they've used correctly
- adjectives: adjectives they've used
- verbs: for each verb, list the lemma and what tenses/persons they've used
- adverbs: adverbs they've used
- prepositions: prepositions they've used correctly
- conjunctions: conjunctions they've used
- articles: articles they've used correctly
- interjections: interjections they've used

Focus on words they used correctly and contextually appropriately. Don't include obvious mistakes.

Output ONLY a valid JSON object with this structure:
{{
  "nouns": ["word1", "word2"],
  "pronouns": ["word1", "word2"],
  "adjectives": ["word1", "word2"],
  "verbs": {{
    "lemma1": {{
      "present": ["1st_person", "3rd_person"],
      "past": ["1st_person"]
    }}
  }},
  "adverbs": ["word1", "word2"],
  "prepositions": ["word1", "word2"],
  "conjunctions": ["word1", "word2"],
  "articles": ["word1", "word2"],
  "interjections": ["word1", "word2"]
}}

Messages to analyze:
{transcript}"""

        # Call OpenAI API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4-turbo-preview",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1500
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error in knowledge analysis: {error_text}")
                    return None
                
                response_data = await response.json()
                result = response_data["choices"][0]["message"]["content"]
        
        # Parse the result
        new_knowledge = extract_json_from_response(result)
        if not new_knowledge:
            logger.error(f"Failed to parse knowledge analysis result")
            return None
        
        logger.info(f"[Knowledge Analysis] Analyzed {len(new_messages)} new messages")
        return new_knowledge
        
    except Exception as e:
        logger.error(f"Error in incremental knowledge analysis: {e}")
        return None

async def get_user_completed_lessons(user_id: str, language: str) -> List[Dict]:
    """Get all completed lessons for a user in chronological order."""
    try:
        result = supabase.table('lesson_progress').select(
            'id, lesson_id, curriculum_id, completed_at, conversation_id, '
            'lesson_templates(title), conversations(created_at, language)'
        ).eq('user_id', user_id).eq('status', 'completed').execute()
        
        # Filter by language and sort by completion time
        lessons = []
        for lesson in result.data:
            if (lesson.get('conversations') and 
                lesson['conversations'].get('language') == language):
                lessons.append(lesson)
        
        # Sort by completion time
        lessons.sort(key=lambda x: x['completed_at'])
        return lessons
        
    except Exception as e:
        logger.error(f"Error fetching completed lessons for user {user_id}: {e}")
        return []

async def get_conversations_up_to_lesson(user_id: str, language: str, lesson_completion_time: str) -> List[str]:
    """Get all conversation IDs for a user/language up to a specific lesson completion time."""
    try:
        result = supabase.table('conversations').select('id').eq(
            'user_id', user_id
        ).eq('language', language).lte('created_at', lesson_completion_time).execute()
        
        return [conv['id'] for conv in result.data]
        
    except Exception as e:
        logger.error(f"Error fetching conversations for user {user_id}: {e}")
        return []

async def reconstruct_verb_knowledge_at_time(user_id: str, language: str, 
                                           conversation_ids: List[str]) -> Optional[Dict]:
    """Reconstruct verb knowledge state using conversations up to a specific point."""
    if not conversation_ids:
        return {"verbs": {}}
    
    try:
        # Use the existing analysis function to reconstruct knowledge
        logger.info(f"Analyzing {len(conversation_ids)} conversations for knowledge reconstruction")
        knowledge = await analyze_conversations_incrementally(
            user_id, language, conversation_ids
        )
        
        # Extract just the verbs section
        if knowledge and 'verbs' in knowledge:
            return knowledge['verbs']
        else:
            return {}
            
    except Exception as e:
        logger.error(f"Error reconstructing verb knowledge: {e}")
        return {}

async def create_verb_snapshot(user_id: str, language: str, curriculum_id: str,
                             lesson_progress_id: str, conversation_id: Optional[str],
                             verb_knowledge: Dict, snapshot_time: str) -> bool:
    """Create a verb knowledge snapshot entry."""
    try:
        snapshot_data = {
            'user_id': user_id,
            'language': language,
            'curriculum_id': curriculum_id,
            'lesson_progress_id': lesson_progress_id,
            'conversation_id': conversation_id,
            'snapshot_reason': 'lesson_completion',
            'verb_knowledge': verb_knowledge,
            'snapshot_at': snapshot_time
        }
        
        result = supabase.table('verb_knowledge_snapshots').insert(snapshot_data).execute()
        
        if result.data:
            logger.info(f"Created snapshot for lesson_progress_id: {lesson_progress_id}")
            return True
        else:
            logger.error(f"Failed to create snapshot: {result}")
            return False
            
    except Exception as e:
        logger.error(f"Error creating verb snapshot: {e}")
        return False

async def check_existing_snapshot(lesson_progress_id: str) -> bool:
    """Check if a snapshot already exists for this lesson progress."""
    try:
        result = supabase.table('verb_knowledge_snapshots').select('id').eq(
            'lesson_progress_id', lesson_progress_id
        ).execute()
        
        return len(result.data) > 0
        
    except Exception as e:
        logger.error(f"Error checking existing snapshot: {e}")
        return False

async def backfill_user_snapshots(user_id: str, language: str, max_lessons: int = None) -> int:
    """Backfill verb knowledge snapshots for a specific user and language."""
    logger.info(f"Starting backfill for user {user_id}, language {language}")
    
    # Get all completed lessons for this user/language
    completed_lessons = await get_user_completed_lessons(user_id, language)
    
    if not completed_lessons:
        logger.info(f"No completed lessons found for user {user_id}, language {language}")
        return 0
    
    if max_lessons:
        completed_lessons = completed_lessons[:max_lessons]
    
    logger.info(f"Found {len(completed_lessons)} completed lessons to process")
    
    snapshots_created = 0
    
    for i, lesson in enumerate(completed_lessons):
        lesson_progress_id = lesson['id']
        curriculum_id = lesson['curriculum_id']
        conversation_id = lesson.get('conversation_id')
        completion_time = lesson['completed_at']
        lesson_title = lesson.get('lesson_templates', {}).get('title', 'Unknown')
        
        logger.info(f"Processing lesson {i+1}/{len(completed_lessons)}: {lesson_title}")
        
        # Skip if snapshot already exists
        if await check_existing_snapshot(lesson_progress_id):
            logger.info(f"Snapshot already exists for lesson {lesson_progress_id}, skipping")
            continue
        
        # Get all conversations up to this lesson completion
        conversation_ids = await get_conversations_up_to_lesson(
            user_id, language, completion_time
        )
        
        if not conversation_ids:
            logger.warning(f"No conversations found up to lesson completion time {completion_time}")
            # Create empty snapshot
            verb_knowledge = {}
        else:
            # Reconstruct verb knowledge at this point in time
            verb_knowledge = await reconstruct_verb_knowledge_at_time(
                user_id, language, conversation_ids
            )
        
        # Create the snapshot
        success = await create_verb_snapshot(
            user_id, language, curriculum_id, lesson_progress_id,
            conversation_id, verb_knowledge, completion_time
        )
        
        if success:
            snapshots_created += 1
        
        # Add a small delay to avoid overwhelming the API
        await asyncio.sleep(0.5)
    
    logger.info(f"Backfill complete for user {user_id}. Created {snapshots_created} snapshots.")
    return snapshots_created

async def backfill_all_users() -> None:
    """Backfill verb knowledge snapshots for all users with completed lessons."""
    logger.info("Starting full backfill process")
    
    try:
        # Get all unique user/language combinations with completed lessons
        result = supabase.table('lesson_progress').select(
            'user_id, conversations(language)'
        ).eq('status', 'completed').execute()
        
        # Build unique user/language pairs
        user_language_pairs = set()
        for record in result.data:
            if record.get('conversations') and record['conversations'].get('language'):
                user_id = record['user_id']
                language = record['conversations']['language']
                user_language_pairs.add((user_id, language))
        
        logger.info(f"Found {len(user_language_pairs)} unique user/language combinations")
        
        total_snapshots = 0
        
        for i, (user_id, language) in enumerate(user_language_pairs):
            logger.info(f"Processing user/language {i+1}/{len(user_language_pairs)}: {user_id[:8]}.../{language}")
            
            try:
                snapshots_created = await backfill_user_snapshots(user_id, language)
                total_snapshots += snapshots_created
                
            except Exception as e:
                logger.error(f"Error processing user {user_id}, language {language}: {e}")
                continue
        
        logger.info(f"Backfill complete! Created {total_snapshots} total snapshots.")
        
    except Exception as e:
        logger.error(f"Error during full backfill: {e}")
        raise

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill verb knowledge snapshots')
    parser.add_argument('--user-id', help='Specific user ID to backfill')
    parser.add_argument('--language', help='Specific language to backfill')
    parser.add_argument('--max-lessons', type=int, help='Maximum number of lessons to process per user')
    parser.add_argument('--all', action='store_true', help='Backfill all users')
    
    args = parser.parse_args()
    
    if args.all:
        await backfill_all_users()
    elif args.user_id and args.language:
        await backfill_user_snapshots(args.user_id, args.language, args.max_lessons)
    else:
        print("Usage:")
        print("  python backfill_verb_knowledge_snapshots.py --all")
        print("  python backfill_verb_knowledge_snapshots.py --user-id USER_ID --language LANGUAGE")
        print("  python backfill_verb_knowledge_snapshots.py --user-id USER_ID --language LANGUAGE --max-lessons 5")

if __name__ == '__main__':
    asyncio.run(main()) 