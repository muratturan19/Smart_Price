import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "Price App"))
sys.path.insert(0, str(root / "Sales App"))
