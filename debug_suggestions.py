import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from server import check_lesson_suggestion_threshold, generate_lesson_with_openai

async def debug_suggestions():
    print("🔍 Debugging lesson suggestions...")
    
    # Test with a real curriculum ID that might exist
    # First, let's check what curriculums exist
    from server import supabase
    
    try:
        # Get a real curriculum
        curriculums = supabase.table('curriculums').select('*').limit(5).execute()
        print(f"Found {len(curriculums.data)} curriculums")
        
        if not curriculums.data:
            print("❌ No curriculums found - need to create one first")
            return
        
        curriculum = curriculums.data[0]
        user_id = curriculum['user_id']
        curriculum_id = curriculum['id']
        language = curriculum['language']
        
        print(f"✓ Testing with curriculum: {curriculum_id}")
        print(f"  Language: {language}")
        print(f"  User: {user_id}")
        
        # Check threshold
        print("\n1. Checking threshold...")
        threshold_result = await check_lesson_suggestion_threshold(user_id, curriculum_id)
        print(f"Threshold result: {threshold_result}")
        
        if not threshold_result.get("needs_suggestion"):
            print("❌ Threshold not met - need more mistakes")
            print("Creating fake patterns for testing...")
            
            # Create fake patterns for testing
            fake_patterns = [{
                'category': 'grammar',
                'type': 'verb tense',
                'frequency': 5,
                'severity_distribution': {'minor': 2, 'moderate': 3, 'critical': 0},
                'examples': [
                    {'error': 'I go yesterday', 'correction': 'I went yesterday', 'explanation': 'Past tense needed'}
                ],
                'language_feature_tags': ['past_tense']
            }]
            
            print("\n2. Testing lesson generation with fake pattern...")
            try:
                lesson = await generate_lesson_with_openai(fake_patterns, language, 'A1')
                print(f"✓ Lesson generation successful: {lesson.get('title', 'No title')}")
            except Exception as e:
                print(f"❌ Lesson generation failed: {e}")
                print("This might be an OpenAI API issue")
        else:
            patterns = threshold_result.get("patterns", [])
            print(f"✓ Threshold met with {len(patterns)} patterns")
            
            if patterns:
                print("\n2. Testing lesson generation with real patterns...")
                try:
                    lesson = await generate_lesson_with_openai(patterns[:1], language, 'A1')
                    print(f"✓ Lesson generation successful: {lesson.get('title', 'No title')}")
                except Exception as e:
                    print(f"❌ Lesson generation failed: {e}")
            else:
                print("❌ No patterns found despite threshold being met")
                
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_suggestions()) 