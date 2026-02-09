# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PDF to Long PNG Converter — a Python utility that converts multi-page PDF files into a single vertically-stacked PNG image. Supports both command-line usage and Windows GUI (drag-and-drop onto the .exe). UI messages are bilingual (Korean/English).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the converter
python pdf_to_long_png.py <input.pdf> [output.png]

# Build standalone Windows executable (output: dist/pdf_to_long_png.exe)
pyinstaller pdf_to_long_png.spec
```

There are no test or lint commands configured.

## Architecture

The entire application is a single file: `pdf_to_long_png.py` (~122 lines).

- **`pdf_to_long_png(pdf_path, output_path)`** — Core conversion function. Uses PyMuPDF (`fitz`) to render each page at 2x zoom, converts to PIL Images, then vertically concatenates them onto a white canvas.
- **`show_message(title, msg, is_error)`** — Displays Windows MessageBox (via `ctypes.windll`) in windowed mode, falls back to `print()` when a console is available. Note: this function is defined *inside* `pdf_to_long_png()` but is only called from the main execution block below it — this is a structural issue.
- **Main execution block** (lines 83–121) — Parses `sys.argv` for input/output paths, calls the conversion function, and shows success/error messages.

## Dependencies

- `pymupdf` (imported as `fitz`) — PDF rendering
- `pillow` (PIL) — Image manipulation
- `pyinstaller` — Packaging into standalone `.exe`

## Known Bugs

- **Lines 44, 50, 59**: Call `log()` which is undefined — should be `print()`. These will cause `NameError` at runtime when those code paths execute.
- **Lines 53–64**: Each page image is pasted twice and `current_y` is incremented twice, resulting in double-height output with each page duplicated.
- **Line 72**: `show_message()` is defined inside `pdf_to_long_png()` function scope but called from the module-level main block — this will cause a `NameError` since `show_message` is not accessible outside the function.

## Build Configuration

`pdf_to_long_png.spec` configures PyInstaller for:
- Single-file mode (one `.exe`)
- Windowed mode (`console=False`) — no terminal window
- UPX compression enabled
