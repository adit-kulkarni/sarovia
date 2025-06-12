#!/usr/bin/env python3

import os
import json
import re
import spacy
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict, Counter
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
    logging.info("Loaded Spanish SpaCy model")
except OSError:
    logging.error("Spanish SpaCy model not found. Install with: python -m spacy download es_core_news_sm")
    exit(1)

def extract_vocabulary_from_text(text, language='es'):
    """Extract vocabulary from text using NLP"""
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
        if token.is_alpha and len(token.text) > 1:  # Only alphabetic tokens longer than 1 char
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
            elif pos == 'ADP':  # Adpositions (prepositions)
                vocabulary['prepositions'].add(lemma)
            elif pos in ['CCONJ', 'SCONJ']:  # Coordinating and subordinating conjunctions
                vocabulary['conjunctions'].add(lemma)
            elif pos == 'DET':  # Determiners (includes articles)
                vocabulary['articles'].add(lemma)
            elif pos == 'INTJ':
                vocabulary['interjections'].add(lemma)
    
    return vocabulary

def get_all_user_conversations():
    """Get all conversations with user messages"""
    try:
        conversations = supabase.table('conversations').select('*').execute()
        logging.info(f"Found {len(conversations.data)} conversations")
        return conversations.data
    except Exception as e:
        logging.error(f"Error fetching conversations: {e}")
        return []

def get_user_messages_for_conversation(conversation_id):
    """Get all user messages for a conversation with timestamps"""
    try:
        messages = supabase.table('messages').select('*').eq(
            'conversation_id', conversation_id
        ).eq('role', 'user').order('created_at').execute()
        
        return messages.data
    except Exception as e:
        logging.error(f"Error fetching messages for conversation {conversation_id}: {e}")
        return []

def calculate_vocabulary_diversity_score(vocabulary_counts):
    """Calculate a diversity score based on vocabulary breadth"""
    total_words = sum(vocabulary_counts.values())
    if total_words == 0:
        return 0
    
    # Weight different parts of speech
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
    return min(weighted_score / 10, 100)  # Scale to 0-100

def process_conversations_to_snapshots():
    """Process all conversations and create daily knowledge snapshots"""
    conversations = get_all_user_conversations()
    
    # Group by user and language
    user_language_data = defaultdict(lambda: defaultdict(list))
    
    for conversation in conversations:
        user_id = conversation['user_id']
        language = conversation['language']
        curriculum_id = conversation.get('curriculum_id')
        conversation_id = conversation['id']
        created_at = conversation['created_at']
        
        # Get user messages for this conversation
        messages = get_user_messages_for_conversation(conversation_id)
        
        if messages:
            user_language_data[user_id][language].append({
                'conversation_id': conversation_id,
                'curriculum_id': curriculum_id,
                'messages': messages,
                'created_at': created_at
            })
    
    logging.info(f"Processing {len(user_language_data)} users")
    
    # Process each user's language data
    for user_id, languages in user_language_data.items():
        for language, conversations in languages.items():
            logging.info(f"Processing user {user_id} for language {language} - {len(conversations)} conversations")
            
            # Sort conversations by date
            conversations.sort(key=lambda x: x['created_at'])
            
            # Track cumulative vocabulary over time
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
            
            # Process conversations chronologically
            daily_snapshots = {}
            
            for conv_data in conversations:
                conversation_id = conv_data['conversation_id']
                curriculum_id = conv_data['curriculum_id']
                messages = conv_data['messages']
                
                # Extract vocabulary from all messages in this conversation
                conversation_vocabulary = {
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
                
                for message in messages:
                    if message['content']:
                        vocab = extract_vocabulary_from_text(message['content'], language)
                        for part, words in vocab.items():
                            conversation_vocabulary[part].update(words)
                
                # Add to cumulative vocabulary
                for part, words in conversation_vocabulary.items():
                    cumulative_vocabulary[part].update(words)
                
                # Create snapshot for this conversation's date
                message_date = messages[0]['created_at'][:10]  # Get YYYY-MM-DD
                
                # Count vocabulary
                vocabulary_counts = {part: len(words) for part, words in cumulative_vocabulary.items()}
                
                # Calculate scores
                diversity_score = calculate_vocabulary_diversity_score(vocabulary_counts)
                complexity_score = min(sum(vocabulary_counts.values()) / 20, 100)  # Simple complexity based on total vocab
                
                # Store daily snapshot (use the highest counts for each day)
                if message_date not in daily_snapshots or vocabulary_counts['verbs'] > daily_snapshots[message_date]['verbs_count']:
                    daily_snapshots[message_date] = {
                        'user_id': user_id,
                        'language': language,
                        'curriculum_id': curriculum_id,
                        'conversation_id': conversation_id,
                        'snapshot_reason': 'conversation_end',
                        'verbs_count': vocabulary_counts['verbs'],
                        'verbs_with_tenses_count': min(vocabulary_counts['verbs'], vocabulary_counts['verbs'] // 2),  # Estimate
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
                        'snapshot_at': message_date + 'T23:59:59Z'
                    }
            
            # Insert all snapshots for this user/language
            if daily_snapshots:
                snapshots_list = list(daily_snapshots.values())
                logging.info(f"Inserting {len(snapshots_list)} snapshots for user {user_id} language {language}")
                
                try:
                    # Insert in batches to avoid overwhelming the database
                    batch_size = 50
                    for i in range(0, len(snapshots_list), batch_size):
                        batch = snapshots_list[i:i + batch_size]
                        supabase.table('knowledge_snapshots').upsert(batch).execute()
                        
                    logging.info(f"Successfully inserted snapshots for user {user_id} language {language}")
                except Exception as e:
                    logging.error(f"Error inserting snapshots for user {user_id}: {e}")

def main():
    """Main execution function"""
    logging.info("Starting comprehensive knowledge snapshots backfill...")
    
    # Clear existing snapshots (optional - remove if you want to keep existing data)
    try:
        logging.info("Clearing existing knowledge snapshots...")
        supabase.table('knowledge_snapshots').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    except Exception as e:
        logging.warning(f"Could not clear existing snapshots: {e}")
    
    # Process all conversations
    process_conversations_to_snapshots()
    
    logging.info("✅ Knowledge snapshots backfill completed!")
    
    # Show summary
    try:
        result = supabase.table('knowledge_snapshots').select('*', count='exact').execute()
        logging.info(f"📊 Total snapshots created: {result.count}")
        
        # Show sample data
        sample = supabase.table('knowledge_snapshots').select('*').limit(5).execute()
        logging.info("📝 Sample snapshots:")
        for snap in sample.data:
            logging.info(f"  User: {snap['user_id'][:8]}... Date: {snap['snapshot_at'][:10]} Verbs: {snap['verbs_count']} Nouns: {snap['nouns_count']}")
            
    except Exception as e:
        logging.error(f"Error getting summary: {e}")

if __name__ == "__main__":
    main() 