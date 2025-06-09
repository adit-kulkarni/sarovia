import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from server import check_lesson_suggestion_threshold

async def test():
    try:
        result = await check_lesson_suggestion_threshold('test-user', 'test-curriculum')
        print('✓ Threshold function works:', result)
        return True
    except Exception as e:
        print('✗ Threshold function error:', e)
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    if success:
        print("✓ All functions working properly")
    else:
        print("✗ There are still issues to fix") 