import os
import sys
import uvicorn

# Add 'api' directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(BASE_DIR, "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 Starting DocMind AI — API Documentation Agent")
    print("  🌐 Dashboard: http://localhost:8000")
    print("  📚 API Docs:  http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
