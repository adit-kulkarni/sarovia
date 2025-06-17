#!/usr/bin/env python3
"""
Shared Report Card Functions

This module contains all the modular functions for generating report cards
that can be used by both lesson summaries and conversation summaries.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

logger = logging.getLogger(__name__)

def get_supabase_client():
    """Get Supabase client instance"""
    return create_client(url, key)

def parse_datetime_safe(datetime_str):
    """Safely parse datetime string"""
    try:
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str.replace('Z', '+00:00')
        return datetime.fromisoformat(datetime_str)
    except Exception as e:
        logger.error(f"Error parsing datetime '{datetime_str}': {e}")
        return datetime.now(timezone.utc)

def estimate_words_used(turns_completed: int) -> int:
    """Estimate words used based on conversation turns."""
    # Rough estimate: 8-12 words per turn on average
    return turns_completed * 10



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

async def get_conversation_mistakes(conversation_id: str) -> Dict:
    """Get mistake analysis for a conversation."""
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
        logger.error(f"Error getting conversation mistakes: {e}")
        return {"total_mistakes": 0, "mistakes_by_category": []}

def calculate_verb_achievements(before_verbs: Dict, after_verbs: Dict, title: str) -> List[Dict]:
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

async def get_conversation_number(user_id: str, language: str, conversation_id: str) -> int:
    """Get the chronological position of this conversation for a user in a specific language."""
    try:
        supabase = get_supabase_client()
        
        # First get the creation time of the target conversation
        target_result = supabase.table('conversations').select('created_at').eq('id', conversation_id).execute()
        if not target_result.data:
            return 0
        
        target_created_at = target_result.data[0]['created_at']
        
        # Count how many conversations were created before or at the same time as this one
        count_result = supabase.table('conversations').select('id', count='exact').eq('user_id', user_id).eq('language', language).lte('created_at', target_created_at).execute()
        
        return count_result.count or 0
    except Exception as e:
        logger.error(f"Error getting conversation number: {e}")
        return 0

async def generate_report_card(
    before_verbs: Optional[Dict] = None,
    after_verbs: Optional[Dict] = None,
    conversation_id: Optional[str] = None,
    turns_completed: int = 0,
    title: str = "Session",
    duration_str: str = "Unknown",
    existing_achievements: Optional[List[Dict]] = None,
    user_id: Optional[str] = None,
    language: Optional[str] = None
) -> Dict:
    """
    Generate a complete report card using shared modular functions.
    
    This function can be used by both lesson summaries and conversation summaries
    to ensure consistency and avoid code duplication.
    """
    try:
        # Calculate verb achievements (or use existing ones)
        if existing_achievements is not None:
            achievements = existing_achievements[:]  # Copy the list
        else:
            achievements = []
            if before_verbs is not None and after_verbs is not None:
                achievements = calculate_verb_achievements(before_verbs, after_verbs, title)
        
        # Add engagement achievement for conversations with sufficient turns
        if turns_completed >= 5:
            achievements.append({
                "id": "conversation_engagement",
                "title": f"Great Conversation!",
                "description": f"You engaged in {turns_completed} turns of conversation practice.",
                "icon": "💬",
                "type": "engagement",
                "value": turns_completed
            })
        
        # Get mistake analysis
        mistake_data = await get_conversation_mistakes(conversation_id) if conversation_id else {"total_mistakes": 0, "mistakes_by_category": []}
        

        
        # Generate improvement areas
        improvement_areas = generate_improvement_areas(mistake_data['mistakes_by_category'])
        
        # Calculate words used
        words_used = estimate_words_used(turns_completed)
        
        # Get conversation number if user_id, language, and conversation_id are provided
        conversation_number = 0
        if user_id and language and conversation_id:
            conversation_number = await get_conversation_number(user_id, language, conversation_id)
        
        return {
            "lessonTitle": title,
            "totalTurns": turns_completed,
            "totalMistakes": mistake_data['total_mistakes'],
            "achievements": achievements,
            "mistakesByCategory": mistake_data['mistakes_by_category'],
            "conversationDuration": duration_str,
            "wordsUsed": words_used,
            "conversationCount": conversation_number,
            "improvementAreas": improvement_areas,
            "conversationId": conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error generating report card: {e}")
        raise 