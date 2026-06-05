# AgentForge — Building .exe & Distribution Guide

This document covers packaging AgentForge into standalone executables for Windows, macOS, and Linux.

---

## Quick Build

```bash
# One-command build:
python forge.py --build-exe

# Output: dist/AgentForge.exe  (Windows)  or  dist/AgentForge  (Unix)
```

---

## Manual Build with PyInstaller

### 1. Install PyInstaller

```bash
pip install pyinstaller
```

### 2. Build Command

**Windows (.exe):**
```powershell
pyinstaller --onefile --console --name AgentForge forge.py `
  --hidden-import yaml `
  --hidden-import httpx `
  --hidden-import dotenv `
  --hidden-import flask `
  --hidden-import commands `
  --hidden-import orchestrator `
  --hidden-import pipeline `
  --hidden-import executor `
  --hidden-import matcher `
  --hidden-import classifier `
  --hidden-import api_client `
  --hidden-import tools `
  --hidden-import workspace `
  --add-data "forge.yaml;." `
  --add-data "templates;templates" `
  --add-data "static;static" `
  --clean --noconfirm
```

**macOS / Linux:**
```bash
pyinstaller --onefile --console --name AgentForge forge.py \
  --hidden-import yaml \
  --hidden-import httpx \
  --hidden-import dotenv \
  --hidden-import flask \
  --hidden-import commands \
  --hidden-import orchestrator \
  --hidden-import pipeline \
  --hidden-import executor \
  --hidden-import matcher \
  --hidden-import classifier \
  --hidden-import api_client \
  --hidden-import tools \
  --hidden-import workspace \
  --add-data "forge.yaml:." \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --clean --noconfirm
```

### 3. Output

| File | Size | Description |
|---|---|---|
| `dist/AgentForge.exe` | ~20-30 MB | Standalone Windows executable |
| `dist/AgentForge` | ~25-35 MB | Standalone Linux/macOS binary |

---

## Using PyInstaller Spec File (Advanced)

For more control, create a `.spec` file:

```python
# AgentForge.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['forge.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('forge.yaml', '.'),
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'yaml', 'httpx', 'dotenv', 'flask',
        'commands', 'orchestrator', 'pipeline', 'executor',
        'matcher', 'classifier', 'api_client', 'tools', 'workspace',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AgentForge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

Build with:
```bash
pyinstaller AgentForge.spec --clean --noconfirm
```

---

## Distribution Checklist

### Before Releasing

1. [ ] Verify all API providers work (run a quick test with each)
2. [ ] Run `/doctor` command to verify system check
3. [ ] Test GUI mode (`AgentForge.exe --gui`)
4. [ ] Test pipeline with mock mode (`AgentForge.exe --mock "test"`)
5. [ ] Update version in `forge.py` banner text
6. [ ] Update `forge.yaml` version header
7. [ ] Update `CHANGELOG.md` (if exists)
8. [ ] Commit and push all changes

### GitHub Release

1. Build the .exe (see above)
2. Create a new tag:
   ```bash
   git tag v0.5.0
   git push origin v0.5.0
   ```
3. Go to GitHub → Releases → Create New Release
4. Upload `dist/AgentForge.exe`
5. Release notes template:

```markdown
## AgentForge v0.5.0

### New Features
- Slash commands (/help, /doctor, /agents, /pipeline, ...)
- Web GUI (forge --gui)
- Test feedback loop (auto-fix failing tests)
- Git auto-commit (opt-in)
- .exe packaging support
- Enhanced error handling with retry

### Download
- **Windows**: AgentForge.exe (attached below)
- **Source**: zip / tar.gz (auto-generated)

### Quick Start
1. Download AgentForge.exe
2. Create .env file with your API keys
3. Run: AgentForge.exe "build a calculator"

### SHA256
AgentForge.exe: `...`
```

---

## Troubleshooting

### "No module named 'xxx'"

Add the missing module to `--hidden-import`:
```bash
pyinstaller ... --hidden-import missing_module
```

### .exe is too large

- Use UPX compression: `pip install upx` then add `--upx-dir <path>`
- Exclude unnecessary modules: `--exclude-module matplotlib --exclude-module numpy`

### .exe crashes on startup

Run with console to see errors:
```bash
AgentForge.exe --help
```

Check for missing data files (forge.yaml, templates/, static/ must be in the same directory as the .exe or bundled).

### False positive from antivirus

PyInstaller .exe files are sometimes flagged. Submit to your AV vendor for whitelisting, or digitally sign the .exe:
```bash
signtool sign /fd SHA256 /f certificate.pfx /p password dist/AgentForge.exe
```

---

## One-File vs One-Directory

| Mode | Flag | Pros | Cons |
|---|---|---|---|
| One-file | `--onefile` | Single .exe, clean | Slower startup (extracts to temp) |
| One-dir | `--onedir` | Fast startup | Multiple files in dist/ |

For distribution, **one-file** is recommended. For development, one-directory is faster.

---

## Cross-Platform Notes

- **Windows**: Build on Windows for native .exe
- **macOS**: Build on macOS, may need code signing for distribution
- **Linux**: Build on the target distro for compatible glibc version

GitHub Actions can automate multi-platform builds — see `.github/workflows/build.yml` for CI/CD setup.
