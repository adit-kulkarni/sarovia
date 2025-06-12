import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

# Get more snapshots to see date range
verb_snapshots = supabase.table('verb_knowledge_snapshots').select(
    'snapshot_at, verb_knowledge'
).eq('user_id', '119c618c-0e1c-4984-94ad-0e15f70b7c31').eq('language', 'es').eq(
    'curriculum_id', 'f8bcfebc-ddc8-4bd4-bd6e-49b0f04f08eb'
).order('snapshot_at').limit(50).execute()

dates = set()
for snapshot in verb_snapshots.data:
    date = snapshot['snapshot_at'][:10]
    dates.add(date)
    
print(f'Found {len(verb_snapshots.data)} total snapshots across {len(dates)} unique dates')
print('Unique dates:', sorted(dates)) 