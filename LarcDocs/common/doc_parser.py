"""Extraction structurée depuis AGENTS.md."""
import os
import re


def parse_agents_md(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {'sections': [], 'tables': [], 'module_info': {}}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = _extract_sections(content)
    tables = _extract_tables(content)
    module_info = _extract_app_info(content, sections)

    return {
        'sections': sections,
        'tables': tables,
        'module_info': module_info,
    }


def _extract_sections(content: str) -> list:
    sections = []
    current_section = None
    current_content = []

    for line in content.split('\n'):
        if line.startswith('## ') and not line.startswith('### '):
            if current_section:
                sections.append({
                    'title': current_section,
                    'content': '\n'.join(current_content).strip(),
                })
            current_section = line[3:].strip()
            current_content = []
        elif line.startswith('### '):
            if current_section:
                sections.append({
                    'title': current_section,
                    'subtitle': line[4:].strip(),
                    'content': '\n'.join(current_content).strip(),
                })
            current_content = []
        else:
            current_content.append(line)

    if current_section and current_content:
        sections.append({
            'title': current_section,
            'content': '\n'.join(current_content).strip(),
        })

    return sections


def _extract_tables(content: str) -> list:
    tables = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('|') and '---' not in line:
            table_lines = [line]
            j = i + 1
            if j < len(lines) and '---' in lines[j]:
                table_lines.append(lines[j])
                j += 1
                while j < len(lines) and lines[j].startswith('|'):
                    table_lines.append(lines[j])
                    j += 1
                if len(table_lines) >= 3:
                    tables.append(table_lines)
                i = j
                continue
        i += 1
    return tables


def _extract_app_info(content: str, sections: list) -> dict:
    name_match = re.search(r'^# (.+)', content, re.MULTILINE)
    name = name_match.group(1) if name_match else ""

    for s in sections:
        if 'Architecture' in s.get('title', ''):
            return {
                'name': name,
                'description': _extract_first_paragraph(s.get('content', '')),
                'content': s.get('content', ''),
            }
    return {'name': name, 'description': '', 'content': ''}


def _extract_first_paragraph(text: str) -> str:
    for line in text.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('|') and not line.startswith('```'):
            return line
    return ""


def find_agents_md(app_name: str) -> str:
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
    candidates = [
        os.path.join(base, app_name, 'AGENTS.md'),
        os.path.join(base, app_name, 'README.md'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def gen_agents_summary(app_name: str) -> str:
    md_path = find_agents_md(app_name)
    if not md_path:
        return f"Aucun fichier AGENTS.md trouvé pour {app_name}."

    data = parse_agents_md(md_path)
    info = data['module_info']

    lines = []
    lines.append(f"## Résumé depuis {os.path.basename(md_path)}")
    lines.append("")

    if info.get('description'):
        lines.append(f"_{info['description']}_")
        lines.append("")

    lines.append("### Sections principales")
    lines.append("")
    for s in data['sections']:
        title = s.get('title', '')
        subtitle = s.get('subtitle', '')
        full_title = f"{title} > {subtitle}" if subtitle else title
        if full_title:
            lines.append(f"- **{full_title}**")

    lines.append("")

    file_sections = [s for s in data['sections'] if '|' in s.get('content', '') or 'Fichier' in s.get('content', '') or 'Rôle' in s.get('content', '')]
    if file_sections:
        lines.append("### Structure des fichiers (extrait)")
        lines.append("")
        for s in file_sections:
            for line in s['content'].split('\n')[:20]:
                if line.strip().startswith('|') and '---' not in line:
                    lines.append(line)

    return "\n".join(lines)

