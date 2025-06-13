#!/usr/bin/env python3
"""
Pre-launch checklist script for Language Learning Platform
Run this before deploying to production
"""

import os
import requests
import json
from dotenv import load_dotenv
from supabase import create_client

def check_environment_variables():
    """Check if all required environment variables are set"""
    print("🔍 Checking Environment Variables...")
    
    required_vars = [
        'OPENAI_API_KEY',
        'SUPABASE_URL', 
        'SUPABASE_SERVICE_KEY',
        'SUPABASE_JWT_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All environment variables are set")
        return True

def check_database_connection():
    """Test database connection"""
    print("🗄️ Checking Database Connection...")
    
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase = create_client(url, key)
        
        # Simple query to test connection
        result = supabase.table('users').select('id').limit(1).execute()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_openai_api():
    """Test OpenAI API connection"""
    print("🤖 Checking OpenAI API...")
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        headers = {'Authorization': f'Bearer {api_key}'}
        
        response = requests.get('https://api.openai.com/v1/models', headers=headers)
        if response.status_code == 200:
            print("✅ OpenAI API connection successful")
            return True
        else:
            print(f"❌ OpenAI API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        return False

def check_required_tables():
    """Check if required database tables exist"""
    print("📋 Checking Database Schema...")
    
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase = create_client(url, key)
        
        required_tables = [
            'users', 'curriculums', 'conversations', 
            'messages', 'message_feedback', 'lesson_templates',
            'custom_lesson_templates', 'cached_insights'
        ]
        
        missing_tables = []
        for table in required_tables:
            try:
                supabase.table(table).select('*').limit(1).execute()
            except:
                missing_tables.append(table)
        
        if missing_tables:
            print(f"❌ Missing tables: {', '.join(missing_tables)}")
            return False
        else:
            print("✅ All required tables exist")
            return True
    except Exception as e:
        print(f"❌ Schema check failed: {e}")
        return False

def check_spacy_models():
    """Check if required spaCy models are installed"""
    print("🔤 Checking spaCy Models...")
    
    try:
        import spacy
        
        required_models = ['en_core_web_sm', 'es_core_news_sm']
        missing_models = []
        
        for model in required_models:
            try:
                spacy.load(model)
            except OSError:
                missing_models.append(model)
        
        if missing_models:
            print(f"❌ Missing spaCy models: {', '.join(missing_models)}")
            print("   Install with: python -m spacy download <model_name>")
            return False
        else:
            print("✅ All required spaCy models installed")
            return True
    except Exception as e:
        print(f"❌ spaCy check failed: {e}")
        return False

def check_server_health():
    """Check if server starts and responds"""
    print("🌐 Checking Server Health...")
    
    try:
        # This assumes server is running on localhost:8000
        response = requests.get('http://localhost:8000/api/curriculums', timeout=5)
        if response.status_code in [200, 401]:  # 401 is expected without auth
            print("✅ Server is responding")
            return True
        else:
            print(f"❌ Server responded with status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server not running or not accessible")
        print("   Start with: python server.py")
        return False
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        return False

def main():
    """Run all pre-launch checks"""
    print("🚀 Language Learning Platform - Pre-Launch Checklist")
    print("=" * 60)
    
    load_dotenv()
    
    checks = [
        check_environment_variables,
        check_database_connection,
        check_openai_api,
        check_required_tables,
        check_spacy_models,
        check_server_health
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with exception: {e}")
            results.append(False)
        print()
    
    print("=" * 60)
    print("📊 Summary:")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 All checks passed! Ready for launch!")
        return True
    else:
        print("\n⚠️  Some checks failed. Please fix issues before launching.")
        return False

if __name__ == "__main__":
    main() 