"""LetterTemplates — contenu des 100+ modèles de courriers RH.

Chaque fonction _body_<CODE>() retourne le corps spécifique du courrier.
Les paramètres (staff, ecole, date) sont passés à toutes les fonctions.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date

# Fallback si aucun campus n'est trouvé en base
_FALLBACK_NOM = "Établissement Arc-en-Ciel"
_FALLBACK_ADRESSE = "BP 12345, Lomé, Togo"
_FALLBACK_TEL = "+228 90 00 00 00"
_FALLBACK_EMAIL = "direction@arc-en-ciel.tg"
_FALLBACK_DIRECTEUR = "Le Chef d'Établissement"


def _find_logo() -> str:
    """Cherche logo.png dans les emplacements possibles (dev + compilé)."""
    candidates = [
        # 1) À côté de l'exécutable (compilé)
        os.path.join(os.path.dirname(sys.executable), "logo", "logo.png"),
        # 2) Racine projet (dev)
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "logo", "logo.png")),
    ]
    # PyInstaller _MEIPASS (ressources bundlées)
    base = getattr(sys, "_MEIPASS", "")
    if base:
        candidates.insert(0, os.path.join(base, "logo", "logo.png"))

    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]  # on essaie le premier même s'il n'existe pas (compilé)

# Fallback si aucun campus n'est trouvé en base
_FALLBACK_NOM = "Établissement Arc-en-Ciel"
_FALLBACK_ADRESSE = "BP 12345, Lomé, Togo"
_FALLBACK_TEL = "+228 90 00 00 00"
_FALLBACK_EMAIL = "direction@arc-en-ciel.tg"
_FALLBACK_DIRECTEUR = "Le Chef d'Établissement"

# ── Staff vide pour les aperçus (toutes les valeurs None → les _s() renvoient [placeholder]) ──
PLACEHOLDER_STAFF: dict[str, None] = {
    "id": None, "full_name": None, "professional_category": None,
    "date_entree": None, "hire_date": None, "base_salary": None,
}

# ── Tokens substituables dans les corps personnalisés ──
# Ordre : le plus long d'abord pour éviter les correspondances partielles.
# Volontairement exclus : [date], [date début], [nom] minuscule — utilisés éditorialement.
_STAFF_TOKENS = (
    ("[Nom complet]", "full_name"),
    ("[Matricule]",   "id"),
    ("[Nom]",         "full_name"),
    ("[Poste]",       "professional_category"),
    ("[poste]",       "professional_category"),
)

def _get_ecole(campus: dict | None) -> dict:
    """Retourne un dict avec les infos établissement depuis le campus ou le fallback."""
    if campus:
        adresse_parts = [campus.get("adress", "")]
        if campus.get("city"):
            adresse_parts.append(campus["city"])
        if campus.get("country"):
            adresse_parts.append(campus["country"])
        return {
            "nom": campus.get("label", _FALLBACK_NOM),
            "adresse": ", ".join(filter(None, adresse_parts)),
            "tel": campus.get("tel_1", _FALLBACK_TEL),
            "email": campus.get("email_1", _FALLBACK_EMAIL),
            "directeur": "Le Chef d'Établissement",
            "logo": _find_logo(),
        }
    return {
        "nom": _FALLBACK_NOM,
        "adresse": _FALLBACK_ADRESSE,
        "tel": _FALLBACK_TEL,
        "email": _FALLBACK_EMAIL,
        "directeur": _FALLBACK_DIRECTEUR,
        "logo": _find_logo(),
    }


def _s(staff: dict | None, key: str, default: str = "") -> str:
    """Extrait une valeur du dictionnaire staff."""
    if not staff:
        return default
    return str(staff.get(key, default) or default)


def _substitute_staff(text: str, staff: dict | None) -> str:
    """Remplace [Nom], [Poste], [Matricule] par les données réelles du staff.

    Seuls les tokens de la liste _STAFF_TOKENS sont substitués, et uniquement
    quand la valeur correspondante dans staff est truthy.
    """
    if not staff or not text:
        return text
    for token, key in _STAFF_TOKENS:
        val = staff.get(key)
        if val:
            text = text.replace(token, str(val))
    return text


def header(staff: dict | None, objet: str, ref: str,
           today: str = "", campus: dict | None = None) -> str:
    if not today:
        today = date.today().strftime("%d/%m/%Y")
    e = _get_ecole(campus)
    nom = _s(staff, "full_name", "[Nom complet]")
    poste = _s(staff, "professional_category", "[Poste]")
    sid = _s(staff, "id", "[Matricule]")
    return (
        f"{e['nom']}\n"
        f"{e['adresse']}\n"
        f"Tél : {e['tel']}  —  {e['email']}\n"
        f"\n"
        f"Réf : {ref}\n"
        f"Date : {today}\n"
        f"\n"
        f"À l'attention de :\n"
        f"  {nom}\n"
        f"  {poste}\n"
        f"  Matricule : {sid}\n"
        f"\n"
        f"Objet : {objet}\n"
        f"\n"
        f"{'─' * 60}\n"
        f"\n"
    )


def footer(campus: dict | None = None) -> str:
    e = _get_ecole(campus)
    return (
        f"\n{'─' * 60}\n"
        f"\n"
        f"Veuillez agréer, Madame, Monsieur, l'expression de mes salutations distinguées.\n"
        f"\n"
        f"{e['directeur']}\n"
        f"{e['nom']}\n"
        f"\n"
        f"Copie : Dossier de l'employé, Direction\n"
    )


def render_body(staff: dict | None, code: str, template: dict | None = None,
                campus: dict | None = None) -> str:
    """Retourne le corps seul (sans en-tête ni pied) pour aperçu et édition.

    Factorise la logique d'extraction auparavant dupliquée dans generate_docx().
    """
    full = build(staff, code, "", "", campus=campus, template=template)
    lines = full.split("\n")
    body_start = 0
    footer_start = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("Objet :"):
            body_start = i
        if line == "─" * 60 and i > body_start + 1:
            footer_start = i
            break
    body_lines = lines[body_start + 2:]  # skip "Objet :" et ligne vide après
    body_only = "\n".join(body_lines).split(f"\n{'─' * 60}\n")[0].strip()
    return body_only


def build(staff: dict | None, code: str, objet: str, ref: str,
          campus: dict | None = None, template: dict | None = None) -> str:
    global _ECOLE
    _ECOLE = _get_ecole(campus)  # rendu dispo pour toutes les fonctions _body_*
    today = date.today().strftime("%d/%m/%Y")
    h = header(staff, objet, ref, today, campus)
    f = footer(campus)
    body = None

    # 1. Corps personnalisé stocké en base (priorité maximale)
    if template and template.get("body_text"):
        body = _substitute_staff(template["body_text"], staff)

    # 2. Lien vivant vers le code source (copie non modifiée d'un builtin)
    if body is None and template and template.get("source_code"):
        src = template["source_code"]
        if re.fullmatch(r"[A-J][0-9]{2}", src):
            body_func = globals().get(f"_body_{src}")
            if body_func:
                body = body_func(staff, today)

    # 3. Fonction directe _body_{code} (builtin ou code sans template)
    if body is None:
        body_func = globals().get(f"_body_{code}")
        if body_func:
            body = body_func(staff, today)

    # 4. Fallback par famille
    if body is None:
        family = code[0] if code else "F"
        body = _family_fallback(family, staff, today)

    return h + body + f


def _family_fallback(family: str, staff: dict | None, today: str) -> str:
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    poste = _s(staff, "professional_category", "[Poste]")
    sid = _s(staff, "id", "[Matricule]")
    fallbacks = {
        "A": (
            f"Madame, Monsieur,\n\n"
            f"Nous faisons suite à [entretien / décision] et vous informons "
            f"des dispositions relatives à votre contrat de travail.\n\n"
            f"[Détails du contrat : type, dates, salaire, conditions]\n\n"
            f"Nous vous invitons à prendre contact avec le secrétariat pour les formalités."
        ),
        "B": (
            f"Madame, Monsieur,\n\n"
            f"Nous vous informons de la décision suivante concernant votre rémunération "
            f"ou vos avantages professionnels.\n\n"
            f"[Détails : montant, date d'effet, référence]\n\n"
            f"La présente décision prend effet à compter de sa notification."
        ),
        "C": (
            f"Madame, Monsieur,\n\n"
            f"Nous portons à votre connaissance les faits suivants :\n\n"
            f"  • [Description précise des faits]\n\n"
            f"Nous vous informons des suites disciplinaires engagées conformément "
            f"au règlement intérieur et au Code du Travail."
        ),
        "D": (
            f"Madame, Monsieur,\n\n"
            f"Nous faisons suite à votre demande de [type de congé] "
            f"du [date de la demande] pour la période du [date début] au [date fin].\n\n"
            f"Après examen, nous vous informons que [décision].\n\n"
            f"[Motif en cas de refus / Rappel des dates en cas d'accord]"
        ),
        "E": (
            f"Madame, Monsieur,\n\n"
            f"Nous faisons suite à votre [démission / fin de contrat / départ en retraite] "
            f"notifiée le [date].\n\n"
            f"Nous vous informons des modalités de votre départ et des documents "
            f"qui vous seront remis."
        ),
        "F": (
            f"Madame, Monsieur,\n\n"
            f"[Nom],\n\n"
            f"Nous portons à votre connaissance l'information suivante : "
            f"[contenu de la communication].\n\n"
            f"Pour toute question, veuillez vous adresser au secrétariat de direction."
        ),
        "G": (
            f"Madame, Monsieur,\n\n"
            f"Nous faisons suite à votre candidature pour le poste de {poste} "
            f"au sein de {_ECOLE['nom']}.\n\n"
            f"Après examen de votre dossier, nous vous informons que [décision].\n\n"
            f"Nous vous remercions de l'intérêt que vous portez à notre établissement."
        ),
        "H": (
            f"Madame, Monsieur le Directeur,\n\n"
            f"Je soussigné(e), {nom}, matricule n°{sid}, {poste},\n"
            f"ai l'honneur de [objet de la demande].\n\n"
            f"[Détails et motivation de la demande]\n\n"
            f"Je vous prie d'agréer, Madame, Monsieur, "
            f"l'expression de mes salutations distinguées.\n\n"
            f"Signature de l'employé"
        ),
        "I": (
            f"Madame, Monsieur,\n\n"
            f"Dans le cadre du programme du Baccalauréat International (IB), "
            f"nous attestons / vous informons que [contenu spécifique IB].\n\n"
            f"La présente [attestation / notification] est délivrée pour servir "
            f"et valoir ce que de droit."
        ),
        "J": (
            f"Madame, Monsieur le Délégué du Personnel,\n\n"
            f"Dans le cadre du dialogue social au sein de {_ECOLE['nom']}, "
            f"nous vous informons que [contenu].\n\n"
            f"Vous voudrez bien en prendre note et en informer les personnels concernés."
        ),
    }
    return fallbacks.get(family, "[Corps du courrier à compléter]")


# ════════════════════════════════════════════════════════════════════
# Famille A — Contrat et emploi
# ════════════════════════════════════════════════════════════════════

def _body_A01(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    salaire = str(staff.get("base_salary") or "[salaire brut]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à votre entretien avec la commission de recrutement et à la décision de la "
        f"Direction en date du [date de la décision], nous avons le plaisir de vous confirmer "
        f"votre engagement au sein de l'{_ECOLE['nom']} en qualité de {poste}, "
        f"à compter du {date_emb}.\n\n"
        f"Il s'agit d'un Contrat à Durée Indéterminée (CDI) régi par les dispositions du Code "
        f"du Travail en vigueur et la Convention Collective applicable à l'enseignement privé.\n\n"
        f"Votre rémunération brute mensuelle est fixée à {salaire} francs CFA, assortie des "
        f"avantages prévus par le statut du personnel de l'établissement (indemnité de logement, "
        f"indemnité de transport, prime de bilan annuelle).\n\n"
        f"Une période d'essai de trois (3) mois est prévue à compter de votre prise de fonction. "
        f"Durant cette période, chacune des parties pourra rompre le contrat moyennant un préavis "
        f"de huit (8) jours. À l'issue de cette période d'essai concluante, votre contrat sera "
        f"définitivement confirmé.\n\n"
        f"Vous voudrez bien vous présenter au Bureau du Directeur le [date] à [heure] pour la "
        f"signature du contrat et la constitution de votre dossier administratif (pièce d'identité, "
        f"diplômes originaux, certificat médical, extrait de casier judiciaire, photos d'identité).\n\n"
        f"Nous vous souhaitons la bienvenue au sein de notre communauté éducative et vous adressons "
        f"tous nos vœux de réussite dans vos nouvelles fonctions."
    )


def _body_A02(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date début]"))
    salaire = str(staff.get("base_salary") or "[salaire brut]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à votre entretien avec la commission de recrutement, nous vous confirmons votre "
        f"engagement au sein de l'{_ECOLE['nom']} en qualité de {poste}, pour une durée déterminée "
        f"allant du {date_emb} au [date de fin].\n\n"
        f"Ce Contrat à Durée Déterminée (CDD) est conclu pour le motif suivant : "
        f"[remplacement de M./Mme X, en congé de maternité / maladie de longue durée / "
        f"accroissement temporaire d'activité / projet spécifique].\n\n"
        f"Votre rémunération brute mensuelle est fixée à {salaire} francs CFA.\n\n"
        f"Conformément à la législation en vigueur, une indemnité de fin de contrat (indemnité de "
        f"précarité) vous sera versée au terme de celui-ci, sauf en cas de transformation en CDI "
        f"ou de rupture anticipée à votre initiative.\n\n"
        f"Vous voudrez bien vous présenter au Bureau du Directeur le [date] pour signature."
    )


def _body_A06(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Par avenant au contrat de travail qui vous lie à l'{_ECOLE['nom']} en date du "
        f"[date du contrat initial / dernier avenant], nous vous informons de la "
        f"modification suivante apportée à votre contrat :\n\n"
        f"  1. Nature de la modification :\n"
        f"     □ Modification de la rémunération\n"
        f"     □ Modification du temps de travail\n"
        f"     □ Changement d'affectation (campus / niveau / programme)\n"
        f"     □ Modification de la durée du contrat\n"
        f"     □ Autre : [préciser]\n\n"
        f"  2. Nouvelle disposition : [détail de la nouvelle clause]\n\n"
        f"  3. Date d'effet : [date]\n\n"
        f"Toutes les autres clauses et conditions de votre contrat initial restent inchangées "
        f"et continuent de produire leurs pleins effets.\n\n"
        f"Le présent avenant prend effet à compter de sa signature par les deux parties. "
        f"Nous vous invitons à vous présenter au Bureau du Directeur pour signature."
    )


def _body_A07(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Votre Contrat à Durée Déterminée arrivant à échéance le [date de fin], et après "
        f"évaluation positive de votre travail, nous avons le plaisir de vous informer de son "
        f"renouvellement pour une nouvelle période allant du [nouvelle date début] au "
        f"[nouvelle date fin], dans les mêmes fonctions de {poste}.\n\n"
        f"Les autres conditions de votre contrat (rémunération, avantages, lieu de travail) "
        f"restent inchangées, sauf disposition contraire précisée dans l'avenant joint.\n\n"
        f"Nous vous remercions pour la qualité de votre travail et votre engagement au service "
        f"des élèves de l'{_ECOLE['nom']}."
    )


def _body_A08(staff, today):
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"Madame, Monsieur,\n\n"
        f"Votre période d'essai, débutée le {date_emb}, arrive à son terme le "
        f"[date de fin de la période d'essai].\n\n"
        f"Après évaluation de votre travail par votre supérieur hiérarchique, nous avons le "
        f"plaisir de vous confirmer la validation définitive de cette période d'essai.\n\n"
        f"Votre contrat de travail se poursuit donc dans les conditions initialement convenues, "
        f"et vous êtes désormais intégré(e) au personnel permanent de l'établissement.\n\n"
        f"Nous vous félicitons pour votre intégration réussie et la qualité du travail accompli "
        f"depuis votre arrivée. Nous sommes heureux de vous compter parmi les membres de notre "
        f"communauté éducative."
    )


def _body_A09(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous faisons suite à votre contrat de travail et à la période d'essai en cours.\n\n"
        f"Après évaluation approfondie de votre travail et de votre intégration dans l'équipe, "
        f"nous sommes au regret de vous informer que nous mettons fin à votre période d'essai "
        f"à compter du [date].\n\n"
        f"Cette décision est motivée par les éléments suivants portés à notre connaissance :\n"
        f"  • [Motif 1]\n"
        f"  • [Motif 2]\n\n"
        f"Conformément aux dispositions du Code du Travail relatives à la période d'essai, "
        f"cette rupture intervient sans préavis ni indemnité.\n\n"
        f"Nous vous remercions pour votre contribution et vous souhaitons pleine réussite "
        f"dans la suite de votre parcours professionnel."
    )


def _body_A10(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Dans le cadre de [la session d'examens / du projet / de l'événement], "
        f"nous vous confions une mission spécifique en qualité de {poste}.\n\n"
        f"Cette mission se déroulera du [date début] au [date fin] et comprendra "
        f"les tâches suivantes :\n"
        f"  • [Tâche 1]\n"
        f"  • [Tâche 2]\n\n"
        f"Pour l'accomplissement de cette mission, vous percevrez une rémunération / indemnité "
        f"de [montant] francs CFA [par vacation / jour / heure].\n\n"
        f"La présente lettre de mission est établie en complément de votre contrat de travail "
        f"et ne modifie pas vos conditions d'emploi habituelles."
    )


def _body_A11(staff, today):
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"Madame, Monsieur,\n\n"
        f"Votre Contrat à Durée Déterminée conclu le {date_emb} arrive à échéance "
        f"le [date de fin].\n\n"
        f"Après examen de votre situation, nous vous informons que ce contrat ne sera pas "
        f"renouvelé, pour le motif suivant : [retour du titulaire du poste / fin du projet / "
        f"réorganisation du service / autre].\n\n"
        f"Nous vous remercions sincèrement pour votre contribution à l'{_ECOLE['nom']} "
        f"durant cette période. Nous tenons à votre disposition les documents suivants qui "
        f"vous seront remis lors de votre départ :\n"
        f"  • Votre certificat de travail\n"
        f"  • Votre solde de tout compte\n"
        f"  • L'attestation d'emploi\n\n"
        f"Nous conservons votre dossier et n'hésiterons pas à faire appel à vous si une "
        f"nouvelle opportunité correspondant à votre profil se présente."
    )


def _body_A12(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Votre Contrat à Durée Déterminée arrivant à échéance le [date], et compte tenu de "
        f"la qualité de votre travail et des besoins permanents de l'établissement, nous avons "
        f"le plaisir de vous proposer une transformation de votre contrat en Contrat à Durée "
        f"Indéterminée (CDI).\n\n"
        f"Cette proposition prendrait effet le [date] et maintiendrait vos fonctions actuelles "
        f"de {poste}. Votre rémunération et vos avantages resteraient inchangés, avec une "
        f"régularisation de votre ancienneté reprenant la date de votre engagement initial.\n\n"
        f"Nous vous remercions de nous faire part de votre réponse avant le [date]."
    )


# ════════════════════════════════════════════════════════════════════
# Famille B — Rémunération
# ════════════════════════════════════════════════════════════════════

def _body_B01(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"En reconnaissance de la qualité de votre travail, de votre engagement au service des "
        f"élèves et de l'atteinte de vos objectifs professionnels pour l'année scolaire écoulée, "
        f"nous avons le plaisir de vous informer que votre rémunération brute mensuelle est portée "
        f"de [ancien salaire] à [nouveau salaire] francs CFA, à compter du 1er [mois] [année].\n\n"
        f"Cette augmentation prend en compte :\n"
        f"  • Votre ancienneté au sein de l'établissement\n"
        f"  • Les résultats de votre évaluation professionnelle annuelle\n"
        f"  • Le barème salarial en vigueur pour votre catégorie\n\n"
        f"Un avenant à votre contrat de travail formalisant cette modification vous sera soumis "
        f"pour signature dans les meilleurs délais."
    )


def _body_B02(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à [l'évaluation de votre dossier / la vacance de poste / la réorganisation du "
        f"service], nous avons le plaisir de vous informer de votre promotion au poste de "
        f"[nouveau poste] à compter du [date].\n\n"
        f"Cette promotion s'accompagne des modifications suivantes :\n"
        f"  • Nouvelle rémunération brute mensuelle : [montant] francs CFA\n"
        f"  • Nouvelle classification : [échelon / catégorie]\n"
        f"  • Nouvelles responsabilités : [description]\n\n"
        f"Nous vous félicitons pour cette promotion qui témoigne de la confiance que nous vous "
        f"accordons et de la qualité de votre parcours professionnel."
    )


def _body_B03(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous avons le plaisir de vous informer de l'attribution d'une prime exceptionnelle "
        f"d'un montant de [montant] francs CFA.\n\n"
        f"Cette prime vous est attribuée au titre de :\n"
        f"  □ Prime de bilan annuelle — Exercice [année]\n"
        f"  □ 13e mois\n"
        f"  □ Gratification pour [motif]\n"
        f"  □ Prime de [technicité / performance / ancienneté]\n\n"
        f"Ce montant sera versé avec votre salaire du mois de [mois] [année].\n\n"
        f"Nous vous remercions pour votre contribution à la réussite de notre établissement."
    )


def _body_B04(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Dans le cadre de [la réorganisation des services / l'ouverture d'un nouveau campus / "
        f"la réponse à un besoin exprimé], nous vous informons de votre mutation du campus de "
        f"[campus d'origine] vers le campus de [campus de destination] à compter du [date].\n\n"
        f"Vos fonctions de [poste] et vos conditions contractuelles restent inchangées.\n\n"
        f"Nous vous remercions de prendre contact avec le responsable du campus de [destination] "
        f"pour organiser votre prise de fonction. Nous restons à votre disposition pour toute "
        f"question relative à cette mutation."
    )


def _body_B05(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    sid = _s(staff, "id", "[Matricule]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"certifie que {nom}, matricule n°{sid}, exerce les fonctions de {poste} "
        f"au sein de notre établissement depuis le {date_emb}.\n\n"
        f"À la date du {today}, l'ancienneté cumulée de l'intéressé(e) est de "
        f"[X années et Y mois].\n\n"
        f"La présente attestation est délivrée à l'intéressé(e) pour servir et valoir "
        f"ce que de droit."
    )


def _body_B06(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    sid = _s(staff, "id", "[Matricule]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"atteste que {nom}, matricule n°{sid}, est employé(e) au sein de notre établissement "
        f"depuis le {date_emb}, en qualité de {poste}, dans le cadre d'un Contrat à Durée "
        f"[Indéterminée / Déterminée].\n\n"
        f"L'intéressé(e) exerce ses fonctions à temps [plein / partiel] et perçoit une "
        f"rémunération brute mensuelle de [montant] francs CFA.\n\n"
        f"La présente attestation d'emploi est délivrée à la demande de l'intéressé(e) pour "
        f"servir et valoir ce que de droit, notamment auprès de [banque / administration / "
        f"organisme de logement / ambassade]."
    )


def _body_B09(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date début]"))
    return (
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"certifie que {nom} a exercé les fonctions de {poste} au sein de notre établissement "
        f"du {date_emb} au [date de départ].\n\n"
        f"Durant cette période, l'intéressé(e) a accompli ses fonctions avec sérieux, compétence "
        f"et dévouement, donnant entière satisfaction à sa hiérarchie.\n\n"
        f"En foi de quoi, le présent certificat de travail est délivré à l'intéressé(e) "
        f"conformément aux dispositions de l'article [numéro] du Code du Travail en vigueur, "
        f"pour servir et valoir ce que de droit.\n\n"
        f"Fait à Lomé, le {today}"
    )


def _body_B10(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    sid = _s(staff, "id", "[Matricule]")
    return (
        f"ATTESTATION DE RETENUE DE L'IMPÔT SUR LE TRAITEMENT ET SALAIRES (ITS)\n\n"
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"atteste que les retenues d'Impôt sur le Traitement et Salaires (ITS) ont été "
        f"effectuées sur les salaires de {nom}, matricule n°{sid}, "
        f"pour la période du 1er janvier au 31 décembre [année].\n\n"
        f"Montant total des retenues ITS sur l'année : [montant] francs CFA.\n\n"
        f"La présente attestation est délivrée à l'intéressé(e) pour sa déclaration fiscale "
        f"annuelle."
    )


def _body_B11(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    sid = _s(staff, "id", "[Matricule]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"ATTESTATION D'AFFILIATION À LA CAISSE NATIONALE DE SÉCURITÉ SOCIALE (CNSS)\n\n"
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"atteste que {nom}, matricule n°{sid}, employé(e) depuis le {date_emb}, "
        f"est régulièrement déclaré(e) auprès de la Caisse Nationale de Sécurité Sociale (CNSS) "
        f"sous le numéro d'immatriculation [n° CNSS].\n\n"
        f"Les cotisations sociales (part salariale et part patronale) sont versées mensuellement "
        f"conformément à la réglementation en vigueur.\n\n"
        f"La présente attestation est délivrée pour servir et valoir ce que de droit."
    )


# ════════════════════════════════════════════════════════════════════
# Famille C — Discipline
# ════════════════════════════════════════════════════════════════════

def _body_C01(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous constatons que vous avez été absent(e) de votre poste de travail aux dates "
        f"suivantes, sans autorisation préalable ni justificatif transmis dans les délais "
        f"réglementaires :\n\n"
        f"  • [Date 1]\n"
        f"  • [Date 2]\n"
        f"  • [Date 3]\n\n"
        f"Pour rappel, le Règlement Intérieur de l'établissement stipule que toute absence doit "
        f"être signalée à votre supérieur hiérarchique direct dès la première heure d'absence, "
        f"et qu'un justificatif écrit (certificat médical ou autre) doit être fourni dans un "
        f"délai maximum de quarante-huit (48) heures.\n\n"
        f"Ces absences injustifiées perturbent le fonctionnement du service et portent préjudice "
        f"à la continuité pédagogique vis-à-vis de nos élèves.\n\n"
        f"Par la présente, nous vous adressons un premier rappel à l'ordre. Nous vous demandons "
        f"de bien vouloir régulariser votre situation dans les plus brefs délais et de respecter "
        f"scrupuleusement les procédures en vigueur à l'avenir.\n\n"
        f"À défaut d'amélioration, nous serons contraints d'engager une procédure disciplinaire "
        f"conformément aux dispositions du Règlement Intérieur et du Code du Travail."
    )


def _body_C02(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous constatons avec regret que vous avez accumulé les retards suivants au cours "
        f"des dernières semaines :\n\n"
        f"  • [Date 1] : arrivée à [heure]\n"
        f"  • [Date 2] : arrivée à [heure]\n"
        f"  • [Date 3] : arrivée à [heure]\n"
        f"  • [Date 4] : arrivée à [heure]\n"
        f"  • [Date 5] : arrivée à [heure]\n\n"
        f"Ces retards répétés, non justifiés, perturbent l'organisation des cours et nuisent "
        f"à la qualité de l'enseignement dispensé aux élèves.\n\n"
        f"Nous vous rappelons que l'horaire de prise de service est fixé à [heure] et que "
        f"tout retard doit rester exceptionnel et justifié.\n\n"
        f"La présente constitue un premier rappel à l'ordre. Nous vous demandons de prendre "
        f"les dispositions nécessaires pour respecter vos horaires de travail."
    )


def _body_C04(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Malgré le rappel à l'ordre qui vous a été adressé le [date du précédent courrier], "
        f"nous constatons la persistance des faits suivants :\n\n"
        f"  1. [Description précise du premier fait reproché, avec dates]\n"
        f"  2. [Description précise du second fait reproché, avec dates]\n\n"
        f"Ces agissements constituent un manquement caractérisé à vos obligations "
        f"contractuelles et aux dispositions du Règlement Intérieur de l'établissement, "
        f"notamment :\n"
        f"  • Article [X] — [Obligation visée]\n"
        f"  • Article [Y] — [Obligation visée]\n\n"
        f"En conséquence, nous vous notifions par la présente un AVERTISSEMENT ÉCRIT "
        f"qui sera versé à votre dossier administratif.\n\n"
        f"Nous vous demandons instamment de modifier votre comportement et de vous conformer "
        f"strictement à vos obligations professionnelles. Tout nouveau manquement pourrait "
        f"entraîner des sanctions disciplinaires plus graves."
    )


def _body_C05(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à l'avertissement écrit qui vous a été notifié le [date] et aux faits "
        f"persistants suivants :\n\n"
        f"  • [Énumération des faits reprochés]\n\n"
        f"Après examen approfondi de votre dossier et après vous avoir entendu lors de "
        f"l'entretien du [date], nous avons décidé de vous infliger un BLÂME.\n\n"
        f"Cette sanction, qui constitue le deuxième niveau de l'échelle disciplinaire, "
        f"sera inscrite à votre dossier.\n\n"
        f"Nous vous engageons fermement à prendre les mesures nécessaires pour remédier "
        f"définitivement à cette situation. Nous attirons votre attention sur le fait que "
        f"la persistance des manquements constatés pourrait conduire à des sanctions plus "
        f"lourdes, pouvant aller jusqu'au licenciement."
    )


def _body_C07(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Des faits susceptibles de constituer une faute disciplinaire vous étant imputables "
        f"ont été portés à notre connaissance, à savoir :\n\n"
        f"  • [Description précise et circonstanciée des faits reprochés]\n"
        f"  • [Dates et lieux]\n\n"
        f"En application des articles [numéros] du Code du Travail et du Règlement Intérieur "
        f"de l'établissement, nous vous convoquons à un entretien préalable qui se tiendra :\n\n"
        f"  Date : [date]\n"
        f"  Heure : [heure]\n"
        f"  Lieu : Bureau du Directeur / Bureau du DRH\n\n"
        f"Lors de cet entretien, vous pourrez présenter vos explications et observations "
        f"sur les faits qui vous sont reprochés.\n\n"
        f"Conformément à la loi, vous avez la possibilité de vous faire assister par une "
        f"personne de votre choix appartenant obligatoirement au personnel de l'établissement. "
        f"Vous voudrez bien nous communiquer le nom de cette personne au moins 48 heures avant "
        f"l'entretien.\n\n"
        f"Nous vous invitons à prendre cet entretien avec le plus grand sérieux, une sanction "
        f"disciplinaire pouvant aller jusqu'au licenciement étant susceptible d'être prononcée "
        f"à son issue."
    )


def _body_C10(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous faisons suite à l'entretien préalable du [date] au cours duquel vous avez pu "
        f"présenter vos observations, assisté(e) de M./Mme [nom de l'assistant].\n\n"
        f"Après examen approfondi des faits et de l'ensemble des éléments de votre dossier, "
        f"nous sommes au regret de vous notifier votre LICENCIEMENT POUR FAUTE [GRAVE / LOURDE] "
        f"à compter du [date].\n\n"
        f"Les motifs de cette décision, qui vous ont été exposés lors de l'entretien préalable "
        f"et consignés dans le compte-rendu joint, sont les suivants :\n"
        f"  1. [Grief détaillé 1]\n"
        f"  2. [Grief détaillé 2]\n\n"
        f"Conformément aux dispositions du Code du Travail, [le préavis de licenciement est dû "
        f"et s'élève à (durée) / la faute grave vous prive de l'indemnité de préavis et de "
        f"l'indemnité de licenciement].\n\n"
        f"Nous tenons à votre disposition votre certificat de travail, votre solde de tout "
        f"compte et l'attestation d'emploi, qui vous seront remis à la date de votre départ "
        f"effectif."
    )


# ════════════════════════════════════════════════════════════════════
# Famille D — Congés (RH → Employé)
# ════════════════════════════════════════════════════════════════════

def _body_D01(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous accusons réception de votre demande de [type de congé] en date du [date de "
        f"la demande], concernant la période du [date début] au [date fin], "
        f"soit [X] jours [ouvrés / calendaires].\n\n"
        f"Nous vous informons que votre demande a bien été enregistrée sous la référence "
        f"[référence] et qu'elle est en cours d'examen par votre supérieur hiérarchique.\n\n"
        f"Vous recevrez une réponse dans un délai maximum de [X] jours ouvrés. "
        f"Nous vous rappelons que vous ne devez pas vous absenter avant d'avoir reçu "
        f"l'accord écrit de votre hiérarchie.\n\n"
        f"Nous restons à votre disposition pour toute information complémentaire."
    )


def _body_D02(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à votre demande de congé annuel du [date de la demande], nous avons le plaisir "
        f"de vous informer que votre congé est ACCORDÉ pour la période suivante :\n\n"
        f"  Date de début : [date début]\n"
        f"  Date de fin : [date fin]\n"
        f"  Date de reprise : [date de reprise]\n"
        f"  Nombre de jours ouvrés : [X] jours\n"
        f"  Solde de congés restant après décompte : [X] jours\n\n"
        f"Nous vous rappelons que vous devez impérativement reprendre votre service le "
        f"[date de reprise] à [heure]. En cas d'empêchement, vous devez en informer "
        f"votre supérieur hiérarchique dans les plus brefs délais.\n\n"
        f"Nous vous souhaitons un excellent repos et une bonne continuation à votre retour."
    )


def _body_D03(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous faisons suite à votre demande de congé annuel du [date de la demande] pour "
        f"la période du [date début] au [date fin].\n\n"
        f"Après examen de votre demande et compte tenu des contraintes d'organisation du "
        f"service, nous sommes au regret de ne pouvoir y donner une suite favorable pour le "
        f"motif suivant :\n\n"
        f"  • [Motif précis : pic d'activité lié aux examens de fin de trimestre / nombre "
        f"    trop important d'absences simultanées dans votre département / nécessité de "
        f"    service liée à (événement)]\n\n"
        f"Nous vous invitons à soumettre une nouvelle demande pour une période ultérieure, "
        f"en concertation avec votre supérieur hiérarchique. Nous restons à votre disposition "
        f"pour vous aider à identifier une période compatible avec les besoins du service."
    )


def _body_D06(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous accusons réception du certificat médical que vous nous avez transmis en date "
        f"du [date], prescrivant un arrêt de travail du [date début] au [date fin].\n\n"
        f"Votre absence est enregistrée en congé de maladie. Nous vous rappelons vos "
        f"obligations :\n\n"
        f"  1. Transmettre tout certificat médical dans un délai maximum de 48 heures "
        f"     suivant le début de l'absence\n"
        f"  2. Informer votre supérieur hiérarchique de la durée prévisible de votre absence\n"
        f"  3. Transmettre tout certificat de prolongation dans les mêmes délais\n"
        f"  4. Vous soumettre à la visite médicale de reprise à l'issue de votre arrêt\n\n"
        f"Nous vous souhaitons un prompt rétablissement et restons à votre disposition pour "
        f"toute question relative à vos droits."
    )


def _body_D09(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame,\n\n"
        f"Nous accusons réception de votre déclaration de grossesse en date du [date] et vous "
        f"en remercions.\n\n"
        f"Conformément aux dispositions du Code du Travail, vous bénéficiez d'un congé de "
        f"maternité de quatorze (14) semaines, réparti comme suit :\n\n"
        f"  • Six (6) semaines avant la date présumée d'accouchement, soit à compter du [date]\n"
        f"  • Huit (8) semaines après l'accouchement, soit jusqu'au [date]\n\n"
        f"Votre congé maternité est donc programmé du [date début] au [date fin], sous réserve "
        f"de la date effective de votre accouchement.\n\n"
        f"Pendant cette période, votre salaire est intégralement maintenu dans les conditions "
        f"prévues par la loi et la convention collective applicable.\n\n"
        f"Nous vous souhaitons une grossesse sereine et restons à votre disposition pour toute "
        f"question relative à vos droits ou à l'organisation de votre retour."
    )


def _body_D10(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à votre demande du [date] et sur présentation de l'acte de naissance de votre "
        f"enfant, nous avons le plaisir de vous accorder un congé de paternité de trois (3) jours "
        f"ouvrables, à prendre dans un délai de [X] jours suivant la naissance.\n\n"
        f"Période retenue : du [date début] au [date fin].\n\n"
        f"Toutes nos félicitations pour cet heureux événement."
    )


def _body_D12(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous faisons suite à votre absence du [date(s)] et constatons que nous n'avons pas "
        f"reçu, dans les délais réglementaires, les justificatifs permettant de régulariser "
        f"votre situation.\n\n"
        f"Nous vous demandons de bien vouloir nous transmettre, dans un délai de [X] jours "
        f"à compter de la réception de la présente, le(s) document(s) suivant(s) :\n\n"
        f"  □ Certificat médical original\n"
        f"  □ Certificat de décès (en cas de décès d'un proche)\n"
        f"  □ Acte de mariage\n"
        f"  □ Autre justificatif : [préciser]\n\n"
        f"À défaut de réception de ces justificatifs dans le délai imparti, les journées "
        f"concernées seront considérées comme des absences injustifiées et pourront donner "
        f"lieu à une retenue sur salaire et/ou à des poursuites disciplinaires."
    )


# ════════════════════════════════════════════════════════════════════
# Famille E — Fin de contrat et départ
# ════════════════════════════════════════════════════════════════════

def _body_E01(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous accusons réception de votre lettre de démission en date du [date de la lettre], "
        f"par laquelle vous nous informez de votre décision de quitter vos fonctions "
        f"au sein de l'{_ECOLE['nom']}.\n\n"
        f"Nous prenons acte de votre démission. Conformément à la législation en vigueur et "
        f"aux dispositions de votre contrat de travail, votre préavis de [durée] débutera le "
        f"[date] et prendra fin le [date]. Votre départ effectif interviendra à l'issue de "
        f"ce préavis.\n\n"
        f"Durant cette période, vous restez tenu(e) à l'ensemble de vos obligations "
        f"professionnelles. Nous vous remercions de bien vouloir faciliter la transition "
        f"et la passation de vos dossiers à votre successeur.\n\n"
        f"Nous vous remercions pour votre contribution à l'{_ECOLE['nom']} et vous souhaitons "
        f"pleine réussite dans la poursuite de votre carrière."
    )


def _body_E05(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    sid = _s(staff, "id", "[Matricule]")
    return (
        f"REÇU POUR SOLDE DE TOUT COMPTE\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, reconnais avoir reçu de "
        f"l'{_ECOLE['nom']} la somme nette de [montant en chiffres] francs CFA "
        f"([montant en lettres] francs CFA), représentant le solde de tout compte "
        f"consécutif à la rupture de mon contrat de travail.\n\n"
        f"Ce solde se décompose comme suit :\n"
        f"  • Salaire du [date] au [date] : [montant] F CFA\n"
        f"  • Indemnité compensatrice de congés payés ([X] jours) : [montant] F CFA\n"
        f"  • Indemnité de licenciement : [montant] F CFA\n"
        f"  • Indemnité de préavis : [montant] F CFA\n"
        f"  • Autres : [détail et montant]\n\n"
        f"Je reconnais que cette somme couvre l'intégralité des sommes qui m'étaient dues "
        f"par mon employeur au titre de l'exécution et de la rupture de mon contrat de travail, "
        f"et donne quitus à l'employeur pour solde de tout compte.\n\n"
        f"Fait à [Lieu], le [date]\n\n"
        f"Signature de l'employé\n"
        f"(précédée de la mention manuscrite « Lu et approuvé, Bon pour solde de tout compte »)"
    )


def _body_E06(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date début]"))
    return (
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"certifie que {nom} a exercé les fonctions de {poste} au sein de notre établissement "
        f"du {date_emb} au [date de départ].\n\n"
        f"Pendant la durée de son emploi, l'intéressé(e) a accompli ses fonctions avec "
        f"[sérieux, compétence et dévouement / appréciation], donnant [entière / bonne] "
        f"satisfaction à sa hiérarchie.\n\n"
        f"En foi de quoi, le présent certificat de travail est délivré pour servir et valoir "
        f"ce que de droit, conformément aux dispositions de l'article [numéro] du Code du "
        f"Travail en vigueur.\n\n"
        f"Fait à Lomé, le {today}"
    )


def _body_E08(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Je suis heureux de vous recommander {nom} qui a exercé les fonctions de {poste} "
        f"au sein de l'{_ECOLE['nom']}.\n\n"
        f"Durant [X années] passées dans notre établissement, {nom} a fait preuve de qualités "
        f"professionnelles remarquables : [rigueur, créativité pédagogique, esprit d'équipe, "
        f"engagement envers les élèves, etc.].\n\n"
        f"[Paragraphe personnalisé sur les réalisations et qualités spécifiques du candidat]\n\n"
        f"Je recommande {nom} sans réserve et suis convaincu(e) qu'il/elle saura apporter "
        f"une contribution précieuse à tout établissement qui l'accueillera.\n\n"
        f"Je reste à votre disposition pour tout renseignement complémentaire."
    )


def _body_E09(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous faisons suite à votre demande de départ à la retraite en date du [date].\n\n"
        f"Après vérification de votre dossier, nous vous confirmons que vous remplissez les "
        f"conditions pour faire valoir vos droits à la retraite à compter du [date].\n\n"
        f"Votre départ effectif est fixé au [date]. Compte tenu de votre ancienneté au sein "
        f"de l'établissement depuis le {date_emb}, votre indemnité de départ à la retraite "
        f"s'élève à [montant] francs CFA, calculée conformément à la convention collective "
        f"applicable.\n\n"
        f"Nous vous remercions chaleureusement pour l'ensemble de votre carrière au service "
        f"de l'{_ECOLE['nom']} et de ses élèves. Votre dévouement et votre contribution à la "
        f"vie de notre établissement resteront dans nos mémoires.\n\n"
        f"Une cérémonie de départ sera organisée en votre honneur le [date]."
    )


# ════════════════════════════════════════════════════════════════════
# Famille F — Vie professionnelle
# ════════════════════════════════════════════════════════════════════

def _body_F01(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Vous êtes convoqué(e) à la [réunion pédagogique / réunion de coordination / "
        f"réunion administrative / conseil de classe / conseil d'établissement] "
        f"qui se tiendra :\n\n"
        f"  Date : [date]\n"
        f"  Heure : [heure]\n"
        f"  Durée prévue : [durée]\n"
        f"  Lieu : [salle / bureau]\n\n"
        f"Ordre du jour :\n"
        f"  1. [Point 1]\n"
        f"  2. [Point 2]\n"
        f"  3. [Point 3]\n"
        f"  4. Questions diverses\n\n"
        f"Votre présence est obligatoire. En cas d'empêchement majeur et justifié, "
        f"veuillez en informer le secrétariat de direction au moins 24 heures à l'avance.\n\n"
        f"Nous vous remercions de bien vouloir préparer les éléments relevant de votre "
        f"responsabilité."
    )


def _body_F02(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Dans le cadre du cycle annuel d'évaluation professionnelle, nous vous convions "
        f"à un entretien d'évaluation qui se tiendra selon les modalités suivantes :\n\n"
        f"  Date : [date]\n"
        f"  Heure : [heure]\n"
        f"  Lieu : [bureau du coordinateur / bureau du DRH]\n"
        f"  Évaluateur : [nom et fonction]\n\n"
        f"L'ordre du jour de cet entretien portera sur les points suivants :\n"
        f"  1. Bilan de l'année scolaire écoulée (réalisations, difficultés rencontrées)\n"
        f"  2. Évaluation de l'atteinte de vos objectifs professionnels\n"
        f"  3. Analyse de vos besoins en formation et développement professionnel\n"
        f"  4. Fixation des objectifs pour l'année à venir\n"
        f"  5. Perspectives de carrière et souhaits d'évolution\n\n"
        f"Afin que cet entretien soit le plus constructif possible, nous vous invitons à "
        f"préparer une brève auto-évaluation et à rassembler tout document utile "
        f"(planifications, résultats d'élèves, rapports d'activité, formations suivies)."
    )


def _body_F05(staff, today):
    return (
        f"NOTE DE SERVICE N° [numéro]/[année]\n\n"
        f"Destinataires : [Tout le personnel / Personnel enseignant / Programme / Campus]\n"
        f"Émetteur : Le Chef d'Établissement\n"
        f"Date : {today}\n"
        f"Objet : [Objet de la note]\n\n"
        f"[Corps de la note — description détaillée de la décision, de la procédure ou de "
        f"l'information]\n\n"
        f"La présente note de service entre en vigueur à compter de sa date de diffusion. "
        f"Elle sera affichée sur les tableaux prévus à cet effet et tenue à disposition du "
        f"personnel au secrétariat de direction.\n\n"
        f"Pour toute question relative à la présente note, les personnels sont invités à "
        f"s'adresser à leur supérieur hiérarchique direct.\n\n"
        f"Le Chef d'Établissement\n"
        f"{_ECOLE['nom']}"
    )


def _body_F07(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Dans le cadre de [la réorganisation pédagogique / de l'ouverture de nouvelles classes "
        f"/ de la réponse à un besoin identifié], nous vous informons de votre changement "
        f"d'affectation à compter du [date].\n\n"
        f"Nouvelle affectation :\n"
        f"  • Campus : [campus]\n"
        f"  • Programme : [PYP / MYP / DP / Programme national]\n"
        f"  • Niveau(x) / Classe(s) : [détail]\n"
        f"  • Matière(s) : [matière(s)]\n\n"
        f"Cette décision prend en compte les besoins de l'établissement et votre profil "
        f"professionnel. Nous sommes convaincus que vous saurez vous y épanouir.\n\n"
        f"Votre supérieur hiérarchique et le coordinateur de programme se tiennent à votre "
        f"disposition pour préparer cette transition dans les meilleures conditions."
    )


def _body_F10(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous attirons votre attention sur une échéance administrative importante vous "
        f"concernant :\n\n"
        f"  Document / Autorisation concerné(e) : [permis de travail / visa / certification / "
        f"  pièce d'identité / autre]\n"
        f"  Date d'expiration : [date]\n"
        f"  Délai restant : [X] jours\n\n"
        f"Nous vous invitons à entreprendre sans délai les démarches de renouvellement "
        f"nécessaires. Le secrétariat de direction peut vous fournir les documents "
        f"administratifs requis (attestation d'emploi, certificat de travail, etc.).\n\n"
        f"Pour rappel, le défaut de présentation d'un document en cours de validité pourrait "
        f"avoir des conséquences sur votre situation contractuelle.\n\n"
        f"Nous restons à votre disposition pour toute question."
    )


# ════════════════════════════════════════════════════════════════════
# Famille G — Recrutement
# ════════════════════════════════════════════════════════════════════

def _body_G01(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous accusons réception de votre candidature pour le poste de [poste] "
        f"au sein de l'{_ECOLE['nom']}, reçue le [date].\n\n"
        f"Nous vous remercions de l'intérêt que vous portez à notre établissement. "
        f"Votre dossier est en cours d'examen par notre commission de recrutement.\n\n"
        f"Nous ne manquerons pas de vous informer des suites qui y seront données "
        f"dans les meilleurs délais.\n\n"
        f"Dans l'intervalle, nous vous prions d'agréer, Madame, Monsieur, "
        f"l'expression de nos salutations distinguées."
    )


def _body_G02(staff, today):
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à l'examen de votre candidature pour le poste de {poste}, nous avons le "
        f"plaisir de vous convier à un entretien de recrutement qui se tiendra :\n\n"
        f"  Date : [date]\n"
        f"  Heure : [heure]\n"
        f"  Durée prévue : [durée]\n"
        f"  Lieu : {_ECOLE['nom']}, {_ECOLE['adresse']}\n"
        f"  Interlocuteur(s) : [nom et fonction]\n\n"
        f"Nous vous remercions de bien vouloir confirmer votre présence par email à "
        f"{_ECOLE['email']} ou par téléphone au {_ECOLE['tel']}, au plus tard le [date].\n\n"
        f"Nous vous prions de vous munir des documents suivants :\n"
        f"  • Pièce d'identité en cours de validité\n"
        f"  • Originaux de vos diplômes et certifications\n"
        f"  • Attestations de travail antérieures\n"
        f"  • Tout document ou portfolio que vous jugerez utile\n\n"
        f"Nous nous réjouissons de faire votre connaissance."
    )


def _body_G04(staff, today):
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous avons bien reçu votre candidature pour le poste de [poste] et vous remercions "
        f"de l'intérêt que vous portez à l'{_ECOLE['nom']}.\n\n"
        f"Après un examen attentif de votre dossier par notre commission de recrutement, nous "
        f"sommes au regret de vous informer que votre candidature n'a pas été retenue pour "
        f"ce poste.\n\n"
        f"Cette décision ne remet nullement en cause la qualité de votre parcours académique "
        f"et professionnel, d'autres candidatures correspondant davantage au profil recherché "
        f"pour ce poste spécifique.\n\n"
        f"Nous conservons votre dossier dans nos archives et n'hésiterons pas à vous "
        f"recontacter si une opportunité correspondant à votre profil se présentait à l'avenir, "
        f"sauf avis contraire de votre part.\n\n"
        f"Nous vous souhaitons pleine réussite dans vos recherches et dans la poursuite "
        f"de votre carrière."
    )


def _body_G05(staff, today):
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Suite à votre entretien du [date] avec notre commission de recrutement, nous avons "
        f"le plaisir de vous proposer le poste de {poste} au sein de l'{_ECOLE['nom']}.\n\n"
        f"Les conditions de cette proposition sont les suivantes :\n\n"
        f"  1. Type de contrat : [CDI / CDD]\n"
        f"  2. Date de prise de fonction souhaitée : [date]\n"
        f"  3. Rémunération brute mensuelle : [montant] francs CFA\n"
        f"  4. Avantages complémentaires :\n"
        f"     • Indemnité de logement : [montant] F CFA / mois\n"
        f"     • Indemnité de transport : [montant] F CFA / mois\n"
        f"     • Prime de bilan annuelle\n"
        f"     • [Autres avantages : scolarité enfants, assurance santé, etc.]\n"
        f"  5. Période d'essai : [durée]\n"
        f"  6. Lieu de travail : [campus]\n\n"
        f"Cette proposition est valable jusqu'au [date]. Nous vous remercions de nous faire "
        f"part de votre décision par écrit avant cette date.\n\n"
        f"Dans l'attente de votre réponse, nous restons à votre disposition pour toute "
        f"information complémentaire."
    )


def _body_G06(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur,\n\n"
        f"Nous avons le plaisir de vous confirmer votre engagement au poste de {poste} "
        f"au sein de l'{_ECOLE['nom']}, suite à votre acceptation de notre proposition "
        f"d'embauche en date du [date].\n\n"
        f"Pour rappel, votre prise de fonction est fixée au [date]. Nous vous invitons "
        f"à vous présenter ce jour à [heure] au Bureau du Directeur pour :\n\n"
        f"  • La signature de votre contrat de travail\n"
        f"  • La remise des documents constitutifs de votre dossier administratif\n"
        f"  • La présentation de l'établissement et de votre équipe\n"
        f"  • La remise de vos outils de travail\n\n"
        f"Vous trouverez ci-joint la liste des documents à fournir impérativement le jour "
        f"de votre arrivée.\n\n"
        f"Nous nous réjouissons de vous accueillir et vous souhaitons la bienvenue."
    )


# ════════════════════════════════════════════════════════════════════
# Famille H — Demandes employé (montantes)
# ════════════════════════════════════════════════════════════════════

def _body_H01(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    sid = _s(staff, "id", "[Matricule]")
    poste = _s(staff, "professional_category", "[Poste]")
    return (
        f"Objet : Demande de congé annuel\n\n"
        f"Madame, Monsieur le Directeur,\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, exerçant les fonctions de {poste} "
        f"au sein de l'{_ECOLE['nom']}, ai l'honneur de solliciter de votre bienveillance "
        f"un congé annuel pour la période suivante :\n\n"
        f"  Du : [date début]\n"
        f"  Au : [date fin]\n"
        f"  Soit : [X] jours ouvrés\n\n"
        f"Je m'engage à reprendre mon service le [date de reprise] aux horaires habituels.\n\n"
        f"Durant mon absence, la continuité du service sera assurée par [nom du collègue / "
        f"dispositions prises], après concertation avec mon supérieur hiérarchique.\n\n"
        f"Dans l'attente d'une suite favorable, je vous prie d'agréer, Madame, Monsieur "
        f"le Directeur, l'expression de mes salutations distinguées.\n\n"
        f"Fait à [Lieu], le [date]\n\n"
        f"Signature de l'employé"
    )


def _body_H06(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    sid = _s(staff, "id", "[Matricule]")
    poste = _s(staff, "professional_category", "[Poste]")
    return (
        f"Objet : Demande d'autorisation d'absence\n\n"
        f"Madame, Monsieur le Directeur,\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, {poste}, sollicite une autorisation "
        f"d'absence exceptionnelle pour le [date] de [heure début] à [heure fin].\n\n"
        f"Motif de cette demande : [rendez-vous administratif / rendez-vous médical / "
        f"convocation officielle / obligation familiale impérieuse].\n\n"
        f"Je m'engage à récupérer les heures d'absence selon les modalités convenues avec "
        f"mon supérieur hiérarchique.\n\n"
        f"Dans l'attente de votre accord, je vous prie d'agréer, Madame, Monsieur "
        f"le Directeur, l'expression de mes salutations distinguées.\n\n"
        f"Signature de l'employé"
    )


def _body_H12(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    sid = _s(staff, "id", "[Matricule]")
    poste = _s(staff, "professional_category", "[Poste]")
    return (
        f"Objet : Lettre de démission\n\n"
        f"Madame, Monsieur le Directeur,\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, exerçant les fonctions de {poste} "
        f"au sein de l'{_ECOLE['nom']}, ai l'honneur de vous présenter ma démission de mes "
        f"fonctions, à compter du [date].\n\n"
        f"Conformément aux dispositions de mon contrat de travail et du Code du Travail, "
        f"j'effectuerai mon préavis d'une durée de [X semaines / mois] à partir de la "
        f"date de réception de la présente.\n\n"
        f"Je tiens à vous exprimer ma profonde gratitude pour la confiance que vous m'avez "
        f"accordée durant ces [X] années passées au sein de votre établissement, ainsi que "
        f"pour l'expérience professionnelle et humaine que j'y ai acquise.\n\n"
        f"Je reste naturellement à votre disposition pour assurer une passation de mes "
        f"dossiers dans les meilleures conditions.\n\n"
        f"Je vous prie d'agréer, Madame, Monsieur le Directeur, l'expression de mes "
        f"salutations distinguées et de mon profond respect.\n\n"
        f"Fait à [Lieu], le [date]\n\n"
        f"Signature de l'employé"
    )


def _body_H16(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    sid = _s(staff, "id", "[Matricule]")
    poste = _s(staff, "professional_category", "[Poste]")
    return (
        f"Objet : Recours contre une sanction disciplinaire\n\n"
        f"Madame, Monsieur le Directeur,\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, {poste}, conteste par la présente "
        f"la sanction disciplinaire de [avertissement / blâme / mise à pied] qui m'a été "
        f"notifiée par votre courrier en date du [date].\n\n"
        f"Les motifs de ma contestation sont les suivants :\n"
        f"  1. [Argument 1]\n"
        f"  2. [Argument 2]\n"
        f"  3. [Argument 3]\n\n"
        f"Je sollicite respectueusement le réexamen de cette sanction et la communication "
        f"de l'ensemble des pièces de mon dossier.\n\n"
        f"Je vous prie d'agréer, Madame, Monsieur le Directeur, l'expression de mes "
        f"salutations distinguées.\n\n"
        f"Signature de l'employé"
    )


def _body_H18(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    sid = _s(staff, "id", "[Matricule]")
    poste = _s(staff, "professional_category", "[Poste]")
    return (
        f"Objet : Demande d'avance sur salaire\n\n"
        f"Madame, Monsieur le Directeur,\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, {poste}, ai l'honneur de solliciter "
        f"de votre bienveillance une avance sur salaire d'un montant de [montant en chiffres] "
        f"francs CFA ([montant en lettres] francs CFA).\n\n"
        f"Cette demande est motivée par les circonstances suivantes : [décrire précisément "
        f"le motif : dépenses médicales imprévues, frais de scolarité, décès familial, etc.].\n\n"
        f"Je propose un échelonnement du remboursement sur [X] mensualités de [montant] francs "
        f"CFA, à compter du salaire du mois de [mois] [année].\n\n"
        f"Je vous remercie par avance de l'attention que vous porterez à ma demande et reste "
        f"à votre disposition pour tout complément d'information.\n\n"
        f"Je vous prie d'agréer, Madame, Monsieur le Directeur, l'expression de mes "
        f"salutations distinguées.\n\n"
        f"Signature de l'employé"
    )


def _body_H20(staff, today):
    nom = _s(staff, "full_name", "M./Mme [Nom]")
    sid = _s(staff, "id", "[Matricule]")
    return (
        f"Objet : Déclaration de changement de coordonnées\n\n"
        f"Madame, Monsieur le Directeur,\n\n"
        f"Je soussigné(e), {nom}, matricule n°{sid}, vous prie de bien vouloir prendre "
        f"note de mes nouvelles coordonnées :\n\n"
        f"  Ancienne adresse : [adresse]\n"
        f"  Nouvelle adresse : [adresse]\n\n"
        f"  Ancien téléphone : [téléphone]\n"
        f"  Nouveau téléphone : [téléphone]\n\n"
        f"  Nouvel email : [email]\n\n"
        f"  Situation familiale : [inchangée / nouvelle situation]\n"
        f"  Personne à contacter en cas d'urgence : [nom] — [téléphone]\n\n"
        f"Je vous remercie de bien vouloir mettre à jour mon dossier administratif.\n\n"
        f"Signature de l'employé"
    )


# ════════════════════════════════════════════════════════════════════
# Famille I — IB / International
# ════════════════════════════════════════════════════════════════════

def _body_I01(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    date_emb = _s(staff, "hire_date", _s(staff, "date_entree", "[date]"))
    return (
        f"ATTESTATION D'ENSEIGNEMENT — PROGRAMME DU BACCALAURÉAT INTERNATIONAL\n\n"
        f"Je soussigné, {_ECOLE['directeur']}, Chef d'Établissement de l'{_ECOLE['nom']}, "
        f"établissement autorisé par l'Organisation du Baccalauréat International (IBO) "
        f"à dispenser le(s) programme(s) [PYP / MYP / DP / CP], atteste que :\n\n"
        f"  {nom}\n\n"
        f"enseigne le(s) programme(s) IB suivant(s) au sein de notre établissement depuis "
        f"le {date_emb} :\n\n"
        f"  • [Programme 1] — Matière(s) : [matière(s)] — Niveau(x) : [niveau(x)]\n"
        f"  • [Programme 2] — Matière(s) : [matière(s)] — Niveau(x) : [niveau(x)]\n\n"
        f"Durant cette période, l'intéressé(e) a participé aux ateliers de formation IB "
        f"suivants : [Catégorie 1 / Catégorie 2 / Catégorie 3] en [année(s)].\n\n"
        f"La présente attestation est délivrée pour servir et valoir ce que de droit, "
        f"notamment dans le cadre de la candidature de l'intéressé(e) à l'IB Educator "
        f"Certificate (IBEC).\n\n"
        f"Fait à Lomé, le {today}"
    )


def _body_I02(staff, today):
    nom = _s(staff, "full_name", "[Nom]")
    poste = _s(staff, "professional_category", "[poste]")
    return (
        f"Madame, Monsieur le Chef d'Établissement,\n\n"
        f"Je suis heureux de recommander {nom} qui exerce les fonctions de {poste} "
        f"au sein de l'{_ECOLE['nom']}, école du monde de l'IB.\n\n"
        f"Durant [X] années au sein de notre établissement, {nom} a démontré :\n\n"
        f"  • Une excellente maîtrise du programme [PYP / MYP / DP / CP] de l'IB, "
        f"    incluant la planification des unités de recherche, l'évaluation critériée "
        f"    et la mise en œuvre des approches de l'apprentissage\n"
        f"  • Un engagement remarquable dans le développement professionnel continu "
        f"    (formations IB Cat. [1/2/3], participation aux communautés de pratique)\n"
        f"  • Une contribution significative à [la planification collaborative / "
        f"    l'encadrement du Projet Personnel / du Mémoire / de l'Étude du Milieu / "
        f"    du Projet de Créativité-Activité-Service]\n\n"
        f"[Paragraphe personnalisé sur les qualités spécifiques du candidat]\n\n"
        f"Je recommande {nom} sans aucune réserve pour tout poste d'enseignement "
        f"au sein d'une école du monde de l'IB."
    )


# ════════════════════════════════════════════════════════════════════
# Famille J — Syndical et instances représentatives
# ════════════════════════════════════════════════════════════════════

def generate_docx(staff: dict | None, code: str, objet: str, ref: str,
                  campus: dict | None = None, output_path: str = "",
                  template: dict | None = None, body_override: str | None = None) -> str:
    """Génère un fichier .docx avec logo, en-tête formaté et corps du courrier.

    body_override : si fourni (ex. corps édité dans le dialogue de génération),
    utilise ce texte plutôt que build()/render_body().
    """
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    e = _get_ecole(campus)
    today = date.today().strftime("%d/%m/%Y")

    # Corps du courrier
    if body_override is not None:
        body_only = body_override
    else:
        body_only = render_body(staff, code, template=template, campus=campus)

    doc = Document()

    # ── Marges ──
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.0)

    # ── Logo en haut à gauche ──
    logo_path = e.get("logo", "")
    if logo_path and os.path.exists(logo_path):
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p_logo.add_run()
        run.add_picture(logo_path, width=Inches(1.6))

    # ── En-tête établissement ──
    p_nom = doc.add_paragraph()
    p_nom.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p_nom.add_run(e["nom"])
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(0x1B, 0x1B, 0x1F)

    p_adr = doc.add_paragraph()
    p_adr.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p_adr.add_run(f"{e['adresse']}  —  Tél : {e['tel']}  —  {e['email']}")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x5F, 0x5F, 0x5F)

    # ── Séparateur ──
    doc.add_paragraph("─" * 70)

    # ── Réf & Date ──
    p_ref = doc.add_paragraph()
    run = p_ref.add_run(f"Réf : {ref}")
    run.font.size = Pt(10)
    p_date = doc.add_paragraph()
    run = p_date.add_run(f"Date : {today}")
    run.font.size = Pt(10)

    doc.add_paragraph()

    # ── Destinataire ──
    nom = _s(staff, "full_name", "[Nom complet]")
    poste = _s(staff, "professional_category", "[Poste]")
    sid = _s(staff, "id", "[Matricule]")
    p_dest = doc.add_paragraph()
    p_dest.add_run("À l'attention de :\n").bold = True
    p_dest.add_run(f"  {nom}\n  {poste}\n  Matricule : {sid}")

    doc.add_paragraph()

    # ── Objet ──
    p_obj = doc.add_paragraph()
    run = p_obj.add_run(f"Objet : {objet}")
    run.bold = True
    run.underline = True
    run.font.size = Pt(11)

    doc.add_paragraph()

    # ── Corps du courrier — chaque paragraphe = un paragraphe DOCX ──
    for para_text in body_only.split("\n\n"):
        para_text = para_text.strip()
        if not para_text:
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.3
        run = p.add_run(para_text)
        run.font.size = Pt(11)

    doc.add_paragraph()

    # ── Pied ──
    doc.add_paragraph("─" * 70)
    p_close = doc.add_paragraph()
    run = p_close.add_run(
        "Veuillez agréer, Madame, Monsieur, l'expression de mes salutations distinguées.")
    run.font.size = Pt(11)

    doc.add_paragraph()
    p_sig = doc.add_paragraph()
    run = p_sig.add_run(e["directeur"])
    run.bold = True
    run.font.size = Pt(11)
    p_sig_nom = doc.add_paragraph()
    run = p_sig_nom.add_run(e["nom"])
    run.font.size = Pt(11)

    doc.add_paragraph()
    p_copy = doc.add_paragraph()
    run = p_copy.add_run("Copie : Dossier de l'employé, Direction")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x5F, 0x5F, 0x5F)

    doc.save(output_path)
    return output_path


def _body_J01(staff, today):
    return (
        f"Madame, Monsieur le Délégué du Personnel,\n\n"
        f"Conformément aux dispositions du Code du Travail relatives aux institutions "
        f"représentatives du personnel, vous êtes convoqué(e) à la réunion périodique "
        f"des Délégués du Personnel qui se tiendra :\n\n"
        f"  Date : [date]\n"
        f"  Heure : [heure]\n"
        f"  Lieu : [salle de réunion]\n"
        f"  Durée prévue : [durée]\n\n"
        f"Ordre du jour :\n"
        f"  1. Examen des réclamations individuelles et collectives\n"
        f"  2. Conditions de travail, hygiène et sécurité\n"
        f"  3. Emploi et effectifs\n"
        f"  4. Formation professionnelle\n"
        f"  5. Œuvres sociales\n"
        f"  6. Questions diverses\n\n"
        f"Vous voudrez bien nous communiquer, au moins 48 heures avant la réunion, "
        f"les points que vous souhaitez voir inscrits à l'ordre du jour.\n\n"
        f"Nous vous remercions de bien vouloir confirmer votre présence."
    )
