import os
import json
from supabase import create_client
from dotenv import load_dotenv
import aiohttp
import asyncio
import re

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def fetch_user_messages(user_id, language):
    conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('language', language).execute()
    conversation_ids = [c['id'] for c in conversations.data]
    if not conversation_ids:
        return []
    messages = []
    for cid in conversation_ids:
        res = supabase.table('messages').select('content', 'role').eq('conversation_id', cid).eq('role', 'user').order('created_at', desc=False).execute()
        messages.extend([m['content'] for m in res.data if m['role'] == 'user'])
    return messages

def build_prompt(messages, language):
    transcript = "\n".join(messages)
    prompt = f"""
You are a language learning assistant. Analyze the following transcript of a user's {language} messages. For each part of speech, provide a list of unique words the user has used:
- nouns
- pronouns
- adjectives
- verbs (for each verb, list the lemma, and for each lemma, all tenses and persons used, e.g., 'ir': {{'Presente': ['yo', 'tú'], 'Pretérito': ['él', 'ellos']}})
- adverbs
- prepositions
- conjunctions
- articles
- interjections

Output ONLY a valid JSON object with this structure, and nothing else (no markdown, no explanation, no code block):
{{
  "nouns": ["..."],
  "pronouns": ["..."],
  "adjectives": ["..."],
  "verbs": {{
    "lemma": {{
      "tense": ["person1", "person2", ...],
      ...
    }},
    ...
  }},
  "adverbs": ["..."],
  "prepositions": ["..."],
  "conjunctions": ["..."],
  "articles": ["..."],
  "interjections": ["..."]
}}

Here is the transcript:
{transcript}
"""
    return prompt

def extract_json_from_response(text):
    # Remove code block markers if present
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*', '', text)
        text = text.strip('`\n')
    # Find the first JSON object in the text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except Exception:
            pass
    # Fallback: try to parse the whole text
    try:
        return json.loads(text)
    except Exception:
        return None

async def analyze_with_openai(prompt):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4-turbo-preview",
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1500
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            data = await response.json()
            return data["choices"][0]["message"]["content"]

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze user's language knowledge using OpenAI completions API.")
    parser.add_argument('--user_id', required=True, help='Supabase user ID')
    parser.add_argument('--language', default='en', help='Language code (e.g., en, es)')
    args = parser.parse_args()

    messages = await fetch_user_messages(args.user_id, args.language)
    if not messages:
        print(f"No {args.language} user messages found for this user.")
        return
    prompt = build_prompt(messages, args.language)
    print(f"Sending {args.language} transcript to OpenAI for analysis...")
    result = await analyze_with_openai(prompt)
    parsed = extract_json_from_response(result)
    out_file = f'user_knowledge_llm_summary_{args.language}.json' if parsed is not None else f'user_knowledge_llm_summary_{args.language}_raw.txt'
    if parsed is not None:
        with open(out_file, 'w') as f:
            json.dump(parsed, f, indent=2)
        print(f"Structured summary written to {out_file}")
    else:
        with open(out_file, 'w') as f:
            f.write(result)
        print(f"Raw output written to {out_file} (could not parse as JSON)")

if __name__ == "__main__":
    asyncio.run(main()) 