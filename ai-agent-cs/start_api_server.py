import sys
import subprocess
import os

def run():
    print(f"🌐 Starting Luxury Hotel API Server...")
    print(f"🐍 Using Python: {sys.executable}")
    print(f"📍 URL: http://localhost:8000")
    print(f"📜 Docs: http://localhost:8000/docs")

    # Use uvicorn to run the FastAPI app
    # We use 'python -m uvicorn' to ensure it's run within the current environment
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "backend.api_server:app", 
        "--host", "0.0.0.0", 
        "--port", "8000", 
        "--reload"
    ]
    
    try:
        # Run from the 'ai-agent-cs' directory
        subprocess.run(cmd, check=True, cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\nStopping API Server...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run()
