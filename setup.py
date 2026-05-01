"""Setup script: installs dependencies for the Space Engineers GPS Manager bot.

Creates a virtual environment (.venv/) and installs requirements into it.

Usage:
    python3 setup.py
"""
import subprocess
import sys
from pathlib import Path

ROOT         = Path(__file__).parent
REQUIREMENTS = ROOT / "requirements.txt"
VENV_DIR     = ROOT / ".venv"


def run(*cmd, **kwargs):
    subprocess.check_call(list(cmd), **kwargs)


def main():
    if sys.version_info < (3, 8):
        sys.exit(f"Python 3.8+ required, found {sys.version.split()[0]}")

    if not REQUIREMENTS.exists():
        sys.exit(f"Could not find {REQUIREMENTS}")

    # ── Create venv if it doesn't exist ──────────────────────────────────
    if not VENV_DIR.exists():
        print(f"Creating virtual environment at {VENV_DIR} ...")
        run(sys.executable, "-m", "venv", str(VENV_DIR))
    else:
        print(f"Virtual environment already exists at {VENV_DIR}")

    # Resolve the pip/python inside the venv
    if sys.platform == "win32":
        venv_python = VENV_DIR / "Scripts" / "python.exe"
    else:
        venv_python = VENV_DIR / "bin" / "python"

    # ── Ensure pip is available inside the venv ───────────────────────────
    # On some Linux distros the venv is created without pip; bootstrap it.
    try:
        run(str(venv_python), "-m", "pip", "--version",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("pip not found in venv, bootstrapping via ensurepip ...")
        run(str(venv_python), "-m", "ensurepip", "--upgrade")

    # ── Install / upgrade requirements ───────────────────────────────────
    print(f"Installing dependencies from {REQUIREMENTS.name} ...")
    try:
        run(str(venv_python), "-m", "pip", "install", "--upgrade", "-r", str(REQUIREMENTS))
    except subprocess.CalledProcessError as e:
        sys.exit(f"pip install failed (exit code {e.returncode})")

    # ── Token reminder ────────────────────────────────────────────────────
    token_file = ROOT / "DiscordToken.txt"
    if not token_file.exists():
        print(f"\nNote: {token_file.name} not found. "
              "Create it and paste your Discord bot token before running the bot.")

    # ── Done ──────────────────────────────────────────────────────────────
    print("\nSetup complete.")
    if sys.platform == "win32":
        print(f"Run the bot with:  {venv_python} VectorHandler.py")
    else:
        print(f"Run the bot with:  {venv_python} VectorHandler.py")
        print(f"  or activate first:  source {VENV_DIR}/bin/activate")


if __name__ == "__main__":
    main()
