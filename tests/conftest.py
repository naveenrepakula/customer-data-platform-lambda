import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LAMBDA_PATH = ROOT / "lambda" / "validation"
if str(LAMBDA_PATH) not in sys.path:
    sys.path.insert(0, str(LAMBDA_PATH))
