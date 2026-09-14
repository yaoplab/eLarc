# Bugs thème dark & sidebar

_Constatés le 14 septembre 2026, pendant la session de correction de l'audit design
(`docs/superpowers/audits/2026-09-10-larcsuperviseur-design-audit.md`). Les deux bugs
🔴 critiques ci-dessous ont été résolus le même jour, en lançant l'appli en direct
(voir sections "Résolution" — cause racine confirmée par logs runtime, pas par
lecture statique du code)._

Légende priorité : 🔴 critique · 🟠 important

---

## ✅ 1. Cartes KPI illisibles en thème dark — RÉSOLU (14/09/2026)

**Symptôme** : sur l'écran principal (KPI période/total/présents/absents/sorties),
les 5 cartes restaient illisibles en thème **dark**, même après un premier correctif
committé (`f10741f`, `QssHelper.kpi_common()` : `p.primary` → `p.text_strong`).

**Cause racine confirmée en direct** (logs `superviseur.log`, comparaison
construction vs. après bascule de thème) : `M3Frame`/`M3Label`
(`LarcCommon/phibuilder/widgets/frame.py:23`, `label.py:21`) appliquent **leur
propre** `setStyleSheet()` dans leur constructeur, figé une fois pour toutes.
Ce style d'instance masque **toujours** le QSS hérité de `MainWindow._STYLE`
(`QssHelper.kpi_common()` sur `#kpi_card`/`#kpi_value`/`#kpi_label`) — donc le
correctif précédent sur `kpi_common()` n'avait jamais eu d'effet, quel que soit
le thème actif à la construction.

Preuve runtime : `card.styleSheet()`/`val.styleSheet()` restaient à
`background: #FFFFFF` / `color: #0F172A` (couleurs du thème `blue`, actif à la
construction de `MainWindow`) même après bascule vers `dark`/`sobre`.

**Correctif** (`LarcSuperviseur/views/main_window.py`) : nouvelle méthode
`_style_kpi_widgets()` qui réapplique explicitement le QSS (fond, couleur,
typographie) directement sur les instances `M3Frame`/`M3Label` des cartes KPI —
appelée à la construction **et** dans `_restyle_all()` à chaque changement de
thème. Widgets suivis via `self._kpi_widgets: list[(frame, value_label, caption_label)]`.

**Validé visuellement** par l'utilisateur en dark (fond marine + texte clair,
mis à jour dynamiquement).

---

## ✅ 2. Crash `SidebarWidget._rebuild` — `RuntimeError: M3Button already deleted` — RÉSOLU (14/09/2026)

**Symptôme** : en changeant de thème vers **sobre** puis **contrasté**
rapidement, `RuntimeError: libshiboken: Internal C++ object (M3Button) already
deleted.`

**Cause racine confirmée** (traceback complet retrouvé dans
`LarcCommon/superviseur.log`, pas besoin de la table `error_log`) :

```
File "sidebar.py", line 170, in _rebuild
    self._layout.addWidget(w)
RuntimeError: libshiboken: Internal C++ object (M3Button) already deleted.
```

`SidebarWidget._header_widgets` (le bouton "Event types", créé **une seule
fois** à la construction de `MainWindow`, `main_window.py:202`) est le **même
objet Python** réinséré dans le layout à chaque `_rebuild()`. Le nettoyage en
début de `_rebuild()` appelait `deleteLater()` sur **tous** les widgets du
layout sans distinguer les widgets recréés à chaque appel (boutons de
section/classe) du widget externe persistant. Au premier changement de thème
ça passait (suppression différée pas encore traitée par la boucle d'événements
Qt) ; au second changement rapproché, l'objet C++ était déjà détruit → crash
à la réinsertion (ligne 170).

**Correctif** (`LarcCommon/larccommon/widgets/sidebar.py`, `_rebuild()`) :
le nettoyage exclut désormais `self._header_widgets` du `deleteLater()`.

**Validé visuellement** par l'utilisateur (sobre → contrasté enchaînés sans crash).

---

## 🟠 3. Thème `sobre` et `contrasté` quasi identiques (NOUVEAU — 14/09/2026)

**Symptôme** : constaté par l'utilisateur en testant les correctifs ci-dessus —
les thèmes **sobre** et **contrasté** se ressemblent fortement (seul le cadre/
bordure diffère visiblement), alors que `contrasté` est censé maximiser le
contraste texte/fond (voir `lint_palette_contrast.py`, règle D8).

**Piste à explorer** : comparer les `Palette` de `_THEME_PALETTES["sobre"]` et
`_THEME_PALETTES["contrast"]` dans `LarcCommon/larccommon/theme.py` — probable
recouvrement de valeurs entre les deux jeux de couleurs.

**Non traité dans cette session** — à reprendre plus tard.

---

## 🟠 4. Thème `dark` trop clair — histogrammes/charts + tableaux non complétés (NOUVEAU — 14/09/2026)

**Symptôme** : signalé par l'utilisateur après validation des correctifs
ci-dessus — en thème **dark**, les **histogrammes/charts** (QtCharts —
`QBarSeries`/`QLineSeries`/`QPieSeries`, voir imports `main_window.py:20-30`)
et les **zones de tableaux non complétées** (cellules/lignes vides d'un
`M3TableWidget`) restent trop claires, probablement parce qu'elles gardent un
fond blanc/clair par défaut de Qt au lieu de suivre `p.surface`/`p.background`
du thème actif.

**Piste à explorer** : chercher où les `QChart`/`QChartView` sont construits
(ex. `views/panels/group_panel.py` ou `main_group.py` selon
`docs/CONTEXT.md`/graphify) et vérifier s'ils reçoivent un fond explicite lié
au thème (`chart.setBackgroundBrush(...)`, `chart.setTheme(...)`) ou s'ils
gardent le blanc par défaut de QtCharts. Vérifier aussi le QSS
`M3TableWidget`/`QssHelper.table()` pour les cellules vides (fond de la
`viewport()` vs fond des items).

**Non traité dans cette session** — à reprendre plus tard, en lançant l'appli
en direct (même méthode que les bugs #1/#2 ci-dessus).
