"""Fonctions partagees pour la gestion des evaluations."""
from .database import db


def save_evaluation_criteria(eval_id: int, label: str, nature: str, source: str,
                              crits: dict) -> bool:
    """Sauvegarde les criteres d'une evaluation dans SQLite.

    Args:
        eval_id: id de l'evaluation
        label: label existant (non modifie par le formulaire)
        nature: nature de l'evaluation (ex: Devoir, Interro...)
        source: texte markdown source
        crits: dict avec les cles crit_a..crit_d, valeurs '1' ou '0'
    """
    conn = db.local_conn
    if conn is None:
        return False
    try:
        conn.execute(
            """UPDATE larcauth_evaluation
               SET label=?, nature=?, source=?,
                   crit_a=?, crit_b=?, crit_c=?, crit_d=?
               WHERE id=?""",
            (label,
             nature,
             source,
             crits.get('crit_a', '0'),
             crits.get('crit_b', '0'),
             crits.get('crit_c', '0'),
             crits.get('crit_d', '0'),
             eval_id),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur sauvegarde evaluation {eval_id}: {e}")
        return False
