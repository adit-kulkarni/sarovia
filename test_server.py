try:
    import server
    print('✓ Server imports successfully')
except Exception as e:
    print(f'✗ Import error: {e}')
    import traceback
    traceback.print_exc() 