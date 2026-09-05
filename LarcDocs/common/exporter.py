"""Export de documents générés."""
import os
import tempfile
import webbrowser
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def export_markdown(content: str, filepath: str):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def export_html(content: str, filepath: str):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def export_pdf_from_html(content: str, filepath: str):
    import re
    html_with_head = content
    if '<!DOCTYPE html>' not in content and '<html>' not in content:
        html_with_head = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Document</title></head>
<body>{content}</body>
</html>"""

    year = os.popen('echo %DATE%').read().strip().split('/')[-1] if os.name == 'nt' else '2026'
    html_with_head = html_with_head.replace('{{year}}', year)

    import markdown
    if not content.strip().startswith('<'):
        html_body = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        html_with_head = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Document</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; line-height: 1.6; }}
h1 {{ color: #1565C0; }} h2 {{ color: #1E88E5; }}
table {{ border-collapse: collapse; width: 100%; }} td, th {{ border: 1px solid #ddd; padding: 8px; }}
th {{ background: #1565C0; color: white; }}
</style></head>
<body>{html_body}</body>
</html>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_with_head)
        tmp_path = f.name

    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(tmp_path)))


def copy_to_clipboard(content: str):
    from PySide6.QtWidgets import QApplication
    QApplication.clipboard().setText(content)


def check_latex_available() -> bool:
    import shutil
    return shutil.which('pdflatex') is not None


def export_latex(content: str, filepath: str):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def compile_latex(tex_path: str) -> bool:
    import subprocess, os
    tex_dir = os.path.dirname(tex_path) or '.'
    tex_name = os.path.basename(tex_path)
    try:
        subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', tex_dir, tex_name],
            cwd=tex_dir, capture_output=True, timeout=60, check=True
        )
        subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', tex_dir, tex_name],
            cwd=tex_dir, capture_output=True, timeout=60, check=True
        )
        return True
    except Exception:
        return False

