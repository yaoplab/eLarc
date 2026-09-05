"""Extraction d'informations depuis le code source Python."""
import ast
import os


def parse_python_file(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    rel_path = os.path.basename(filepath)

    classes = []
    functions = []
    imports = []
    module_doc = ast.get_docstring(tree) or ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)

        if isinstance(node, ast.ClassDef):
            classes.append({
                'name': node.name,
                'doc': ast.get_docstring(node) or "",
                'methods': [
                    {
                        'name': m.name,
                        'doc': ast.get_docstring(m) or "",
                        'args': _format_args(m),
                    }
                    for m in node.body if isinstance(m, ast.FunctionDef)
                ],
            })

        if isinstance(node, ast.FunctionDef) and not _is_method(node, tree):
            functions.append({
                'name': node.name,
                'doc': ast.get_docstring(node) or "",
                'args': _format_args(node),
            })

    return {
        'file': rel_path,
        'doc': module_doc,
        'classes': classes,
        'functions': functions,
        'imports': sorted(set(imports)),
    }


def parse_directory(dirpath: str) -> list:
    results = []
    for root, dirs, files in os.walk(dirpath):
        for f in sorted(files):
            if f.endswith('.py') and not f.startswith('__'):
                filepath = os.path.join(root, f)
                try:
                    results.append(parse_python_file(filepath))
                except Exception:
                    pass
    return results


def _format_args(node: ast.FunctionDef) -> str:
    args = []
    for a in node.args.args:
        name = a.arg
        if name == 'self':
            continue
        args.append(name)
    for a in node.args.posonlyargs:
        args.append(a.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    for a in node.args.kwonlyargs:
        args.append(a.arg)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return ", ".join(args)


def _is_method(node: ast.FunctionDef, tree: ast.Module) -> bool:
    for parent in ast.walk(tree):
        if isinstance(parent, ast.ClassDef):
            for child in ast.walk(parent):
                if child is node:
                    return True
    return False


def gen_summary_from_code(dirpath: str) -> str:
    files = parse_directory(dirpath)
    if not files:
        return "Aucun fichier source trouvé."

    lines = []
    lines.append(f"## Analyse du code source — {os.path.basename(dirpath)}")
    lines.append(f"")
    lines.append(f"**{len(files)} fichiers** analysés.")
    lines.append("")

    total_classes = sum(len(f['classes']) for f in files)
    total_funcs = sum(len(f['functions']) for f in files)
    lines.append(f"- {total_classes} classes")
    lines.append(f"- {total_funcs} fonctions libres")
    lines.append("")

    lines.append("### Fichiers")
    lines.append("")
    lines.append("| Fichier | Classes | Fonctions | Doc |")
    lines.append("|---------|---------|-----------|-----|")
    for f in files:
        has_doc = "oui" if f['doc'] else "non"
        lines.append(f"| `{f['file']}` | {len(f['classes'])} | {len(f['functions'])} | {has_doc} |")

    lines.append("")
    lines.append("### Classes principales")
    lines.append("")
    for f in files:
        for cls in f['classes']:
            doc_preview = cls['doc'].split('\n')[0][:80] if cls['doc'] else "—"
            n_methods = len(cls['methods'])
            lines.append(f"#### `{cls['name']}` ({f['file']})")
            lines.append(f"_{doc_preview}_")
            lines.append(f"- {n_methods} méthodes")
            if cls['methods']:
                for m in cls['methods'][:10]:
                    args_str = f"({m['args']})" if m['args'] else "()"
                    lines.append(f"  - `{m['name']}{args_str}`")
                if len(cls['methods']) > 10:
                    lines.append(f"  - ... +{len(cls['methods']) - 10} méthodes")
            lines.append("")

    lines.append("### Fonctions libres")
    lines.append("")
    for f in files:
        for func in f['functions']:
            args_str = f"({func['args']})" if func['args'] else "()"
            doc_preview = func['doc'].split('\n')[0][:80] if func['doc'] else "—"
            lines.append(f"- **`{func['name']}{args_str}`** ({f['file']}) — {doc_preview}")

    lines.append("")
    lines.append("### Dépendances (imports)")
    lines.append("")
    all_imports = sorted(set(i for f in files for i in f['imports']))
    external = [i for i in all_imports if not i.startswith(('LarcSuperviseur', 'larccommon', 'phibuilder', 'LarcCommon'))]
    internal = [i for i in all_imports if i.startswith(('LarcSuperviseur', 'larccommon', 'phibuilder', 'LarcCommon'))]
    lines.append("**Internes** : " + ", ".join(f"`{i}`" for i in sorted(internal)[:30]))
    lines.append("")
    lines.append("**Externes** : " + ", ".join(f"`{i}`" for i in sorted(external)))

    return "\n".join(lines)

