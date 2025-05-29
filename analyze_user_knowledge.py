import os
import json
from supabase import create_client
import spacy
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Load spaCy English model
nlp = spacy.load("en_core_web_sm")

def fetch_english_messages(user_id):
    # Fetch all user messages for the user in English
    conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('language', 'en').execute()
    conversation_ids = [c['id'] for c in conversations.data]
    if not conversation_ids:
        return []
    messages = []
    for cid in conversation_ids:
        res = supabase.table('messages').select('content', 'role').eq('conversation_id', cid).eq('role', 'user').execute()
        messages.extend([m['content'] for m in res.data if m['role'] == 'user'])
    return messages

def analyze_messages(messages):
    # Data structures
    pos_categories = {
        'NOUN': 'nouns',
        'PRON': 'pronouns',
        'ADJ': 'adjectives',
        'VERB': 'verbs',
        'ADV': 'adverbs',
        'ADP': 'prepositions',
        'CCONJ': 'conjunctions',
        'DET': 'articles',
        'INTJ': 'interjections',
    }
    summary = {cat: set() for cat in pos_categories.values()}
    verb_details = defaultdict(lambda: defaultdict(set))  # lemma -> tense -> person set

    for msg in messages:
        doc = nlp(msg)
        for token in doc:
            cat = pos_categories.get(token.pos_)
            if not cat:
                continue
            lemma = token.lemma_.lower()
            if cat == 'verbs':
                # Get tense and person if available
                tense = token.morph.get('Tense')
                person = token.morph.get('Person')
                tense = tense[0] if tense else 'Unknown'
                person = person[0] if person else 'Unknown'
                verb_details[lemma][tense].add(person)
                summary[cat].add(lemma)
            else:
                summary[cat].add(lemma)
    # Convert sets to sorted lists for JSON
    for k in summary:
        summary[k] = sorted(list(summary[k]))
    # Format verb details
    verb_matrix = {}
    for lemma, tenses in verb_details.items():
        verb_matrix[lemma] = {tense: sorted(list(persons)) for tense, persons in tenses.items()}
    summary['verb_usage'] = verb_matrix
    return summary

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze user's English knowledge from conversations.")
    parser.add_argument('--user_id', required=True, help='Supabase user ID')
    args = parser.parse_args()

    messages = fetch_english_messages(args.user_id)
    if not messages:
        print("No English messages found for this user.")
        return
    summary = analyze_messages(messages)
    # Write to file
    with open('user_knowledge_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print("Summary written to user_knowledge_summary.json")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main() 