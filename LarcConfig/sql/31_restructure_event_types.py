"""Restructure larcauth_event_type_config : nouvel arbre + IDs hiérarchiques.

ID = [langue][niv1][niv2][niv3][niv4]  (langue : 2 = FR, 1 = EN), un chiffre par niveau,
9 fils maximum par parent. Un nœud X couvre la plage [X, X + 10^k[ (k = 3, 2, 1, 0
selon son niveau) : toute sa branche se lit par plage d'IDs, sans jointure.

Principe gabarit : aucune ligne n'est créée ni supprimée. Les lignes existantes sont
réutilisées (libellé/parent/actif/ID modifiés) ; celles qui sortent de l'arbre
deviennent des slots libres inactifs (Categorie_Niv<ID parent>_Level_<rang>) rangés sous
les nœuds actifs.
Les deux langues sont appariées par `code` (UNIQUE (code, fk_language)) et suivent le
même arbre. Les libellés EN sont pour l'instant identiques aux libellés FR.

Usage :  python 31_restructure_event_types.py            # essai annulé + export CSV
         python 31_restructure_event_types.py --apply    # applique (Intranet)
"""
import csv
import re
import sys
import unicodedata

N = None
# (libellé, catégorie, ligne FR réutilisée, enfants)
SPEC = [
    ("Absent de l'école", "absence", 4, [
        ("Justifiée", "absence", N, []),
        ("Justifiée (sans détail)", "absence", 7, []),
        ("Injustifiée", "absence", 8, [])]),
    ("Absent du cours", "absence", 5, [
        ("Justifiée", "absence", N, []),
        ("Justifiée (sans détail)", "absence", 10, []),
        ("Injustifiée", "absence", 11, [])]),
    ("Retard à l'école", "retard", 61, [
        ("5 min", "retard", 12, []),
        ("10 min", "retard", N, []),
        ("15 min", "retard", 13, []),
        ("20 min et +", "retard", 14, [])]),
    ("Retard au cours", "retard", 62, [
        ("5 min", "retard", 75, []),
        ("10 min et +", "retard", 76, [])]),
    ("Événement", "evenement", 3, [
        ("Positif", "evenement", 85, [
            ("Mérite/Encouragement", "evenement", 87, []),
            ("Autre", "evenement", 86, [])]),
        ("Mauvais comportement", "evenement", 88, [        # ex-« Négatif », ses fils sont conservés
            ("Élève trop agité", "evenement", N, []),
            ("Manque de respect", "evenement", N, []),
            ("Violence physique", "evenement", 90, []),
            ("Violence verbale", "evenement", 93, []),
            ("Moquerie", "evenement", N, []),
            ("Harcèlement", "evenement", N, []),
            ("Autre", "evenement", 94, [])]),
        ("Manque de travail", "evenement", 98, [
            ("Plagiat", "evenement", N, []),
            ("Devoirs non faits", "evenement", 99, []),
            ("Bavardage", "evenement", N, []),
            ("Élève distrait", "evenement", N, []),
            ("Élève dort", "evenement", N, []),
            ("Autre", "evenement", 100, [])]),
        ("Matériel oublié (l'élève continue de travailler)", "evenement", 97, [])]),
    ("Sortie du cours", "sortie", 40, [
        ("Toilettes", "sortie", 41, []),
        ("Autre", "sortie", 42, []),
        ("Convocation vie scolaire", "sortie", 43, []),
        ("Infirmerie", "sortie", 44, [])]),
    ("Sortie de l'école", "sortie", 55, [
        ("Justifiée", "sortie", N, []),
        ("Justifiée (sans détail)", "sortie", N, []),
        ("Injustifiée", "sortie", N, [])]),
]
CUSTOM_ROOT_ROWS = (212, 214)      # slots libres racine : 28000 et 29000 (FR)
# Événements dont le type disparaît : (ancienne ligne FR) -> chemin du nouveau type
RECLASS = {
    20: ("Absent de l'école", "Justifiée"),                       # Maladie > Chronique
    36: ("Absent du cours", "Justifiée"),                         # Activité scolaire
    84: ("Retard au cours", "10 min et +"),                       # 15 min et + > Transport
    89: ("Événement", "Mauvais comportement", "Autre"),           # Négatif > Dégradation matériel
    # Anciens « Sortie > Mauvais comportement > … » : le comportement devient un événement
    # de l'arbre Événement, et la sortie est portée par la case student_event.sortie.
    48: ("Événement", "Mauvais comportement", "Autre"),               # Dégradation matériel
    49: ("Événement", "Mauvais comportement", "Violence physique"),
    50: ("Événement", "Mauvais comportement", "Manque de respect"),   # Insolence
}
SORTIE_FLAG_ROWS = (48, 49, 50)    # leurs événements reçoivent sortie = TRUE
FR, EN = 2, 1
MAX_CHILDREN = 9


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def build_plan(cur):
    """Calcule, sans rien écrire, l'état cible de chacune des lignes des 2 langues."""
    cur.execute("select id, code, label, parent_id, is_active, category, fk_language "
                "from larcauth_event_type_config")
    rows = cur.fetchall()
    by_id = {r[0]: r for r in rows}
    en_of = {}                                  # id FR -> id EN (même code)
    for r in rows:
        if r[6] == EN:
            for f in rows:
                if f[6] == FR and f[1] == r[1]:
                    en_of[f[0]] = r[0]
    fr_ids = sorted(r[0] for r in rows if r[6] == FR)
    used = set(CUSTOM_ROOT_ROWS)

    # 1. Nœuds actifs : ligne réutilisée ou slot libre pur
    for _l, _c, rid, _k in _iter_spec(SPEC):
        if rid:
            used.add(rid)
    pure_slots = [i for i in fr_ids if i not in used and by_id[i][1].startswith("type_niv")]
    nodes = []                                  # dicts, ordre = parcours en profondeur

    def make(spec, parent, level, prefix):
        for idx, (label, cat, rid, kids) in enumerate(spec, 1):
            if rid is None:
                rid = pure_slots.pop(0)
                used.add(rid)
            node = {"fr": rid, "label": label, "cat": cat, "level": level, "parent": parent,
                    "digits": prefix + [idx], "children": [], "active": True, "kind": "node",
                    "path": (parent["path"] if parent else ()) + (label,)}
            if parent:
                parent["children"].append(node)
            nodes.append(node)
            make(kids, node, level + 1, node["digits"])
    roots = []
    make(SPEC, None, 1, [])
    roots = [n for n in nodes if n["level"] == 1]
    for j, rid in enumerate(CUSTOM_ROOT_ROWS, len(SPEC) + 1):
        node = {"fr": rid, "label": by_id[rid][2], "cat": "custom", "level": 1, "parent": None,
                "digits": [j], "children": [], "active": False, "kind": "custom",
                "path": (by_id[rid][2],)}
        nodes.append(node)

    # 2. Codes : conservés si le libellé est inchangé, sinon dérivés du chemin
    #    (les nœuds sont dans l'ordre parent -> enfant : le code du parent est déjà connu)
    for n in nodes:
        old_code, old_label = by_id[n["fr"]][1], by_id[n["fr"]][2]
        if n["kind"] == "custom" or old_label == n["label"]:
            n["code"] = old_code
        else:
            code = (n["parent"]["code"] + "_" if n["parent"] else "") + slug(n["label"])
            n["code"] = code[:64]                # colonne code : varchar(64)
    codes = [n["code"] for n in nodes]
    assert len(codes) == len(set(codes)), "codes en double dans l'arbre actif"

    # 3. Slots libres : les lignes restantes, réparties à tour de rôle sous les parents actifs
    leftover = [i for i in fr_ids if i not in used]
    hosts = [n for n in nodes if n["kind"] == "node" and n["level"] <= 3]
    slot_count = {id(h): 0 for h in hosts}
    slots = []
    k = 0
    while leftover:
        placed = False
        for h in hosts:
            if not leftover:
                break
            if len(h["children"]) + slot_count[id(h)] < MAX_CHILDREN:
                slot_count[id(h)] += 1
                n_ = slot_count[id(h)]
                rid = leftover.pop(0)
                child_level = h["level"] + 1
                slot = {"fr": rid, "level": child_level, "parent": h,
                        "label": None, "cat": h["cat"],
                        "code": None, "active": False,
                        "kind": "slot", "children": [], "path": h["path"]}
                h["children"].append(slot)
                slots.append(slot)
                placed = True
        if not placed:
            raise RuntimeError(f"capacité insuffisante : {len(leftover)} lignes sans place")
    # racines : chiffres des slots = rang parmi les fils (actifs d'abord)
    def assign(node, digits):
        node["digits"] = digits
        for i, ch in enumerate(node["children"], 1):
            assign(ch, digits + [i])
    for r in roots:
        assign(r, r["digits"])
    all_nodes = nodes + slots
    for n in all_nodes:
        s = "".join(map(str, n["digits"])).ljust(4, "0")
        n["new_fr"], n["new_en"] = int(f"{FR}{s}"), int(f"{EN}{s}")
        n["new_parent_fr"] = n["parent"]["new_fr"] if n["parent"] else None
        n["new_parent_en"] = n["parent"]["new_en"] if n["parent"] else None
    for n in all_nodes:
        if n["kind"] == "slot":                  # code court et unique : suffixe du nouvel ID
            n["code"] = f"type_niv{n['level']}_{n['new_fr'] % 100000}"
        if n["kind"] in ("slot", "custom"):
            # libellé = parent + rang : « Categorie_Niv21100_Level_5 » = 5e fils de 21100
            # (les 4 premiers sont déjà actifs). Un libellé propre à chaque langue.
            rank = n["digits"][-1]
            p_fr = n["parent"]["new_fr"] if n["parent"] else FR * 10000
            p_en = n["parent"]["new_en"] if n["parent"] else EN * 10000
            n["label"] = f"Categorie_Niv{p_fr}_Level_{rank}"
            n["label_en"] = f"Categorie_Niv{p_en}_Level_{rank}"
    codes = [n["code"] for n in all_nodes]
    assert len(codes) == len(set(codes)), "codes en double"
    assert all(len(c) <= 64 for c in codes), "code trop long"
    return by_id, en_of, all_nodes


def _iter_spec(spec):
    for label, cat, rid, kids in spec:
        yield label, cat, rid, kids
        yield from _iter_spec(kids)


def check(all_nodes, n_rows_fr):
    assert len(all_nodes) == n_rows_fr, (len(all_nodes), n_rows_fr)
    ids = [n["new_fr"] for n in all_nodes] + [n["new_en"] for n in all_nodes]
    assert len(ids) == len(set(ids)), "IDs en double"
    for n in all_nodes:
        assert len(n["children"]) <= MAX_CHILDREN
        assert n["level"] <= 4
        assert all(1 <= d <= 9 for d in n["digits"])


def reclass_targets(all_nodes, by_id):
    """{ancienne ligne FR: nouvel ID FR} pour les événements à reclasser."""
    idx = {n["path"]: n for n in all_nodes if n["kind"] == "node"}
    return {old: idx[path]["fr"] for old, path in RECLASS.items()}


def export_csv(all_nodes, by_id, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["ID FR", "ID EN", "Niveau", "Type", "Libellé", "Actif", "Ancien ID FR",
                    "Ancien libellé", "Ancien actif", "Code", "Catégorie"])
        for n in sorted(all_nodes, key=lambda n: n["new_fr"]):
            o = by_id[n["fr"]]
            w.writerow([n["new_fr"], n["new_en"], n["level"], n["kind"], n["label"], int(n["active"]),
                        n["fr"], o[2], int(o[4]), n["code"], n["cat"]])


def apply_plan(conn, all_nodes, by_id, en_of):
    cur = conn.cursor()
    fk = [("larcauth_event_type_config", "larcauth_event_type_config_parent_id_fkey"),
          ("student_event", "student_event_event_type_config_id_fkey"),
          ("staff_event", "staff_event_event_type_config_id_fkey")]
    for tbl, name in fk:
        cur.execute(f"ALTER TABLE {tbl} ALTER CONSTRAINT {name} DEFERRABLE INITIALLY IMMEDIATE")
    cur.execute("SET CONSTRAINTS " + ", ".join(n for _t, n in fk) + " DEFERRED")
    # « l'élève est sorti du cours » : information portée par l'événement lui-même
    cur.execute("ALTER TABLE student_event ADD COLUMN IF NOT EXISTS sortie "
                "BOOLEAN NOT NULL DEFAULT FALSE")

    idmap, rows = {}, []                        # ancien id -> nouvel id ; (id ancien, valeurs)
    for n in all_nodes:
        rows.append((n["fr"], FR, n["new_fr"], n["new_parent_fr"], n))
        rows.append((en_of[n["fr"]], EN, n["new_en"], n["new_parent_en"], n))
        idmap[n["fr"]] = n["new_fr"]
        idmap[en_of[n["fr"]]] = n["new_en"]

    # événements à reclasser (les deux langues, via l'appariement par code)
    targets = reclass_targets(all_nodes, by_id)
    ev_map = dict(idmap)
    for old, tgt in targets.items():
        ev_map[old] = idmap[tgt]
        ev_map[en_of[old]] = idmap[en_of[tgt]]
    active_old = {n["fr"] for n in all_nodes if n["kind"] == "node"}
    active_old |= {en_of[o] for o in active_old}
    removed = set(targets) | {en_of[o] for o in targets}
    cur.execute("select distinct event_type_config_id from student_event "
                "where event_type_config_id is not null")
    for (t,) in cur.fetchall():
        if t not in active_old and t not in removed:
            raise RuntimeError(f"événements sur un type qui disparaît sans reclassement : {t}")

    flag_ids = [i for o in SORTIE_FLAG_ROWS for i in (o, en_of[o])]
    cur.execute("update student_event set sortie = TRUE where event_type_config_id = any(%s)",
                (flag_ids,))
    cur.execute("update larcauth_event_type_config set code = 'tmp_' || id")
    for old, lang, new_id, new_parent, n in rows:
        label = n.get("label_en") if lang == EN and n.get("label_en") else n["label"]
        cur.execute("update larcauth_event_type_config set code=%s, label=%s, category=%s, "
                    "is_active=%s, parent_id=%s, updated_at=now() where id=%s",
                    (n["code"], label, n["cat"], n["active"], new_parent, old))
    for old, new in ev_map.items():
        cur.execute("update student_event set event_type_config_id=%s where event_type_config_id=%s",
                    (new, old))
    for old, lang, new_id, new_parent, n in rows:
        cur.execute("update larcauth_event_type_config set id=%s where id=%s", (new_id, old))
    cur.execute("select setval('larcauth_event_type_config_id_seq', "
                "(select max(id) from larcauth_event_type_config))")
    # texte de type conservé dans student_event.event_type : chemin des libellés du nouveau type
    cur.execute("select id, label, parent_id from larcauth_event_type_config")
    cfg = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    def path_of(i):
        parts = []
        while i:
            parts.append(cfg[i][0])
            i = cfg[i][1]
        return " > ".join(reversed(parts))
    cur.execute("select distinct event_type_config_id from student_event "
                "where event_type_config_id is not null")
    for (t,) in cur.fetchall():
        cur.execute("update student_event set event_type=%s where event_type_config_id=%s",
                    (path_of(t), t))
    return targets


if __name__ == "__main__":
    import psycopg2
    sys.path.insert(0, r"D:\projets")
    conn = psycopg2.connect(host="127.0.0.1", port=55517, dbname="NewLarcDb",
                            user="postgres", password="postgres")
    conn.autocommit = False
    cur = conn.cursor()
    by_id, en_of, all_nodes = build_plan(cur)
    check(all_nodes, sum(1 for r in by_id.values() if r[6] == FR))
    print("plan OK :", len(all_nodes), "lignes FR ;",
          sum(1 for n in all_nodes if n["kind"] == "node"), "nœuds actifs ;",
          sum(1 for n in all_nodes if n["kind"] == "slot"), "slots libres")
    if "--apply" not in sys.argv:
        export_csv(all_nodes, by_id, "arbre_evenements_complet.csv")
    try:
        apply_plan(conn, all_nodes, by_id, en_of)
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")           # force le contrôle des FK
        print("contrôle des clés étrangères OK")
        if "--apply" in sys.argv:
            conn.commit()
            print("COMMIT")
            conn.autocommit = True
            for tbl, name in (("larcauth_event_type_config", "larcauth_event_type_config_parent_id_fkey"),
                              ("student_event", "student_event_event_type_config_id_fkey"),
                              ("staff_event", "staff_event_event_type_config_id_fkey")):
                cur.execute(f"ALTER TABLE {tbl} ALTER CONSTRAINT {name} NOT DEFERRABLE")
            print("contraintes remises en NOT DEFERRABLE")
        else:
            conn.rollback()
            print("ROLLBACK (essai)")
    except Exception:
        conn.rollback()
        raise
