from pathlib import Path
src=Path(SPECPATH)
a=Analysis([str(src/'launcher.py')],pathex=[str(src)],binaries=[],datas=[(str(src/'catalog.json'),'.')],hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
cli=EXE(pyz,a.scripts,[],exclude_binaries=True,name='CSL-DD-No-Rim',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=True)
gui=EXE(pyz,a.scripts,[],exclude_binaries=True,name='CSL-DD-No-Rim-Setup',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(cli,gui,a.binaries,a.datas,strip=False,upx=False,name='CSL-DD-No-Rim-Setup-Portable')
