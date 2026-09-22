-- Migration 2026-09-22 — LarcConfig : piste linguistique croisée
--
-- Ajoute un indicateur booléen fiable pour marquer un slot de matière-classe
-- (larcauth_classroom_termsubject) enseigné dans l'autre langue que celle du
-- programme de la classe (ex. une matière anglophone dans une classe PEI).
--
-- Contexte : le plan 2026-09-19 supposait que la langue se lisait sur le
-- programme parent de la matière (fk_language_id via subjectgroup). Vérifié
-- faux le 2026-09-22 : les 62 slots concernés (15 libellés distincts, ex.
-- « Sciences (En) », « Histoire(FR) », « Gestion (Fr) SL ») ont tous le même
-- fk_language_id que le reste de leur classe — seul le texte libre du
-- libellé porte l'information, avec 5 variantes de casse/espacement.
-- Au lieu de parser ce texte (fragile), on capture l'intention dans une
-- colonne dédiée, au niveau du slot — même principe que `niv_sup`, qui est
-- déjà un indicateur de slot indépendant de la matière-modèle (levelsubject).
--
-- Réversible : DROP COLUMN larcauth_classroom_termsubject.cross_track;

BEGIN;

ALTER TABLE larcauth_classroom_termsubject
    ADD COLUMN cross_track boolean NOT NULL DEFAULT FALSE;

-- Backfill ponctuel : bascule les 62 slots déjà marqués par convention de
-- libellé. Un seul nettoyage à la création de la colonne — ensuite la case
-- sera éditée directement dans LarcConfig (Onglet A), plus besoin du texte.
UPDATE larcauth_classroom_termsubject
SET cross_track = TRUE, updated = NOW()
WHERE label ~* '\(\s*(en|fr)\s*\)';

-- Vérification : doit donner 62.
SELECT COUNT(*) AS flagged FROM larcauth_classroom_termsubject WHERE cross_track = TRUE;

COMMIT;
