import sys
from pathlib import Path

# Добавляем корень backend\ в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine
import app.models  # регистрирует все модели в metadata

Base.metadata.create_all(bind=engine)
print("Tables created:", ", ".join(Base.metadata.tables.keys()))
