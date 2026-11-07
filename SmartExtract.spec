# Resep PyInstaller. Bangun lewat build_exe.bat; hasilnya dist\SmartExtract.exe.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from smartextract import __app_name__, __author__, __copyright__, __version__

parts = tuple(int(part) for part in __version__.split(".")) + (0,)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=parts, prodvers=parts),
    kids=[
        StringFileInfo([
            StringTable("040904B0", [
                StringStruct("CompanyName", __author__),
                StringStruct("FileDescription", __app_name__),
                StringStruct("FileVersion", __version__),
                StringStruct("InternalName", __app_name__),
                StringStruct("LegalCopyright", __copyright__),
                StringStruct("OriginalFilename", f"{__app_name__}.exe"),
                StringStruct("ProductName", __app_name__),
                StringStruct("ProductVersion", __version__),
            ]),
        ]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    # PyMuPDF belum punya hook PyInstaller, jadi pustakanya dikumpulkan di sini.
    binaries=collect_dynamic_libs("pymupdf"),
    datas=[
        (str(root / "smartextract/assets/icon.ico"), "smartextract/assets"),
        (str(root / "LICENSE.txt"), "legal"),
        (str(root / "THIRD_PARTY_NOTICES.txt"), "legal"),
    ],
    hiddenimports=collect_submodules("pymupdf", filter=lambda name: ".layout" not in name),
    excludes=["cv2", "IPython", "matplotlib", "onnxruntime", "pandas", "pytest", "rapidocr_onnxruntime", "scipy"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=__app_name__,
    console=False,
    upx=False,                  # UPX sering memicu peringatan antivirus
    icon=str(root / "smartextract/assets/icon.ico"),
    version=version_info,
)
