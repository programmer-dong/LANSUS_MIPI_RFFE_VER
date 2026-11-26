# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

target = os.environ.get("LANSUS_BUILD_TARGET", "")
if target not in {"centos7", "rocky8"}:
    raise SystemExit("LANSUS_BUILD_TARGET 必须是 centos7 或 rocky8，当前为: %s" % target)

root = Path.cwd()
template = root / "templates" / "rffe_base.v"
if not template.is_file():
    raise SystemExit("缺少任务库模板: %s" % template)
a = Analysis(
    [str(root / "mipi_gui.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(template), "templates")],
    hiddenimports=["numpy", "pandas", "xlrd", "openpyxl", "sim_top_gen", "sim_flow", "gen_sim_case"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide2", "PySide6", "PyQt5", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mipi_gui",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="mipi_gui",
)
