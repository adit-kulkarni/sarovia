#!/usr/bin/env python3

import os
import json
import spacy
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

# Load SpaCy model for Spanish
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    logging.warning("Spanish SpaCy model not found. Some features may not work.")
    nlp = None

def extract_vocabulary_from_text(text, language='es'):
    """Extract vocabulary from text using NLP"""
    if not nlp:
        return {
            'verbs': set(),
            'nouns': set(),
            'adjectives': set(),
            'pronouns': set(),
            'adverbs': set(),
            'prepositions': set(),
            'conjunctions': set(),
            'articles': set(),
            'interjections': set()
        }
    
    doc = nlp(text.lower())
    
    vocabulary = {
        'verbs': set(),
        'nouns': set(), 
        'adjectives': set(),
        'pronouns': set(),
        'adverbs': set(),
        'prepositions': set(),
        'conjunctions': set(),
        'articles': set(),
        'interjections': set()
    }
    
    for token in doc:
        if token.is_alpha and len(token.text) > 1:
            lemma = token.lemma_
            pos = token.pos_
            
            if pos == 'VERB':
                vocabulary['verbs'].add(lemma)
            elif pos == 'NOUN':
                vocabulary['nouns'].add(lemma)
            elif pos == 'ADJ':
                vocabulary['adjectives'].add(lemma)
            elif pos == 'PRON':
                vocabulary['pronouns'].add(lemma)
            elif pos == 'ADV':
                vocabulary['adverbs'].add(lemma)
            elif pos == 'ADP':
                vocabulary['prepositions'].add(lemma)
            elif pos in ['CCONJ', 'SCONJ']:
                vocabulary['conjunctions'].add(lemma)
            elif pos == 'DET':
                vocabulary['articles'].add(lemma)
            elif pos == 'INTJ':
                vocabulary['interjections'].add(lemma)
    
    return vocabulary

def get_user_cumulative_vocabulary(user_id, language, up_to_date=None):
    """Get all vocabulary used by a user up to a certain date"""
    try:
        # Get all conversations for this user/language up to the date
        query = supabase.table('conversations').select('id, created_at').eq(
            'user_id', user_id
        ).eq('language', language)
        
        if up_to_date:
            query = query.lte('created_at', up_to_date)
        
        conversations = query.order('created_at').execute()
        
        if not conversations.data:
            return {
                'verbs': set(),
                'nouns': set(),
                'adjectives': set(),
                'pronouns': set(),
                'adverbs': set(),
                'prepositions': set(),
                'conjunctions': set(),
                'articles': set(),
                'interjections': set()
            }
        
        conversation_ids = [conv['id'] for conv in conversations.data]
        
        # Get all user messages from these conversations
        messages = supabase.table('messages').select('content, created_at').in_(
            'conversation_id', conversation_ids
        ).eq('role', 'user').order('created_at').execute()
        
        # Extract vocabulary from all messages
        cumulative_vocabulary = {
            'verbs': set(),
            'nouns': set(),
            'adjectives': set(),
            'pronouns': set(),
            'adverbs': set(),
            'prepositions': set(),
            'conjunctions': set(),
            'articles': set(),
            'interjections': set()
        }
        
        for message in messages.data:
            if message['content']:
                vocab = extract_vocabulary_from_text(message['content'], language)
                for part, words in vocab.items():
                    cumulative_vocabulary[part].update(words)
        
        return cumulative_vocabulary
        
    except Exception as e:
        logging.error(f"Error getting cumulative vocabulary: {e}")
        return {
            'verbs': set(),
            'nouns': set(),
            'adjectives': set(),
            'pronouns': set(),
            'adverbs': set(),
            'prepositions': set(),
            'conjunctions': set(),
            'articles': set(),
            'interjections': set()
        }

def calculate_vocabulary_diversity_score(vocabulary_counts):
    """Calculate a diversity score based on vocabulary breadth"""
    total_words = sum(vocabulary_counts.values())
    if total_words == 0:
        return 0
    
    weights = {
        'verbs': 3.0,
        'adjectives': 2.5,
        'nouns': 2.0,
        'adverbs': 2.0,
        'pronouns': 1.5,
        'prepositions': 1.0,
        'conjunctions': 1.0,
        'articles': 0.5,
        'interjections': 0.5
    }
    
    weighted_score = sum(count * weights.get(part, 1.0) for part, count in vocabulary_counts.items())
    return min(weighted_score / 10, 100)

def create_knowledge_snapshot(user_id, conversation_id, language, curriculum_id=None, lesson_progress_id=None):
    """Create a knowledge snapshot after a conversation"""
    try:
        # Get conversation details
        conversation = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
        if not conversation.data:
            logging.error(f"Conversation {conversation_id} not found")
            return False
        
        conv_data = conversation.data[0]
        conversation_date = conv_data['created_at']
        
        # Get cumulative vocabulary up to this conversation
        cumulative_vocabulary = get_user_cumulative_vocabulary(user_id, language, conversation_date)
        
        # Count vocabulary
        vocabulary_counts = {part: len(words) for part, words in cumulative_vocabulary.items()}
        
        # Calculate scores
        diversity_score = calculate_vocabulary_diversity_score(vocabulary_counts)
        complexity_score = min(sum(vocabulary_counts.values()) / 20, 100)
        
        # Create snapshot
        snapshot_data = {
            'user_id': user_id,
            'language': language,
            'curriculum_id': curriculum_id,
            'conversation_id': conversation_id,
            'lesson_progress_id': lesson_progress_id,
            'snapshot_reason': 'conversation_end',
            'verbs_count': vocabulary_counts['verbs'],
            'verbs_with_tenses_count': min(vocabulary_counts['verbs'], vocabulary_counts['verbs'] // 2),
            'nouns_count': vocabulary_counts['nouns'],
            'adjectives_count': vocabulary_counts['adjectives'],
            'pronouns_count': vocabulary_counts['pronouns'],
            'adverbs_count': vocabulary_counts['adverbs'],
            'prepositions_count': vocabulary_counts['prepositions'],
            'conjunctions_count': vocabulary_counts['conjunctions'],
            'articles_count': vocabulary_counts['articles'],
            'interjections_count': vocabulary_counts['interjections'],
            'vocabulary_diversity_score': diversity_score,
            'complexity_score': complexity_score,
            'snapshot_at': conversation_date
        }
        
        # Upsert the snapshot
        supabase.table('knowledge_snapshots').upsert(snapshot_data).execute()
        
        logging.info(f"✅ Created knowledge snapshot for conversation {conversation_id}")
        logging.info(f"   Verbs: {vocabulary_counts['verbs']}, Nouns: {vocabulary_counts['nouns']}, Adjectives: {vocabulary_counts['adjectives']}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error creating knowledge snapshot: {e}")
        return False

def update_knowledge_for_conversation(conversation_id):
    """Main function to update knowledge snapshots for a specific conversation"""
    try:
        # Get conversation details
        conversation = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
        if not conversation.data:
            logging.error(f"Conversation {conversation_id} not found")
            return False
        
        conv_data = conversation.data[0]
        user_id = conv_data['user_id']
        language = conv_data['language']
        curriculum_id = conv_data.get('curriculum_id')
        
        # Check if this is a lesson conversation
        lesson_progress_id = None
        if conv_data.get('lesson_id') or conv_data.get('custom_lesson_id'):
            # Try to find lesson progress
            progress = supabase.table('lesson_progress').select('id').eq(
                'conversation_id', conversation_id
            ).execute()
            if progress.data:
                lesson_progress_id = progress.data[0]['id']
        
        # Create the snapshot
        success = create_knowledge_snapshot(
            user_id, conversation_id, language, curriculum_id, lesson_progress_id
        )
        
        return success
        
    except Exception as e:
        logging.error(f"Error updating knowledge for conversation {conversation_id}: {e}")
        return False

def main():
    """Main function for standalone usage"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python incremental_knowledge_update_comprehensive.py <conversation_id>")
        sys.exit(1)
    
    conversation_id = sys.argv[1]
    success = update_knowledge_for_conversation(conversation_id)
    
    if success:
        print(f"✅ Successfully updated knowledge for conversation {conversation_id}")
    else:
        print(f"❌ Failed to update knowledge for conversation {conversation_id}")
        sys.exit(1)

if __name__ == "__main__":
    main() 