import sys
from pathlib import Path

# Delegate to the unified multi-app icon generator
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from generate_app_icons import main

if __name__ == "__main__":
    main()
