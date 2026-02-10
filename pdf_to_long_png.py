import sys
import os
import json
import ctypes
import textwrap
import fitz  # pymupdf
from PIL import Image, ImageDraw, ImageFont


# --- Font paths ---
# Malgun Gothic for Korean, Microsoft YaHei for Chinese fallback
FONT_KO_PATH = "C:/Windows/Fonts/malgun.ttf"
FONT_KO_BOLD_PATH = "C:/Windows/Fonts/malgunbd.ttf"
FONT_CJK_PATH = "C:/Windows/Fonts/msyh.ttc"
FONT_CJK_BOLD_PATH = "C:/Windows/Fonts/msyhbd.ttc"


def is_cjk_char(ch):
    """Returns True if the character is in CJK Unified Ideographs ranges."""
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF or      # CJK Unified Ideographs
        0x3400 <= cp <= 0x4DBF or      # CJK Extension A
        0x20000 <= cp <= 0x2A6DF or    # CJK Extension B
        0xF900 <= cp <= 0xFAFF or      # CJK Compatibility Ideographs
        0x2F800 <= cp <= 0x2FA1F       # CJK Compatibility Supplement
    )


def pdf_to_long_png(pdf_path, output_path):
    """
    Converts a PDF into a single long PNG image.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF file: {e}")
        return

    if doc.page_count == 0:
        print("The PDF has no pages.")
        return

    print(f"PDF opened: {pdf_path} ({doc.page_count} pages)")

    images = []
    total_height = 0
    max_width = 0

    # Zoom factor for better quality (2.0 = 200% resolution)
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)

    for i in range(doc.page_count):
        print(f"Processing page {i + 1}/{doc.page_count}...")
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

        total_height += img.height
        if img.width > max_width:
            max_width = img.width

    print(f"Creating output image ({max_width}x{total_height})...")

    # Create the long image
    try:
        long_image = Image.new("RGB", (max_width, total_height), (255, 255, 255))
    except Exception as e:
        print(f"Error creating new image: {e}")
        raise e

    current_y = 0
    for i, img in enumerate(images):
        try:
            long_image.paste(img, (0, current_y))
            current_y += img.height
        except Exception as e:
            print(f"Error pasting page {i}: {e}")
            raise e

    try:
        long_image.save(output_path)
        print(f"Successfully saved to: {output_path}")
    except Exception as e:
        print(f"Error saving image: {e}")


def _draw_text_with_fallback(draw, x, y, text, font_ko, font_cjk, fill):
    """Draw text character by character, using font_cjk for CJK ideographs, font_ko otherwise."""
    cursor_x = x
    for ch in text:
        font = font_cjk if is_cjk_char(ch) else font_ko
        draw.text((cursor_x, y), ch, fill=fill, font=font)
        cursor_x += font.getlength(ch)


def _measure_text_width(text, font_ko, font_cjk):
    """Measure text width using appropriate font per character."""
    width = 0
    for ch in text:
        font = font_cjk if is_cjk_char(ch) else font_ko
        width += font.getlength(ch)
    return width


def _wrap_text_pixel(text, max_width, font_ko, font_cjk):
    """Wrap text based on actual pixel width using mixed fonts."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current_line = ""
        current_width = 0
        for ch in paragraph:
            font = font_cjk if is_cjk_char(ch) else font_ko
            ch_width = font.getlength(ch)
            if current_width + ch_width > max_width and current_line:
                lines.append(current_line)
                current_line = ch
                current_width = ch_width
            else:
                current_line += ch
                current_width += ch_width
        if current_line:
            lines.append(current_line)
    return lines


def mvle_to_long_png(mvle_path, output_path):
    """
    Converts a .mvle JSON file into a single long PNG image.
    """
    with open(mvle_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    blocks = data.get("blocks", [])
    if not blocks:
        print("No blocks found in .mvle file.")
        return

    title = data.get("title", "")
    novel_title = data.get("novel", {}).get("title", "")
    print(f"MVLE opened: {mvle_path} ({len(blocks)} blocks, novel: {novel_title}, episode: {title})")

    # --- Rendering settings (2x supersampling for crisp Korean glyphs) ---
    scale = 2
    img_width = 1200 * scale
    padding_left = 60 * scale
    padding_right = 60 * scale
    padding_top = 80 * scale
    text_width = img_width - padding_left - padding_right
    font_size = 28 * scale
    line_spacing = 16 * scale
    block_spacing = 32 * scale

    try:
        font_ko = ImageFont.truetype(FONT_KO_PATH, font_size)
        font_ko_bold = ImageFont.truetype(FONT_KO_BOLD_PATH, font_size)
        font_cjk = ImageFont.truetype(FONT_CJK_PATH, font_size)
        font_cjk_bold = ImageFont.truetype(FONT_CJK_BOLD_PATH, font_size)
    except Exception as e:
        print(f"Error loading fonts: {e}")
        return

    # --- First pass: calculate total height ---
    print("Calculating layout...")
    line_height = font_size + line_spacing
    current_y = padding_top

    layout = []  # list of (y, lines, is_bold)

    for block in blocks:
        text = block.get("text", "")
        if not text.strip():
            current_y += block_spacing
            continue

        content = block.get("content", [])
        has_bold = any(
            "strong" in [m.get("type") for m in seg.get("marks", [])]
            for seg in content
        )

        fk = font_ko_bold if has_bold else font_ko
        fc = font_cjk_bold if has_bold else font_cjk
        wrapped_lines = _wrap_text_pixel(text, text_width, fk, fc)

        block_height = len(wrapped_lines) * line_height
        layout.append((current_y, wrapped_lines, has_bold))
        current_y += block_height + block_spacing

    total_height = current_y + padding_top

    print(f"Creating output image ({img_width}x{total_height})...")

    # --- Second pass: render ---
    image = Image.new("RGB", (img_width, total_height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    fill = (30, 30, 30)

    for y, lines, is_bold in layout:
        fk = font_ko_bold if is_bold else font_ko
        fc = font_cjk_bold if is_bold else font_cjk
        for line in lines:
            _draw_text_with_fallback(draw, padding_left, y, line, fk, fc, fill)
            y += line_height

    # Downscale to original 1200px width for final output
    final_width = img_width // scale
    final_height = total_height // scale
    image = image.resize((final_width, final_height), Image.LANCZOS)

    try:
        image.save(output_path)
        print(f"Successfully saved to: {output_path}")
    except Exception as e:
        print(f"Error saving image: {e}")


def show_message(title, msg, is_error=False):
    """Displays a message box if no console is available, otherwise prints to stdout."""
    if not sys.stdout or not sys.stdin:
        icon = 0x10 if is_error else 0x40
        ctypes.windll.user32.MessageBoxW(0, msg, title, icon)
    else:
        if is_error:
            print(f"[ERROR] {msg}")
        else:
            print(msg)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        msg = (
            "사용법: PDF 또는 .mvle 파일을 드래그 앤 드롭 하세요.\n\n"
            "Usage: Drag and drop a PDF or .mvle file onto this executable."
        )
        show_message("Document to Long PNG", msg)
        sys.exit(0)

    input_file = sys.argv[1]
    ext = os.path.splitext(input_file)[1].lower()

    if len(sys.argv) >= 3:
        output_png = sys.argv[2]
    else:
        base_name = os.path.splitext(input_file)[0]
        output_png = f"{base_name}_long.png"

    try:
        if ext == ".mvle":
            mvle_to_long_png(input_file, output_png)
        elif ext == ".pdf":
            pdf_to_long_png(input_file, output_png)
        else:
            show_message("오류/Error", f"지원하지 않는 파일 형식입니다: {ext}\nSupported: .pdf, .mvle", is_error=True)
            sys.exit(1)

        if os.path.exists(output_png):
            show_message("성공/Success", f"변환이 완료되었습니다!\nFile saved: {output_png}")
        else:
            show_message("오류/Error", "파일 변환에 실패했습니다.", is_error=True)
    except Exception as e:
        show_message("오류/Error", f"예기치 않은 오류가 발생했습니다:\n{e}", is_error=True)
