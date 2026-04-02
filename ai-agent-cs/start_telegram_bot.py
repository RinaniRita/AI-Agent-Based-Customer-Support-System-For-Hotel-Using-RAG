import subprocess
import os

def run():
    # Use absolute paths to be safe
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    venv_python = os.path.join(project_root, ".venv", "Scripts", "python.exe")
    
    if not os.path.exists(venv_python):
        # Alternative: check in current dir
        venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")

    print(f"🤖 Starting Telegram Bot...")
    print(f"🐍 Using Python: {venv_python}")

    cmd = [venv_python, "-m", "backend.bot_server"]
    
    try:
        subprocess.run(cmd, check=True, cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\nStopping Telegram Bot...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run()
