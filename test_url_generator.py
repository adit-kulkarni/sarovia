#!/usr/bin/env python3

def generate_test_url():
    """Generate the URL to test the lesson conversation with 11 turns"""
    
    # From our debug data
    conversation_id = "b22a60ab-b3fb-41f2-b02e-a1f7b9876352"
    curriculum_id = "f8bcfebc-ddc8-4bd4-bd6e-49b0f04f08eb"
    lesson_id = "321"
    
    # Generate the URL for testing
    base_url = "http://localhost:3000/chat"
    
    # URL parameters for existing conversation
    params = [
        f"conversation={conversation_id}",
        f"curriculum_id={curriculum_id}",
        f"lesson_id={lesson_id}",
        "language=es",
        "level=Easy",
        "context=Lesson: First Words & Greetings"
    ]
    
    test_url = f"{base_url}?" + "&".join(params)
    
    print("=== Test URL for Lesson with 11 Turns ===\n")
    print("Copy and paste this URL into your browser:")
    print(f"\n{test_url}\n")
    
    print("Expected behavior:")
    print("1. Should detect as lesson conversation ✓")
    print("2. Should load existing 11 turns progress ✓") 
    print("3. Should show progress: 11/7 turns ✓")
    print("4. Should show completion button (floating green button) ✓")
    print("5. Clicking completion should return to dashboard ✓")
    
    print("\nDebugging tips:")
    print("- Open browser developer tools")
    print("- Check console for '[Lesson Detection]' and '[Progress]' logs")
    print("- Look for WebSocket 'lesson.progress' events")
    print("- Verify floating green completion button appears")

if __name__ == "__main__":
    generate_test_url() 