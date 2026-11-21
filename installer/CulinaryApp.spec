# PyInstaller build specification for the self-contained Windows application.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(BACKEND / "alembic"), "backend/alembic"),
    (str(BACKEND / "alembic.ini"), "backend"),
]
binaries = []
hiddenimports = (
    collect_submodules("app")
    + collect_submodules("scripts")
)

for package in (
    "alembic",
    "camoufox",
    "human_requests",
    "playwright",
    "pyaterochka_api",
    "selectolax",
    "uvicorn",
):
    package_binaries, package_datas, package_hiddenimports = collect_all(package)
    binaries += package_binaries
    datas += package_datas
    hiddenimports += package_hiddenimports

analysis = Analysis(
    [str(BACKEND / "desktop_launcher.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="CulinaryApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="CulinaryApp",
)
