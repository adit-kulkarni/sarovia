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

def calculate_verb_achievements(before_verbs: Dict, after_verbs: Dict, lesson_title: str) -> List[Dict]:
    """
    Calculate verb-related achievements by comparing before/after verb knowledge states.
    
    This is MUCH faster than the old approach since we're just doing dict comparisons
    instead of re-analyzing all conversations with OpenAI.
    """
    achievements = []
    
    # Track new verbs learned
    before_verb_set = set(before_verbs.keys()) if before_verbs else set()
    after_verb_set = set(after_verbs.keys()) if after_verbs else set()
    new_verbs = after_verb_set - before_verb_set
    
    if new_verbs:
        achievements.append({
            "id": "new_verbs",
            "title": f"New Verbs Used: {len(new_verbs)}",
            "description": f"You successfully used {', '.join(list(new_verbs)[:3])}{'...' if len(new_verbs) > 3 else ''} for the first time!",
            "icon": "🆕",
            "type": "new",
            "value": len(new_verbs),
            "verbs": list(new_verbs)  # Include the full list of verbs
        })
    
    # Track improved verb forms (existing verbs with new tenses/persons)
    improved_verbs = []
    for verb in before_verb_set.intersection(after_verb_set):
        before_forms = set()
        after_forms = set()
        
        # Flatten all tenses and persons for comparison
        if verb in before_verbs:
            for tense, persons in before_verbs[verb].items():
                for person in persons:
                    before_forms.add(f"{tense}_{person}")
        
        if verb in after_verbs:
            for tense, persons in after_verbs[verb].items():
                for person in persons:
                    after_forms.add(f"{tense}_{person}")
        
        new_forms = after_forms - before_forms
        if new_forms:
            improved_verbs.append({
                "verb": verb,
                "new_forms": len(new_forms),
                "forms": list(new_forms)[:2]  # Show first 2 forms
            })
    
    if improved_verbs:
        total_new_forms = sum(v["new_forms"] for v in improved_verbs)
        achievements.append({
            "id": "improved_verbs",
            "title": f"Verb Forms Expanded: {total_new_forms}",
            "description": f"You mastered new forms of {improved_verbs[0]['verb']} and {len(improved_verbs)-1} other verbs!" if len(improved_verbs) > 1 else f"You mastered new forms of {improved_verbs[0]['verb']}!",
            "icon": "📈",
            "type": "improved",
            "value": total_new_forms,
            "improved_verbs": improved_verbs  # Include the full improved verbs data
        })
    
    # Track verb diversity milestone
    total_verbs_after = len(after_verb_set)
    if total_verbs_after >= 10 and total_verbs_after % 5 == 0:
        achievements.append({
            "id": "verb_milestone",
            "title": f"Verb Vocabulary: {total_verbs_after} Verbs!",
            "description": f"You've now successfully used {total_verbs_after} different verbs in conversations. ¡Excelente!",
            "icon": "🎯",
            "type": "milestone",
            "value": total_verbs_after
        })
    
    # Calculate verb strength ranking changes
    before_ranking = generate_verb_strength_ranking(before_verbs)
    after_ranking = generate_verb_strength_ranking(after_verbs)
    
    # Check for significant ranking improvements
    ranking_improvements = []
    for i, (verb, score) in enumerate(after_ranking[:5]):  # Top 5 verbs
        before_position = next((j for j, (v, _) in enumerate(before_ranking) if v == verb), None)
        if before_position is None or before_position > i:
            improvement = "new" if before_position is None else before_position - i
            ranking_improvements.append((verb, improvement))
    
    if ranking_improvements:
        top_verb, improvement = ranking_improvements[0]
        if improvement == "new":
            achievements.append({
                "id": "top_verb_new",
                "title": f"Rising Star: {top_verb}",
                "description": f"'{top_verb}' jumped into your top 5 most mastered verbs!",
                "icon": "⭐",
                "type": "improved",
                "value": top_verb
            })
        elif improvement > 2:
            achievements.append({
                "id": "top_verb_jump",
                "title": f"Verb Mastery Jump: {top_verb}",
                "description": f"'{top_verb}' climbed {improvement} positions in your verb strength ranking!",
                "icon": "🚀",
                "type": "improved",
                "value": improvement
            })
    
    return achievements

def generate_verb_strength_ranking(verbs: Dict) -> List[Tuple[str, int]]:
    """Generate verb strength ranking based on number of forms mastered."""
    if not verbs:
        return []
    
    verb_scores = []
    for verb, tenses in verbs.items():
        # Score based on number of tenses and persons
        score = 0
        for tense, persons in tenses.items():
            score += len(persons)
        verb_scores.append((verb, score))
    
    # Sort by score descending
    verb_scores.sort(key=lambda x: x[1], reverse=True)
    return verb_scores

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
            'id, lesson_id, turns_completed, required_turns, completed_at, conversation_id'
        ).eq('id', lesson_progress_id).execute()
        
        if not lesson_result.data:
            raise ValueError(f"Lesson progress not found: {lesson_progress_id}")
        
        lesson_data = lesson_result.data[0]
        lesson_id = lesson_data.get('lesson_id')
        conversation_id = lesson_data.get('conversation_id')
        turns_completed = lesson_data.get('turns_completed', 0)
        required_turns = lesson_data.get('required_turns', 7)
        
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
        
        # Generate verb-based achievements (this is now super fast!)
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
        
        # Get mistake data from message_feedback (this is already fast)
        mistake_data = await get_lesson_mistakes(conversation_id)
        
        # Build the summary response
        summary = {
            "lessonTitle": lesson_title,
            "totalTurns": turns_completed,
            "totalMistakes": mistake_data['total_mistakes'],
            "achievements": achievements,
            "mistakesByCategory": mistake_data['mistakes_by_category'],
            "conversationDuration": conversation_duration,
            "wordsUsed": estimate_words_used(turns_completed),
            "newVocabulary": extract_new_vocabulary(before_verbs, after_verbs),
            "improvementAreas": generate_improvement_areas(mistake_data['mistakes_by_category']),
            "conversationId": conversation_id
        }
        
        logger.info(f"Generated optimized lesson summary for {lesson_title} in <1 second!")
        logger.info(f"[Lesson Summary] Response includes conversationId: {conversation_id}")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating optimized lesson summary: {e}")
        raise

async def get_lesson_mistakes(conversation_id: str) -> Dict:
    """Get mistake analysis for a lesson conversation."""
    if not conversation_id:
        return {"total_mistakes": 0, "mistakes_by_category": []}
    
    try:
        supabase = get_supabase_client()
        
        # Get message IDs for this conversation first
        messages_result = supabase.table('messages').select('id').eq('conversation_id', conversation_id).execute()
        message_ids = [msg['id'] for msg in messages_result.data]
        
        if not message_ids:
            return {"total_mistakes": 0, "mistakes_by_category": []}
            
        result = supabase.table('message_feedback').select(
            'mistakes'
        ).in_('message_id', message_ids).execute()
        
        all_mistakes = []
        for feedback in result.data:
            if feedback.get('mistakes'):
                all_mistakes.extend(feedback['mistakes'])
        
        # Group mistakes by category
        category_counts = {}
        for mistake in all_mistakes:
            category = mistake.get('category', 'Other')
            if category not in category_counts:
                category_counts[category] = {
                    'category': category,
                    'count': 0,
                    'severity': 'minor',
                    'examples': []
                }
            
            category_counts[category]['count'] += 1
            if len(category_counts[category]['examples']) < 2:
                category_counts[category]['examples'].append({
                    'error': mistake.get('error', ''),
                    'correction': mistake.get('correction', ''),
                    'explanation': mistake.get('explanation', '')
                })
        
        return {
            "total_mistakes": len(all_mistakes),
            "mistakes_by_category": list(category_counts.values())
        }
        
    except Exception as e:
        logger.error(f"Error getting lesson mistakes: {e}")
        return {"total_mistakes": 0, "mistakes_by_category": []}

def estimate_words_used(turns_completed: int) -> int:
    """Estimate words used based on conversation turns."""
    # Rough estimate: 8-12 words per turn on average
    return turns_completed * 10

def extract_new_vocabulary(before_verbs: Dict, after_verbs: Dict) -> List[str]:
    """Extract new vocabulary from verb knowledge diff."""
    if not before_verbs or not after_verbs:
        return []
    
    before_set = set(before_verbs.keys())
    after_set = set(after_verbs.keys())
    new_verbs = list(after_set - before_set)
    
    return new_verbs[:5]  # Return top 5 new verbs

def generate_improvement_areas(mistakes_by_category: List[Dict]) -> List[str]:
    """Generate improvement areas based on mistake patterns."""
    if not mistakes_by_category:
        return ["Keep practicing conversation skills!"]
    
    # Sort by mistake count and suggest improvements
    sorted_categories = sorted(mistakes_by_category, key=lambda x: x['count'], reverse=True)
    
    improvement_areas = []
    for category in sorted_categories[:3]:  # Top 3 categories
        if category['category'] == 'Grammar':
            improvement_areas.append("Focus on grammar structures and verb conjugations")
        elif category['category'] == 'Vocabulary':
            improvement_areas.append("Expand vocabulary through reading and listening")
        elif category['category'] == 'Spelling':
            improvement_areas.append("Practice spelling of commonly used words")
        else:
            improvement_areas.append(f"Work on {category['category'].lower()} skills")
    
    return improvement_areas or ["Keep up the great conversation practice!"]

# Function to be called from server.py
async def get_lesson_summary_optimized(lesson_progress_id: str) -> Dict:
    """Main entry point for optimized lesson summary generation."""
    return await generate_optimized_lesson_summary(lesson_progress_id) 