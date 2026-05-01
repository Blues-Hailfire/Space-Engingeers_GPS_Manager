"""Setup script: installs dependencies for the Space Engineers GPS Manager bot.

Usage:
    python setup.py
"""
import subprocess
import sys
from pathlib import Path

REQUIREMENTS = Path(__file__).parent / "requirements.txt"


def main():
    if sys.version_info < (3, 8):
        sys.exit(f"Python 3.8+ required, found {sys.version.split()[0]}")

    if not REQUIREMENTS.exists():
        sys.exit(f"Could not find {REQUIREMENTS}")

    print(f"Installing dependencies from {REQUIREMENTS.name}...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--upgrade", "-r", str(REQUIREMENTS),
        ])
    except subprocess.CalledProcessError as e:
        sys.exit(f"pip install failed (exit code {e.returncode})")

    token_file = Path(__file__).parent / "DiscordToken.txt"
    if not token_file.exists():
        print(f"\nNote: {token_file.name} not found. "
              "Create it and paste your Discord bot token before running VectorHandler.py.")

    print("\nSetup complete. Run the bot with: python VectorHandler.py")


if __name__ == "__main__":
    main()
