import os
import subprocess
import sys
import venv

VENV_DIR = ".venv" # we use .env file for project secrets
REQUIREMENTS_FILE = "requirements.txt"

def create_venv(venv_path):
    if os.path.exists(venv_path):
        print(f"✅ Virtual environment already exists at '{venv_path}'")
    else:
        print(f"🚧 Creating virtual environment at '{venv_path}'...")
        venv.create(venv_path, with_pip=True)
        print("✅ Virtual environment created.")

def install_requirements(venv_path):
    pip_executable = os.path.join(venv_path, "bin", "pip") if os.name != "nt" else os.path.join(venv_path, "Scripts", "pip.exe")

    if not os.path.isfile(REQUIREMENTS_FILE):
        print(f"❌ No requirements.txt found in current directory.")
        sys.exit(1)

    print("📦 Installing packages from requirements.txt...")
    subprocess.check_call([pip_executable, "install", "-r", REQUIREMENTS_FILE])
    print("✅ Packages installed.")

def main():
    create_venv(VENV_DIR)
    install_requirements(VENV_DIR)

if __name__ == "__main__":
    main()

