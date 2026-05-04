#!/usr/bin/env python3
"""
build_exe.py — Builds TN_Election_2026_Monitor.exe using PyInstaller
Run this script on Windows (recommended) or Linux:
    python build_exe.py

Dependencies installed automatically:
  requests, beautifulsoup4, ttkbootstrap, matplotlib, reportlab, numpy, Pillow
"""
import subprocess
import sys
import os
import platform


def run(cmd):
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"ERROR: command failed with code {result.returncode}")
        sys.exit(result.returncode)


# ── Step 1: ensure PyInstaller is installed ──────────────────────────────────
try:
    import PyInstaller
    print(f"PyInstaller {PyInstaller.__version__} found.")
except ImportError:
    print("PyInstaller not found. Installing...")
    run([sys.executable, "-m", "pip", "install", "pyinstaller"])

# ── Step 2: install ALL runtime dependencies ─────────────────────────────────
deps = [
    "requests",
    "beautifulsoup4",
    "ttkbootstrap",
    "matplotlib",
    "reportlab",
    "numpy",
    "Pillow",
    "lxml",               # faster BS4 parser
    "charset_normalizer", # requests dependency
    "certifi",            # requests SSL certs
    "urllib3",            # requests dependency
    "pyinstaller",        # ensure pyinstaller is up to date
]
print("\n── Installing / verifying dependencies ─────────────────────────────")
for dep in deps:
    run([sys.executable, "-m", "pip", "install", dep, "--quiet", "--upgrade"])

# ── Step 3: Create version file for Windows EXE metadata ─────────────────────
version_content = '''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set to 1,0,0,0 for now - you can update as needed
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    # Contains a bitmask that specifies the valid bits 'flags'
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # OS. Should always be 0x4 for Windows applications
    OS=0x4,
    # The type of file (0x1 = application, 0x2 = DLL)
    fileType=0x1,
    # The subtype of the file (0x0 = unspecified)
    subtype=0x0,
    # Creation date and time stamp
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'TN Election Monitor'),
        StringStruct(u'FileDescription', u'Tamil Nadu Election 2026 Live Results Monitor'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'TN Election Monitor'),
        StringStruct(u'LegalCopyright', u'Open Source'),
        StringStruct(u'OriginalFilename', u'TN_Election_2026_Monitor.exe'),
        StringStruct(u'ProductName', u'TN Election 2026 Monitor'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''

with open("version.txt", "w", encoding="utf-8") as f:
    f.write(version_content)

# ── Step 4: Create spec file for better control ──────────────────────────────
script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tn_election_monitor.py")
if not os.path.exists(script):
    print(f"ERROR: tn_election_monitor.py not found at: {script}")
    print("Make sure build_exe.py and tn_election_monitor.py are in the same folder.")
    sys.exit(1)

# Determine platform-specific settings
is_windows = platform.system() == "Windows"
console_setting = "--windowed" if is_windows else "--console"  # On Linux/Mac, keep console for debugging

# Build PyInstaller command
pyinstaller_args = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",                    # single portable executable
    console_setting,                # no console window on Windows, console on Linux
    "--name", "TN_Election_2026_Monitor",
    "--clean",                      # wipe previous build cache
    "--noconfirm",                  # overwrite output directory without asking
    
    # Add version info (Windows only)
    *(["--version-file", "version.txt"] if is_windows else []),
    
    # Increase recursion limit for large packages
    "--recursion-limit", "10000",

    # ── tkinter ──────────────────────────────────────────────────────────
    "--hidden-import", "tkinter",
    "--hidden-import", "tkinter.ttk",
    "--hidden-import", "tkinter.messagebox",
    "--hidden-import", "tkinter.filedialog",
    "--hidden-import", "tkinter.font",

    # ── ttkbootstrap + themes ────────────────────────────────────────────
    "--hidden-import", "ttkbootstrap",
    "--hidden-import", "ttkbootstrap.themes",
    "--hidden-import", "ttkbootstrap.themes.standard",
    "--hidden-import", "ttkbootstrap.themes.litera",
    "--hidden-import", "ttkbootstrap.themes.darkly",
    "--hidden-import", "ttkbootstrap.themes.flatly",
    "--hidden-import", "ttkbootstrap.themes.cosmo",
    "--hidden-import", "ttkbootstrap.style",
    "--hidden-import", "ttkbootstrap.widgets",
    "--hidden-import", "ttkbootstrap.constants",
    "--collect-all",   "ttkbootstrap",   # pulls in theme JSON/PNG assets
    "--collect-data",  "ttkbootstrap",   # alternative method to collect data files

    # ── Pillow (image handling) ─────────────────────────────────────────
    "--hidden-import", "PIL",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageTk",
    "--hidden-import", "PIL.ImageDraw",
    "--hidden-import", "PIL.ImageFile",
    "--hidden-import", "PIL._tkinter_finder",
    "--collect-all",   "PIL",
    "--collect-data",  "PIL",

    # ── BeautifulSoup + parsers ──────────────────────────────────────────
    "--hidden-import", "bs4",
    "--hidden-import", "bs4.builder",
    "--hidden-import", "bs4.builder._htmlparser",
    "--hidden-import", "bs4.builder._lxml",
    "--hidden-import", "html.parser",
    "--hidden-import", "lxml",
    "--hidden-import", "lxml.etree",
    "--hidden-import", "lxml.html",

    # ── requests + networking ────────────────────────────────────────────
    "--hidden-import", "requests",
    "--hidden-import", "requests.adapters",
    "--hidden-import", "requests.auth",
    "--hidden-import", "requests.cookies",
    "--hidden-import", "requests.exceptions",
    "--hidden-import", "requests.models",
    "--hidden-import", "requests.sessions",
    "--hidden-import", "requests.status_codes",
    "--hidden-import", "requests.utils",
    "--hidden-import", "urllib3",
    "--hidden-import", "urllib3.connection",
    "--hidden-import", "urllib3.connectionpool",
    "--hidden-import", "urllib3.poolmanager",
    "--hidden-import", "urllib3.util",
    "--hidden-import", "urllib3.util.retry",
    "--hidden-import", "urllib3.util.timeout",
    "--hidden-import", "urllib3.util.url",
    "--hidden-import", "certifi",
    "--hidden-import", "charset_normalizer",
    "--hidden-import", "charset_normalizer.md__mypyc",
    "--collect-all", "certifi",
    "--datas", os.path.join(sys.prefix, "Lib", "site-packages", "certifi", "cacert.pem"),

    # ── matplotlib (charts) ───────────────────────────────────────────────
    "--hidden-import", "matplotlib",
    "--hidden-import", "matplotlib.backends",
    "--hidden-import", "matplotlib.backends.backend_tkagg",
    "--hidden-import", "matplotlib.backends.backend_pdf",
    "--hidden-import", "matplotlib.backends._backend_tk",
    "--hidden-import", "matplotlib.figure",
    "--hidden-import", "matplotlib.patches",
    "--hidden-import", "matplotlib.gridspec",
    "--hidden-import", "matplotlib.pyplot",
    "--hidden-import", "matplotlib.font_manager",
    "--hidden-import", "matplotlib.rcsetup",
    "--collect-all",   "matplotlib",
    "--collect-data",  "matplotlib",

    # ── numpy (used by matplotlib) ────────────────────────────────────────
    "--hidden-import", "numpy",
    "--hidden-import", "numpy.core",
    "--hidden-import", "numpy.core._multiarray_umath",
    "--hidden-import", "numpy.core.overrides",
    "--hidden-import", "numpy.linalg",
    "--hidden-import", "numpy.linalg.lapack_lite",
    "--hidden-import", "numpy.random",
    "--collect-all",   "numpy",

    # ── reportlab (PDF export) ────────────────────────────────────────────
    "--hidden-import", "reportlab",
    "--hidden-import", "reportlab.lib",
    "--hidden-import", "reportlab.lib.pagesizes",
    "--hidden-import", "reportlab.lib.colors",
    "--hidden-import", "reportlab.lib.units",
    "--hidden-import", "reportlab.lib.styles",
    "--hidden-import", "reportlab.lib.enums",
    "--hidden-import", "reportlab.lib.utils",
    "--hidden-import", "reportlab.platypus",
    "--hidden-import", "reportlab.platypus.tables",
    "--hidden-import", "reportlab.platypus.paragraph",
    "--hidden-import", "reportlab.pdfgen",
    "--hidden-import", "reportlab.pdfgen.canvas",
    "--hidden-import", "reportlab.pdfbase",
    "--hidden-import", "reportlab.pdfbase.ttfonts",
    "--hidden-import", "reportlab.pdfbase.pdfmetrics",
    "--collect-all",   "reportlab",
    "--collect-data",  "reportlab",

    # ── Additional required modules ───────────────────────────────────────
    "--hidden-import", "concurrent",
    "--hidden-import", "concurrent.futures",
    "--hidden-import", "threading",
    "--hidden-import", "re",
    "--hidden-import", "io",
    "--hidden-import", "math",
    "--hidden-import", "sqlite3",
    "--hidden-import", "hashlib",
    "--hidden-import", "datetime",
    "--hidden-import", "collections",
    "--hidden-import", "copyreg",
    
    # ── Additional binary dependencies ────────────────────────────────────
    "--collect-submodules", "numpy",
    "--collect-submodules", "matplotlib",
    "--collect-submodules", "PIL",

    script,
]

print("\n── Running PyInstaller ──────────────────────────────────────────────")
print(f"Platform: {platform.system()}")
print(f"Python: {sys.version}")
print(f"Script: {script}")
print(f"Output will be in 'dist' folder")

run(pyinstaller_args)

# ── Step 5: Clean up temporary files ────────────────────────────────────────
if os.path.exists("version.txt"):
    os.remove("version.txt")
if os.path.exists("tn_election_monitor.spec"):
    # Keep the spec file for future builds - it's useful for customization
    print("\nSpec file 'tn_election_monitor.spec' generated for future builds")

# ── Step 6: Display build results ───────────────────────────────────────────
print("\n" + "=" * 70)
print("  BUILD COMPLETE!")
print("=" * 70)

dist_exe = os.path.join("dist", "TN_Election_2026_Monitor.exe")
dist_bin = os.path.join("dist", "TN_Election_2026_Monitor")
dist_app = os.path.join("dist", "TN_Election_2026_Monitor.app")  # macOS

if os.path.exists(dist_exe):
    size_mb = os.path.getsize(dist_exe) / 1_048_576
    print(f"\n  ✅ Windows EXE created successfully!")
    print(f"     Location: {dist_exe}")
    print(f"     Size: {size_mb:.1f} MB")
    print(f"\n  To run: Double-click the EXE file")
    
elif os.path.exists(dist_bin) and not is_windows:
    size_mb = os.path.getsize(dist_bin) / 1_048_576
    print(f"\n  ✅ Linux binary created successfully!")
    print(f"     Location: {dist_bin}")
    print(f"     Size: {size_mb:.1f} MB")
    print(f"\n  To run: ./TN_Election_2026_Monitor")
    
elif os.path.exists(dist_app):
    size_mb = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                  for dirpath, dirnames, filenames in os.walk(dist_app) 
                  for filename in filenames) / 1_048_576
    print(f"\n  ✅ macOS app bundle created successfully!")
    print(f"     Location: {dist_app}")
    print(f"     Size: {size_mb:.1f} MB")
    
else:
    print(f"\n  ⚠ Output file not found in 'dist' folder")
    print("  Check the PyInstaller output above for errors")

print("\n" + "=" * 70)
print("  ADDITIONAL NOTES:")
print("  • First run may be slow (extracting embedded files)")
print("  • Database file (tn_election_photos.db) will be created in the same folder")
print("  • Requires internet connection for live election data")
print("  • Windows Defender may flag the EXE - this is normal for PyInstaller builds")
print("=" * 70)