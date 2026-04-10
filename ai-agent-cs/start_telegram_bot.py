import sys
import subprocess
import os

def run():
    print(f"🤖 Starting Telegram Bot...")
    print(f"🐍 Using Python: {sys.executable}")

    cmd = [sys.executable, "-m", "backend.bot_server"]
    
    try:
        subprocess.run(cmd, check=True, cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\nStopping Telegram Bot...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run()
