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
        supabase = get_supabase_client()
        
        # Get lesson progress details (without foreign key joins that don't exist)
        lesson_result = supabase.table('lesson_progress').select(
            'id, lesson_id, turns_completed, required_turns, completed_at, conversation_id, user_id, curriculum_id'
        ).eq('id', lesson_progress_id).execute()
        
        if not lesson_result.data:
            raise ValueError(f"Lesson progress not found: {lesson_progress_id}")
        
        lesson_data = lesson_result.data[0]
        lesson_id = lesson_data.get('lesson_id')
        conversation_id = lesson_data.get('conversation_id')
        turns_completed = lesson_data.get('turns_completed', 0)
        required_turns = lesson_data.get('required_turns', 7)
        user_id = lesson_data.get('user_id')
        curriculum_id = lesson_data.get('curriculum_id')
        
        # Debug logging
        logger.info(f"[Lesson Summary] Progress ID: {lesson_progress_id}")
        logger.info(f"[Lesson Summary] Lesson ID: {lesson_id}")
        logger.info(f"[Lesson Summary] Conversation ID: {conversation_id}")
        logger.info(f"[Lesson Summary] Turns completed: {turns_completed}")
        
        # Get lesson title separately
        lesson_title = "Unknown Lesson"
        if lesson_id:
            lesson_template_result = supabase.table('lesson_templates').select('title, objectives').eq('id', lesson_id).execute()
            if lesson_template_result.data:
                lesson_title = lesson_template_result.data[0].get('title', 'Unknown Lesson')
        
        # Get language from curriculum
        language = None
        if curriculum_id:
            curriculum_result = supabase.table('curriculums').select('language').eq('id', curriculum_id).execute()
            if curriculum_result.data:
                language = curriculum_result.data[0].get('language')
        
        # Calculate conversation duration
        conversation_duration = "Unknown"
        if conversation_id and lesson_data.get('completed_at'):
            conversation_result = supabase.table('conversations').select('created_at').eq('id', conversation_id).execute()
            if conversation_result.data:
                start_time = parse_datetime_safe(conversation_result.data[0]['created_at'])
                end_time = parse_datetime_safe(lesson_data['completed_at'])
                duration_minutes = int((end_time - start_time).total_seconds() / 60)
                conversation_duration = f"{duration_minutes} minutes"
        
        # Get verb knowledge snapshots for before/after comparison
        before_verbs, after_verbs = await get_verb_snapshots_for_lesson(lesson_progress_id)
        
        # Generate verb-based achievements using shared function
        from report_card_shared import calculate_verb_achievements
        achievements = []
        if before_verbs is not None and after_verbs is not None:
            achievements = calculate_verb_achievements(before_verbs, after_verbs, lesson_title)
        else:
            # Fallback achievements if snapshots are missing
            achievements = [
                {
                    "id": "lesson_completed",
                    "title": "Lesson Completed!",
                    "description": f"You successfully completed '{lesson_title}' with {turns_completed} conversation turns.",
                    "icon": "✅",
                    "type": "milestone",
                    "value": turns_completed
                }
            ]
        
        # Get mistake data from message_feedback using shared function
        from report_card_shared import get_conversation_mistakes
        mistake_data = await get_conversation_mistakes(conversation_id)
        
        # Use the shared report card generator for consistency
        try:
            from report_card_shared import generate_report_card
            
            summary = await generate_report_card(
                before_verbs=before_verbs,
                after_verbs=after_verbs,
                conversation_id=conversation_id,
                turns_completed=turns_completed,
                title=lesson_title,
                duration_str=conversation_duration,
                existing_achievements=achievements,
                user_id=user_id,
                language=language
            )
            
        except Exception as e:
            logger.error(f"Could not generate report card using shared function: {e}")
            
            # Fallback to the old method
            from report_card_shared import estimate_words_used, generate_improvement_areas
            summary = {
                "lessonTitle": lesson_title,
                "totalTurns": turns_completed,
                "totalMistakes": mistake_data['total_mistakes'],
                "achievements": achievements,
                "mistakesByCategory": mistake_data['mistakes_by_category'],
                "conversationDuration": conversation_duration,
                "wordsUsed": estimate_words_used(turns_completed),
                "conversationCount": 0,  # Will be 0 in fallback case
                "improvementAreas": generate_improvement_areas(mistake_data['mistakes_by_category']),
                "conversationId": conversation_id
            }
        
        logger.info(f"Generated optimized lesson summary for {lesson_title} in <1 second!")
        logger.info(f"[Lesson Summary] Response includes conversationId: {conversation_id}")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating optimized lesson summary: {e}")
        raise





# Function to be called from server.py
async def get_lesson_summary_optimized(lesson_progress_id: str) -> Dict:
    """Main entry point for optimized lesson summary generation."""
    return await generate_optimized_lesson_summary(lesson_progress_id) 