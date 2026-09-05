"""HR export — fonctions d'export CSV/Excel/PDF."""
from __future__ import annotations


def export_csv(data: list[dict], columns: list[tuple[str, str]], filepath: str) -> bool:
    """Exporte une liste de dicts en CSV.
    Args:
        data: liste de dictionnaires
        columns: liste de tuples (clé, en-tête)
        filepath: chemin du fichier de sortie
    """
    import csv
    try:
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow([h for _, h in columns])
            for row in data:
                w.writerow([row.get(k, "") for k, _ in columns])
        return True
    except Exception:
        import traceback
        traceback.print_exc()
        return False
