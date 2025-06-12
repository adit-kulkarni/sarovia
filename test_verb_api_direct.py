#!/usr/bin/env python3

import os
from supabase import create_client
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def test_verb_counting():
    try:
        # Get verb knowledge snapshots for the test user
        verb_snapshots = supabase.table('verb_knowledge_snapshots').select(
            'snapshot_at, verb_knowledge'
        ).eq('user_id', '119c618c-0e1c-4984-94ad-0e15f70b7c31').eq('language', 'es').eq(
            'curriculum_id', 'f8bcfebc-ddc8-4bd4-bd6e-49b0f04f08eb'
        ).order('snapshot_at').limit(10).execute()
        
        print(f"Found {len(verb_snapshots.data)} verb snapshots")
        
        if not verb_snapshots.data:
            print("No verb snapshots found")
            return
        
        # Process verb snapshots - group by date and count unique verbs
        daily_verb_counts = defaultdict(int)
        
        for snapshot in verb_snapshots.data:
            date = snapshot['snapshot_at'][:10]  # Get YYYY-MM-DD
            verb_knowledge = snapshot.get('verb_knowledge', {})
            
            # Simple count of unique verbs
            verb_count = len(verb_knowledge) if verb_knowledge else 0
            
            print(f"Date: {date}, Verb count: {verb_count}")
            
            # Take the maximum count for each day (in case of multiple snapshots)
            daily_verb_counts[date] = max(daily_verb_counts[date], verb_count)
        
        # Convert to timeline format
        timeline_data = []
        for date in sorted(daily_verb_counts.keys()):
            timeline_data.append({
                'date': date,
                'verbs_total': daily_verb_counts[date]
            })
            
        print("\nTimeline data:")
        for item in timeline_data:
            print(f"  {item['date']}: {item['verbs_total']} verbs")
        
        result = {
            "timeline_data": timeline_data,
            "total_snapshots": len(verb_snapshots.data),
            "date_range": {
                "start": timeline_data[0]['date'] if timeline_data else None,
                "end": timeline_data[-1]['date'] if timeline_data else None
            }
        }
        
        print(f"\nFinal result: {result}")
        
    except Exception as e:
        print('ERROR:', str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_verb_counting() 