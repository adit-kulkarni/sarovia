#!/usr/bin/env python3

import sys
import asyncio
import logging
from server import get_verb_progress_timeline

# Set up logging
logging.basicConfig(level=logging.INFO)

async def test_endpoint():
    try:
        result = await get_verb_progress_timeline(
            language='es',
            curriculum_id='f8bcfebc-ddc8-4bd4-bd6e-49b0f04f08eb',
            limit=5,
            token='eyJhbGciOiJIUzI1NiIsImtpZCI6IlJhYStOWlZlK1FJZ0pYVzEiLCJ0eXAiOiJKV1QifQ.eyJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzM0MDM5NzEzLCJpYXQiOjE3MzQwMzYxMTMsImlzcyI6Imh0dHBzOi8vdG9ibm14YXl0c2tudWJkcHpwbmYuc3VwYWJhc2UuY28vYXV0aC92MSIsInN1YiI6IjExOWM2MThjLTBlMWMtNDk4NC05NGFkLTBlMTVmNzBiN2MzMSIsImVtYWlsIjoiYWRpdC50dWRAZ21haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6e30sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3MzM5NjI1Njd9XSwic2Vzc2lvbl9pZCI6IjY3MDRkM2FmLTAzN2ItNDEyOC1hMjU0LThjNjNmYzIzZTc1YyIsImlzX2Fub255bW91cyI6ZmFsc2V9.oj-W4H_HYPCWt4KNyLuQ_-H5ZxE6oWlUVP5yd8K-iRA'
        )
        print('SUCCESS:', result)
    except Exception as e:
        print('ERROR:', str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_endpoint()) 