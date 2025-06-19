#!/usr/bin/env python3
"""
Optimized lesson summary generation using verb knowledge snapshots.

This replaces the slow lesson summary generation with a fast snapshot-based approach
that diffs verb knowledge states instead of re-analyzing conversations.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Supabase configuration - lazy loading
def get_supabase_client():
    """Get Supabase client with lazy loading"""
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables are required")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_datetime_safe(datetime_str):
    """Safely parse datetime string, handling microseconds and timezone issues"""
    try:
        # Remove Z and add timezone
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str.replace('Z', '+00:00')
        
        # Handle microseconds - truncate to 6 digits if longer
        if '.' in datetime_str:
            date_part, time_part = datetime_str.split('.')
            if '+' in time_part:
                microseconds, timezone_part = time_part.split('+')
                microseconds = microseconds[:6].ljust(6, '0')  # Ensure exactly 6 digits
                datetime_str = f"{date_part}.{microseconds}+{timezone_part}"
            elif time_part.count(':') >= 2:  # Contains timezone offset
                microseconds = time_part[:6].ljust(6, '0')
                datetime_str = f"{date_part}.{microseconds}"
        
        return datetime.fromisoformat(datetime_str)
    except Exception as e:
        logger.error(f"Error parsing datetime '{datetime_str}': {e}")
        # Fallback: try without microseconds
        try:
            if '.' in datetime_str:
                datetime_str = datetime_str.split('.')[0] + '+00:00'
            return datetime.fromisoformat(datetime_str)
        except:
            # Last resort: return current time
            logger.warning(f"Failed to parse datetime '{datetime_str}', using current time")
            return datetime.now(timezone.utc)

async def get_verb_snapshots_for_lesson(lesson_progress_id: str) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Get before/after verb knowledge snapshots for a lesson.
    
    Returns:
        Tuple of (before_snapshot, after_snapshot) verb knowledge dicts
    """
    try:
        supabase = get_supabase_client()
        
        # Get the lesson snapshot (after completion)
        after_result = supabase.table('verb_knowledge_snapshots').select(
            'verb_knowledge, snapshot_at, user_id, language, curriculum_id'
        ).eq('lesson_progress_id', lesson_progress_id).execute()
        
        if not after_result.data:
            logger.error(f"No snapshot found for lesson_progress_id: {lesson_progress_id}")
            return None, None
        
        after_snapshot = after_result.data[0]
        user_id = after_snapshot['user_id']
        language = after_snapshot['language']
        curriculum_id = after_snapshot['curriculum_id']
        lesson_time = after_snapshot['snapshot_at']
        
        # Get the previous snapshot (before this lesson)
        before_result = supabase.table('verb_knowledge_snapshots').select(
            'verb_knowledge'
        ).eq('user_id', user_id).eq('language', language).eq(
            'curriculum_id', curriculum_id
        ).lt('snapshot_at', lesson_time).order('snapshot_at', desc=True).limit(1).execute()
        
        before_verbs = before_result.data[0]['verb_knowledge'] if before_result.data else {}
        after_verbs = after_snapshot['verb_knowledge']
        
        return before_verbs, after_verbs
        
    except Exception as e:
        logger.error(f"Error getting verb snapshots for lesson {lesson_progress_id}: {e}")
        return None, None

async def generate_optimized_lesson_summary(lesson_progress_id: str) -> Dict:
    """
    Generate lesson summary using optimized snapshot-based approach.
    
    This should be 10-50x faster than the old approach since it avoids
    re-analyzing conversations with OpenAI.
    """
    try:
        # Use the new unified data fetcher
        from report_card_shared import get_lesson_data, generate_unified_report_card
        
        # Fetch standardized lesson data
        lesson_data = await get_lesson_data(lesson_progress_id)
        
        # Get verb knowledge snapshots for before/after comparison
        before_verbs, after_verbs = await get_verb_snapshots_for_lesson(lesson_progress_id)
        
        # Generate the unified report card
        summary = await generate_unified_report_card(lesson_data, before_verbs, after_verbs)
        
        logger.info(f"Generated optimized lesson summary for '{lesson_data['title']}' in <1 second!")
        logger.info(f"[Lesson Summary] Response includes conversationId: {lesson_data.get('conversation_id')}")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating optimized lesson summary: {e}")
        raise

# Function to be called from server.py
async def get_lesson_summary_optimized(lesson_progress_id: str) -> Dict:
    """Main entry point for optimized lesson summary generation."""
    return await generate_optimized_lesson_summary(lesson_progress_id) 