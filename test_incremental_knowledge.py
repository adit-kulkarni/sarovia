#!/usr/bin/env python3

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_incremental_knowledge():
    """Test the incremental knowledge analysis system"""
    print("=== Testing Incremental Knowledge Analysis ===\n")
    
    # Test endpoints (adjust port as needed)
    base_url = "http://localhost:8000"
    
    # Mock user token (you'll need to replace this with a real token for testing)
    # You can get this from your browser's dev tools when logged in
    test_token = "your_test_token_here"
    
    if test_token == "your_test_token_here":
        print("❌ Please set a real test token in the script")
        print("   You can get this from your browser's dev tools when logged in")
        return
    
    # Test 1: Check current knowledge
    print("1. Checking current knowledge...")
    response = requests.get(f"{base_url}/api/user_knowledge", params={
        "language": "es",
        "token": test_token
    })
    
    if response.status_code == 200:
        data = response.json()
        if data.get("knowledge"):
            print("✅ Existing knowledge found")
            knowledge = data["knowledge"]
            for category, items in knowledge.items():
                if isinstance(items, dict):
                    print(f"   {category}: {len(items)} verbs")
                else:
                    print(f"   {category}: {len(items)} items")
        else:
            print("ℹ️  No existing knowledge found")
    else:
        print(f"❌ Error getting knowledge: {response.status_code}")
        return
    
    # Test 2: Trigger manual update
    print("\n2. Triggering manual knowledge update...")
    response = requests.post(f"{base_url}/api/user_knowledge/update", params={
        "language": "es",
        "token": test_token
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Update completed: {data.get('updated')}")
        print(f"   Conversations analyzed: {data.get('conversations_analyzed', 0)}")
        
        if data.get("knowledge"):
            knowledge = data["knowledge"]
            print("   Updated knowledge summary:")
            for category, items in knowledge.items():
                if isinstance(items, dict):
                    print(f"     {category}: {len(items)} verbs")
                else:
                    print(f"     {category}: {len(items)} items")
    else:
        print(f"❌ Error updating knowledge: {response.status_code}")
        print(f"   Response: {response.text}")
        return
    
    # Test 3: Check if knowledge is up to date (should show 0 new conversations)
    print("\n3. Checking if knowledge is up to date...")
    response = requests.post(f"{base_url}/api/user_knowledge/update", params={
        "language": "es", 
        "token": test_token
    })
    
    if response.status_code == 200:
        data = response.json()
        if data.get("conversations_analyzed", 0) == 0:
            print("✅ Knowledge is up to date (no new conversations to analyze)")
        else:
            print(f"⚠️  Still found {data.get('conversations_analyzed')} conversations to analyze")
    else:
        print(f"❌ Error in second update check: {response.status_code}")
    
    print("\n=== Test Complete ===")
    print("📝 The system should now automatically update knowledge after lesson completion!")

if __name__ == "__main__":
    test_incremental_knowledge() 