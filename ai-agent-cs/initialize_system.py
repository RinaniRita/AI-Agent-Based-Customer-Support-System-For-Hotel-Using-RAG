import os
import subprocess
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("setup_system")

def run_command(command, description):
    """Utility to run a command and log its output."""
    logger.info("--- " + description + " ---")
    try:
        # Use sys.executable to ensure we use the same python interpreter
        full_command = [sys.executable, "-m"] + command
        result = subprocess.run(full_command, capture_output=True, text=True, check=True)
        print(result.stdout)
        logger.info(f"[SUCCESS] {description} completed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"[FAILURE] {description} failed.")
        print(e.stderr)
        sys.exit(1)

def main():
    # 1. Check for .env file
    if not os.path.exists(".env"):
        logger.warning("No .env file found. Please copy .env.example to .env and fill in your keys.")
    
    # 2. Initialize and Seed Database
    run_command(["backend.database.setup_db"], "Initializing and Seeding SQLite Database")

    # 3. Ingest Knowledge Base
    run_command(["backend.data_scripts.ingest_kb"], "Ingesting Knowledge Base (FAISS Indexing)")

    logger.info("System initialization complete.")
    print("\nYou can now start the bot using: python start_telegram_bot.py")

if __name__ == "__main__":
    # Ensure current directory is always the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Ensure this directory is in path for module lookups (backend, etc.)
    if script_dir not in sys.path:
        sys.path.append(script_dir)
        
    main()
