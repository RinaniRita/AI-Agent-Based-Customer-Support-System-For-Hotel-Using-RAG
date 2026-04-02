import subprocess
import os

def run():
    # Use absolute paths to be safe
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    venv_python = os.path.join(project_root, ".venv", "Scripts", "python.exe")
    
    if not os.path.exists(venv_python):
        # Alternative: check in current dir
        venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")

    print(f"🛰️  Starting API Server (Port 8000)...")
    print(f"🐍 Using Python: {venv_python}")

    cmd = [venv_python, "-m", "uvicorn", "backend.api_server:app", "--port", "8000", "--host", "127.0.0.1", "--reload"]
    
    try:
        subprocess.run(cmd, check=True, cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\nStopping API Server...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run()
