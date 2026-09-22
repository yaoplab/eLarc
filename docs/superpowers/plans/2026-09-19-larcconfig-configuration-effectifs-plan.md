# Plan — LarcConfig : configuration des classes, matières et inscriptions élèves (PEI / DP)

Date : 2026-09-19 — mis à jour le 2026-09-22
Statut : **Phase 0 (socle & diagnostic) et Phase 1 (onglet A) livrées et testées** (cf. section 7). D1, D4, D11 tranchés le 2026-09-22 (voir ci-dessous) ; D2-D3, D5, D7-D10 restent à valider avant la Phase 2 (grille élèves).

**D11 tranché (2026-09-22)** : en PEI comme en DP, un groupe de matières accepte **0, 1 ou 2 matières** (jamais plus) — pas d'obligation d'en avoir une. Règle DP durcie : voyant vert/rouge = 6 matières + groupes 1-5 couverts **et exactement 3 Sup (NS) + 3 niveau moyen (NM)** (remplace l'avertissement souple « 3-4 NS » de la section 4/D3 ci-dessous).

Périmètre demandé : *mettre à jour* (jamais créer, jamais supprimer) la configuration PEI et DP, **par trimestre**.

---

## 1. Principes

1. **Principe gabarit (règle du monorepo).** Toutes les lignes existent déjà. Le système ne fait que des `UPDATE`. « Supprimer » = `enabled = FALSE`. Aucun `INSERT`/`DELETE` dans ce module (garde-fou testé, cf. 6.5).
2. **Tout est scopé par trimestre.** Aucune écriture sans (classe, trimestre) explicite — le `WHERE` de chaque `UPDATE` porte toujours ce périmètre côté serveur, pas seulement dans l'UI.
3. **Prévisualiser puis appliquer.** Toute opération en lot affiche ce qu'elle va changer (« 14 inscrits, 2 déjà inscrits ») avant de s'exécuter.
4. **Tracer.** Les 5 tables touchées ont déjà un trigger `trg_audit_*` → il suffit d'attacher le contexte d'audit (`audit_context.attach(conn)`) pour que `audit_log` sache *qui* a changé *quoi*.
5. **Ne rien corriger en silence.** Les anomalies sont listées avec une correction *proposée* ; l'utilisateur valide.

---

## 2. État des lieux (mesuré en base le 2026-09-19)

### 2.1 Structure réelle

| Besoin exprimé | Table réelle | Colonnes à mettre à jour | Volumétrie |
|---|---|---|---|
| Classes | `larcauth_classroom` | `label`, `enabled` | 60 classes dont **30 désactivées** (gabarits, moitié par programme) : DP 4 actives + 4 inactives, PEI 5+5, MYP 5+5, PP 8+8, PYP 8+8 |
| Matières par classe | `larcauth_classroom_termsubject` | `label`, `enabled` (+ lecture : `niv_sup`, `couleur`, `fk_teacher_id`, `fk_levelsubject_id`) | 3 trimestres × ~41 slots par classe DP (≈ 26 par classe PEI) ; ~670 actives sur ~3 400 |
| Matière par élève | `larcauth_learner_has_termsubject` (**table de base** ; les tables `learnerpei_…`/`learnerdp_…` n'ont **pas** de colonne `enabled`, elles ne portent que les notes, liées par `learner_has_termsubject_ptr_id`) | `enabled` | 136 320 lignes, 6 207 actives — toutes pré-créées |
| Feu vert « élève vérifié » | `larcauth_student.validation` (JSONB **déjà utilisé par LarcSecretaire**) | nouvelle clé (cf. D2) | 2 400 élèves, 406 actifs |
| Groupes de matières | `larcauth_subjectgroup` (46 lignes) ; `larcauth_levelsubject.fk_subjectgroup_id` (568 matières possibles) | lecture seule | DP : 6 groupes (`nr_group_in_pgm` 1→6, Arts = 6) |

### 2.2 Ce que les données montrent du modèle DP

Un élève DP a exactement **6 matières activées** par trimestre parmi ~41 slots (vérifié : les 53 élèves DP actifs en T1 ont tous exactement 6). Exemple réel (élève 231101) : Français NM (groupe 1), Maths NM (2), Économie NS + Gestion NS (groupe 3), Biologie NM (4), Anglais NS (5) — **pas d'Arts** : la 6ᵉ matière est une 2ᵉ matière du groupe 3. C'est exactement la règle « Arts permet toutes les autres » : la 6ᵉ colonne n'est pas « le groupe Arts », c'est « Arts *ou* une matière supplémentaire de n'importe quel groupe ». NM/NS (`niv_sup` False/True) = variantes distinctes de la même matière, chacune son propre slot.

### 2.3 Anomalies existantes (le « il y a encore des corrections/suppressions à faire »)

| # | Anomalie | Nombre |
|---|---|---|
| A1 | Inscription **active** sur une matière-classe **désactivée** | 280 (T1 : 158, T2 : 9, T3 : 113) |
| A2 | Inscription active d'un élève **désactivé** (résidus d'années précédentes) | 1 245 |
| A3 | Matière-classe **active sans aucun élève inscrit** | 251 (T1 : 92, T2 : 11, T3 : 148) |
| A4 | Matière-classe active dont le `label` ≠ celui de sa `levelsubject` | 87 |
| A5 | Matière-classe active **sans enseignant réel** (`fk_teacher_id = 1000`, « en attente ») | 223 |
| A6 | Élèves actifs dont les matières diffèrent entre T1 et T2 | 36 (peut être légitime) |
| ✓ | Inscription dans une classe autre que celle de l'élève | 0 |
| ✓ | Élèves DP actifs à ≠ 6 matières (T1) | 0 |

Ces chiffres nourrissent directement l'onglet « Anomalies » (phase 0) : la correction se fait par `enabled = FALSE`, jamais par suppression, et **toujours après validation** (pour A1 par exemple, la bonne correction peut être de *réactiver* la matière-classe plutôt que de désinscrire les élèves).

### 2.4 Piste linguistique et couleur dans les données (vérifié le 2026-09-19, corrigé)

- **La langue est un attribut du programme parent** (`larcauth_program.fk_language_id`) : 1 = anglais (PYP, MYP, DPEn), 2 = français (PP, PEI, DPFr). Tout groupe de matières (`subjectgroup.fk_program_id`) et toute matière en héritent. **Aucune détection par libellé** (`(En)`) : le libellé n'est qu'un affichage.
- **Nombre de groupes** : **8 en PEI (FR), 8 en MYP (EN)** = 16 colonnes possibles pour un élève francophone qui panache les pistes ; 6 en DPFr, 6 en DPEn. Les groupes MYP sont les groupes 121-128, PEI 221-228 (même `nr_group_in_pgm` 1-8 des deux côtés : c'est la clé d'appariement FR↔EN d'un même groupe).
- **`couleur` est déjà la couleur du groupe** (même valeur pour toutes les matières d'un groupe), mais peut valoir la chaîne `'false'` (DP groupes 3-4 ≈ 70 slots actifs, ≈ 28 slots PEI).
- **Constat (D10 tranché)** : dans PEI-1, les matières « (En) » (Humanities, Sciences, Design, Anglais L&L) sont des slots *supplémentaires de la classe PEI* (programme 22). C'est là que s'inscrit un élève FR qui suit une matière en anglais ; les classes MYP ne reçoivent que leurs propres élèves.

---

## 3. Conception fonctionnelle

Un nouveau panneau **« Classes & matières »** dans la sidebar LarcConfig. En-tête commun : **sélecteur de trimestre (1/2/3)** + **sélecteur de classe** (groupées PEI / MYP / DPFr / DPEn). Quatre onglets.

### Onglet A — Matières de la classe (`classroom` + `classroom_termsubject`)

- Ligne classe : `label` éditable, interrupteur `enabled`. Désactiver une classe → avertissement (pas de cascade automatique : les applis filtrent déjà sur `c.enabled`).
- Tableau des slots de la classe pour le trimestre, **groupés par groupe de matières** (via `levelsubject → subjectgroup`) : `[✔ enabled] [label éditable] [NM/NS] [enseignant (lecture)] [nb élèves inscrits] [⚠]`.
- Slots génériques (« Matiere_supl… », « MatièreSupl… ») grisés et en fin de groupe : ce sont les emplacements libres à renommer/activer.
- Désactiver un slot qui a des élèves inscrits → dialogue de confirmation avec cascade proposée (« désinscrire les N élèves ») exécutée dans la **même transaction**.

### Onglet B — Élèves : **une grille unique** pour PEI/MYP et DP (`learner_has_termsubject.enabled`)

*(Révisé le 2026-09-19 : la matrice PEI « une colonne par matière » est abandonnée au profit de la même grille que le DP.)*

- **Colonnes = groupes de matières** (`subjectgroup.nr_group_in_pgm`) : 8 pour le PEI, 8 de plus pour le MYP (mêmes rangs 1-8, piste EN), 6 pour le DP (et 6 en piste EN). Par défaut la grille montre les 8 groupes du programme de la classe ; un bouton « ajouter la piste EN » affiche les 8 groupes MYP appariés par rang. Lignes = élèves actifs de la classe.
- **Cellule = 1 ou 2 matières, jamais plus de 2** (règle générale ; les autres règles seront ajoutées par l'utilisateur, cf. D11). Chaque matière est une *pastille*.
- **Deux codes visuels** sur chaque pastille :
  - **couleur du groupe** (barre gauche) — c'est la valeur `classroom_termsubject.couleur`, déjà renseignée et cohérente par groupe (PEI : Langue et littérature `#9BC6F5`, Maths `#28A745`, Individus et sociétés `#D0AA39`, Sciences `#002a9a`, Acquisition de langues `#DC3545`, EPS `#6EDB6E`, Arts et Design `#9A72FF`) ; palette de repli quand la valeur est `'false'` (D10) ;
  - **piste linguistique** : pastille **FR** ou **EN**, deux couleurs distinctes, **lue sur le programme parent de la matière** (2.4) ; Cas d'usage : une élève francophone qui suit Sciences ou Humanités **dans la piste anglophone** pour progresser en anglais — la cellule Sciences montre alors « Sciences EN » (ou « Sciences FR » + « Sciences EN » si elle suit les deux).
- **Sélecteur de cellule** : liste des matières-classe *activées* du groupe, pistes FR et EN côte à côte.
- **Ligne « Toute la classe »** en tête de grille : ajouter/retirer une pastille sur cette ligne l'applique à **tous** les élèves actifs de la classe (aperçu obligatoire : « 17 concernés, 2 déjà inscrits »). Un `UPDATE` unique, borné à la classe et au trimestre.
- Les changements sont atomiques (désactiver l'ancienne + activer la nouvelle en une seule instruction ; la connexion est en `autocommit`).

**Spécificités DP** (mêmes composants, jeu de règles différent) :
- Colonnes 1-5 = groupes 1-5 ; **colonne 6 = « Arts ou matière supplémentaire »** : liste d'Arts **∪ toutes les matières des autres groupes** (règle « Arts permet toutes les autres »).
- Lecture d'un état existant : dans chaque groupe 1-5, la première matière activée va dans sa colonne ; une 2ᵉ va en colonne 6 (cas réel de l'élève 231101 : Économie NS + Gestion NS, pas d'Arts).
- Contrôles par ligne : **6 matières** (dur), **groupes 1-5 couverts** (dur), **3 à 4 NS** (avertissement).

**Feu vert (PEI et DP)** en fin de ligne : ● gris (jamais vérifié) · ● orange (modifié depuis la vérification, ou règle non respectée) · ● vert (vérifié). « Vérifié » écrit la clé de validation (D2) ; **toute modification ultérieure des inscriptions de l'élève repasse le feu à orange** (même logique que `_invalidate_note` de LarcProf). Bandeau : « 12/15 élèves vérifiés ».

### Onglet D — Anomalies

Les contrôles A1-A6 en listes filtrables, chacun avec sa correction proposée, un aperçu du nombre de lignes touchées et un bouton « Appliquer ». Lecture seule tant que rien n'est validé.

*(Phase ultérieure : « Copier la configuration du trimestre N vers N+1 » — un `UPDATE … FROM` sur les mêmes slots, avec aperçu ; utile puisque 36 élèves seulement changent de matières entre T1 et T2.)*

---

## 4. Décisions à valider avant d'implémenter

| # | Question | Ma recommandation |
|---|---|---|
| **D1** | ~~Clé de trimestre~~ **Tranché le 2026-09-19** : il n'y a que **3 trimestres configurables ; le 4ᵉ correspond aux vacances** (rien à configurer). `fk_term_id ∈ {1,2,3}` = trimestres 1, 2, 3, réutilisés d'une année à l'autre (principe gabarit). Reste à corriger à part `LarcCommon/auth.py::_load_active_term` (`LIMIT 1` sans `ORDER BY`). | Constante unique `TERM_SLOTS = {1: 1, 2: 2, 3: 3}` ; le sélecteur de trimestre n'a que 3 entrées. |
| **D2** | **Où stocker le feu vert ?** (a) clé JSONB `validation.matieres.<trimestre> = {at, by, ok}` ; (b) nouvelle colonne booléenne `student_configured`. | **(a)** : aucune modification de schéma, même convention que `photo/parent/email/dossier` de LarcSecretaire (qui a lui-même ajouté la colonne `validation`), porte le *qui/quand*, et **supporte « par trimestre »** (une colonne booléenne ne le peut pas). |
| **D3** | Règles DP : lesquelles sont **bloquantes** pour le feu vert ? | Dur : exactement 6 matières + groupes 1-5 couverts. Avertissement : 3-4 NS. |
| **D4** | ~~PEI : deux matières dans le même groupe~~ **Tranché** : 1 ou 2 matières par groupe est *normal* (piste FR + piste EN, cf. section 3). | Maximum 2 par groupe ; les autres règles arrivent (D11). |
| **D5** | Désactiver une matière-classe qui a des inscrits : bloquer, ou proposer la cascade ? | Cascade proposée avec confirmation. |
| **D6** | Périmètre programmes. | PEI, MYP, DPFr, DPEn. PP/PYP hors périmètre. |
| **D7** | Qui a le droit d'utiliser ce panneau (LarcConfig est-il déjà réservé aux admins) ? Faut-il une période de verrouillage (après les bulletins) ? | À préciser ; verrouillage = phase ultérieure. |
| **D8** | Enseignant par matière-classe (`fk_teacher_id`, 223 « en attente ») : dans le périmètre ? | Lecture seule pour l'instant ; édition = extension simple ensuite. |
| **D9** | **Quel libellé fait foi à l'affichage ?** LarcProf (`main_data.py`) affiche `levelsubject.label`, pas `classroom_termsubject.label`. Modifier ce dernier n'aurait donc aucun effet visible chez les profs. | À vérifier appli par appli avant de promettre « les noms par groupe de matières » ; peut nécessiter d'aligner LarcProf. |
| **D10** | ~~Reconnaître la piste FR/EN~~ **Simplifié (2026-09-20)** : FR et EN passent par la **même table** `learner_has_termsubject` ; l'inscription = `UPDATE enabled` sur la ligne (élève × matière-classe), sans logique de langue. Aucune inscription ne traverse les classes (mesuré). Couleur de groupe : `couleur` si valide, sinon palette par rang de groupe. | La pastille FR/EN est décorative (programme parent), non bloquante et optionnelle. |
| **D11** | **Règles d'inscription** (par programme) : l'utilisateur les détaillera. | `enrolment_rules.py` les porte sous forme d'une liste de règles déclaratives (id, sévérité dure/avertissement, fonction pure) — en ajouter une = ajouter une entrée + un test, sans toucher à l'UI. Règle déjà connue : max 2 matières par groupe. |

---

## 5. Impacts en aval (à traiter, pas seulement à noter)

1. **LarcProf ne tient pas compte de l'inscription élève.** Il charge les élèves d'une matière par `s.s_classroom_id = ?` (`views/main_data.py:177`) — toute la classe — et n'utilise jamais `learner_has_termsubject.enabled`. Pour le DP (où « Économie NS » n'est suivie que par quelques élèves) la configuration ne servira à rien tant que LarcProf ne filtre pas. Il faudra : recopier `lht.enabled` dans la base locale au seed (`sqlite_init.py:614/631`), l'inclure dans la synchro, et filtrer les rosters. C'est une **phase à part**, mais c'est la raison d'être de tout ce système.
2. **Django / cohérence des horodatages.** Le schéma `larcauth_*` vient de Django ; aucun trigger `BEFORE` ne met `updated` à jour → chaque `UPDATE` doit poser `updated = NOW()` explicitement.
3. **LarcSecretaire** lit `validation->'<clé>'->>'ok'` pour ses tableaux de bord : une clé `matieres` supplémentaire est invisible pour lui (à vérifier que son bandeau de validation n'énumère pas « toutes » les clés).
4. **LarcConfig lui-même** : le KPI « matières par classe » de l'accueil (`get_stats`) compte `classroom_termsubject.enabled` — il évoluera avec la configuration (voulu).
5. **Synchro cloud** : ces tables n'ont pas de colonnes `sync_version`/`synced_at` ; vérifier le comportement de LarcCloudSync sur des `UPDATE` de masse.

---

## 6. Conception technique

### 6.1 Fichiers (chacun < 500 lignes, limite du monorepo : 1 000)

```
LarcConfig/
  common/
    enrolment_rules.py     # logique métier PURE (aucun Qt, aucun SQL) : lecture 6 colonnes DP,
                           # contrôles (6 matières, groupes couverts, NS), tri-états, diff
    db_enrolment.py        # lecture (classes, slots, matrice, anomalies) + écritures UPDATE-only
  views/
    panel_effectifs.py     # conteneur : en-tête trimestre/classe + onglets
    effectifs_classes.py   # onglet A
    effectifs_grille.py    # onglet B : grille élèves × groupes (PEI/MYP et DP, jeux de règles distincts)
    effectifs_anomalies.py # onglet D
  tests/
    test_enrolment_rules.py
    test_db_enrolment.py
```
`db_access.py` (590 l.) n'est pas gonflé : le nouveau code vit dans son propre module.

### 6.2 Règles d'écriture (toutes les fonctions de `db_enrolment.py`)

- Contexte d'audit attaché avant chaque écriture (`refresh(); attach(conn)` — le même correctif que celui appliqué à LarcSecretaire) ; jamais de `SET LOCAL` (no-op sous autocommit).
- `updated = NOW()` posé explicitement.
- **Périmètre dans le `WHERE`** : les `UPDATE` d'inscription joignent toujours `classroom_termsubject` sur `fk_classroom_id` **et** `fk_term_id`, et `student` sur `s_classroom_id` — une erreur d'UI ne peut pas déborder sur une autre classe/un autre trimestre.
- Opérations multi-lignes (échange de matière DP, cascade de désactivation) : une instruction unique ou `autocommit = False` + `commit`/`rollback` (on ne laisse jamais un état à moitié appliqué — même précaution que `activate_event_type`).
- Retour = nombre de lignes réellement modifiées (`rowcount`) ; l'UI l'affiche (« 14 modifiées »).
- Erreurs : `except Exception` + `log_error` + `get_reporter().report_exception()` (les `except:` nus ont été retirés de `db_access.py` — ne pas les réintroduire).

### 6.3 UI

phibuilder uniquement (`theme=theme_manager.phi_theme`), tokens `ds.*` (zéro hardcoding), `@safe_slot` sur tous les slots, réactivité thème (`_restyle`), cases à cocher via `Qt.ItemIsUserCheckable` (comme `panel_types.py`, pas de `QCheckBox` brut), sélecteurs de cellule DP en `M3ComboBox`. Aucune couleur `p.primary` sur `p.surface`, aucun `text_soft` inline (linters D5/D8).

### 6.4 Trimestre

Une constante unique (`TERM_SLOTS = {1: 1, 2: 2, 3: 3}`) porte le mapping trimestre affiché → `fk_term_id` (D1 tranché : 3 trimestres, le 4ᵉ = vacances).

### 6.5 Tests

- **Règles pures** (`enrolment_rules.py`) : table de cas — élève 231101 (2ᵉ matière du groupe 3, pas d'Arts) ; élève avec Arts ; 5 matières ; groupe 4 non couvert ; 2 NS / 5 NS.
- **SQL** (curseur simulé, même patron que `test_db_access_event_types.py`) : chaque écriture contient le périmètre classe+trimestre, pose `updated`, et **aucun `INSERT`/`DELETE`** n'apparaît dans le module (test qui parcourt le source).
- **Intégration lecture seule** contre la vraie base (ignorée si indisponible) : les 6 contrôles d'anomalies retrouvent les nombres de la section 2.3.
- Vérification visuelle avec un compte de test (l'instance DP de `olgaadja@…` est déjà prête côté LarcProf).

---

## 7. Phasage

| Phase | Contenu | Critère d'acceptation |
|---|---|---|
| **0 — Socle & diagnostic** ✅ 2026-09-22 | `enrolment_rules.py`, `db_enrolment.py` (A1-A6), `TERM_SLOTS`, onglet **Anomalies en lecture seule** | Retrouve A1-A6 (⚠ A2/A6 ont grossi depuis le 19/09 à cause de la cascade de rentrée — mesure vivante, pas un invariant gelé) ; 26 tests verts ; aucune écriture possible |
| **1 — Classes & matières de classe** ✅ 2026-09-22 | Onglet A (`effectifs_classes.py`), écritures `label`/`enabled` classe+slot, cascade confirmée, en-tête commun programme/classe/trimestre dans `panel_effectifs.py` | 81 tests verts (dont intégration lecture live) ; désactiver un slot inscrit propose la cascade ; `WHERE` toujours scopé classe+trimestre ; contexte d'audit attaché (`audit_context.attach`) |
| **2 — Grille commune + PEI** | Onglet B : grille par groupes, pastilles couleur de groupe + FR/EN, ligne « Toute la classe », aperçu, règle « max 2 par groupe » | Affecter à toute la classe = 1 `UPDATE` ; une élève PEI peut avoir Sciences FR et/ou EN ; aperçu correct |
| **3 — DP + feu vert** | Jeu de règles DP (colonne 6/Arts, NS), feu vert par trimestre (PEI et DP) | Les 53 élèves DP actuels s'affichent avec 6/6 ; échange de matière atomique ; modification → feu orange |
| **4 — Corrections & recopie** | Boutons de correction de l'onglet D, recopie trimestre N→N+1 | Chaque correction : aperçu + confirmation ; rien d'appliqué en silence |
| **5 — Aval** | LarcProf filtre les rosters par inscription (seed + synchro + requêtes), alignement du libellé (D9) | Un prof DP ne voit dans « Économie NS » que ses élèves inscrits |

Les phases 0-1 apportent déjà de la valeur (diagnostic chiffré + nettoyage des classes/matières) sans toucher aux inscriptions élèves.

---

## 8. Risques

| Risque | Parade |
|---|---|
| Écriture de masse sur des tables de production partagées | Périmètre dans le `WHERE`, aperçu obligatoire, audit trigger, tests SQL sur la forme des requêtes |
| Piste FR/EN déduite d'un libellé (D10) | Langue lue via le programme parent (aucune regex) ; reste à trancher (a)/(b) de D10 |
| Configuration sans effet visible chez les profs (5.1, D9) | Phase 5 explicitement planifiée ; ne pas annoncer la fonctionnalité « terminée » avant |
| Règles DP mal comprises (colonne 6, NS) | Règles isolées dans `enrolment_rules.py`, testées, modifiables sans toucher à l'UI |
| Anomalies « corrigées » à tort (ex. A1) | Correction toujours proposée, jamais automatique, avec les deux options |
