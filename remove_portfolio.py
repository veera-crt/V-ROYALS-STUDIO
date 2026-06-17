import os

file_path = 'frontend/portfolio.html'
if os.path.exists(file_path):
    try:
        os.remove(file_path)
        print(f"✅ Successfully removed {file_path}")
    except Exception as e:
        print(f"❌ Error removing {file_path}: {e}")
else:
    print(f"ℹ️ {file_path} does not exist (already removed).")
