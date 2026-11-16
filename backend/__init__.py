from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "Bd_Troc.AI"

if not DATABASE_DIR.is_dir():
    raise ModuleNotFoundError(
        f"Diretório do banco de dados não encontrado: {DATABASE_DIR}"
    )

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))