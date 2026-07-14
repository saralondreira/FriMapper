# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller (onedir) para o Frimapper.

Separação recursos/dados (ver frimapper/paths.py e DEVLOG #013): os recursos
(ícones, dados da diagrams, Graphviz) vão para o bundle read-only; a BD,
chave, logs e mapas vivem em %APPDATA%/Frimapper ou ~/.frimapper.

Graphviz: definir a env var GRAPHVIZ_HOME no build (pasta que contém bin/)
para empacotar o `dot`; frimapper/runtime.configure_graphviz coloca-o no PATH
em runtime. Sem GRAPHVIZ_HOME, o executável usa o Graphviz do sistema.

Build:  pyinstaller frimapper.spec
Validação:  dist/Frimapper/frimapper --selftest
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("assets/icons", "assets/icons")]
datas += collect_data_files("diagrams")  # PNGs dos ícones nativos

graphviz_home = os.environ.get("GRAPHVIZ_HOME")
if graphviz_home:
    datas.append((os.path.join(graphviz_home, "bin"), "graphviz/bin"))

hiddenimports = (
    ["passlib.handlers.argon2", "passlib.handlers.bcrypt"]
    + collect_submodules("diagrams")
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="frimapper",
    debug=False,
    strip=False,
    upx=False,
    # console=True para o --selftest ter stdout; mudar para False num
    # lançamento puramente desktop.
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Frimapper",
)
