import re
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
LANGUAGE = 'es'
CURRICULUM_MD = 'spanish_curriculum_1.md'

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_lessons(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Split on "### Lesson X:"
    lesson_blocks = re.split(r'### Lesson \d+: ', text)[1:]
    lessons = []
    for i, block in enumerate(lesson_blocks, 1):
        # Title is first line
        lines = block.strip().split('\n')
        title = lines[0].strip()
        
        # Extract fields
        def extract(field):
            m = re.search(rf'\*\*{field}\*\*: (.+)', block)
            return m.group(1).strip() if m else None

        difficulty_field = extract('Difficulty')
        # Extract level and difficulty (e.g., "A1 - Easy" -> level: "A1", difficulty: "Easy")
        level = None
        difficulty = None
        if difficulty_field:
            m = re.match(r'([A-Z]\d+)\s*-\s*(.+)', difficulty_field)
            if m:
                level = m.group(1)
                difficulty = m.group(2)
            else:
                # fallback: if only level or only difficulty is present
                if re.match(r'^[A-Z]\d+$', difficulty_field):
                    level = difficulty_field
                else:
                    difficulty = difficulty_field
        
        objectives = extract('Objectives')
        content = extract('Content')
        cultural = extract('Cultural Element')
        practice = extract('Practice Activity')

        lessons.append({
            'language': LANGUAGE,
            'level': level,
            'difficulty': difficulty,
            'order_num': i,
            'title': title,
            'objectives': objectives,
            'content': content,
            'cultural_element': cultural,
            'practice_activity': practice,
        })
    return lessons

def insert_lessons(lessons):
    for lesson in lessons:
        try:
            # Insert or update lesson in lesson_templates table
            result = supabase.table('lesson_templates').upsert(lesson).execute()
            print(f"Processed lesson {lesson['order_num']} (Level: {lesson['level']}, Difficulty: {lesson['difficulty']}): {lesson['title']}")
        except Exception as e:
            print(f"Error processing lesson {lesson['order_num']}: {str(e)}")

if __name__ == '__main__':
    lessons = parse_lessons(CURRICULUM_MD)
    print(f"Parsed {len(lessons)} lessons.")
    insert_lessons(lessons)
    print("Done.")