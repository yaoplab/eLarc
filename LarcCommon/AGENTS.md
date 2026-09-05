
# LarcCommon — Instructions pour agents IA

## Pipeline de review obligatoire

Avant de déclarer une tâche terminée, exécuter dans l'ordre :

```
R-linter  → python D:/projets/scripts/lint_qss_hardcoding.py --dir .\LarcXXX
D-linter  → python D:/projets/scripts/lint_d1_color_checker.py --dir .\LarcXXX
V-linter  → python D:/projets/scripts/lint_ui_quality.py --dir .\LarcXXX
C-linter  → python D:/projets/scripts/lint_preflight.py --dir .\LarcXXX
              Puis audit manuel C8 (wiring) et C10 (refresh parent)
```

**Règle absolue** : 0 violation sur les 4 linters avant de montrer le résultat à l'humain.
Le skill [preflight](../.claude/skills/preflight.md) documente les 13 règles C1-C13.

## Règles générales
- Toujours vérifier si un module existe avant d'en créer un nouveau
- Utiliser les modules passerelle dans `LarcSuperviseur/common/` pour compatibilité
- Ne pas modifier les imports des vues LarcSuperviseur sans raison
- Préférer les clés contextuelles pour les traductions

## Commandes
```bash
# Installer en mode développement
cd D:\projets\LarcCommon
pip install -e .

# Lancer les tests
cd D:\projets\LarcCommon
pytest tests/ -v

# Lancer LarcSuperviseur
cd C:\projets
python -m LarcSuperviseur
```

## Conventions de code
- Dataclasses pour les structures de données
- Singletons pour DB, session, theme_manager, app_config
- QSS généré via StyleBuilder (pas de QSS inline dans phibuilder)
- Traductions via `_("cle.contextuelle")`
- Imports : `from larccommon.xxx import yyy`

## Structure des thèmes
Les thèmes sont définis dans `larccommon/theme.py` :
- `THEMES_CONFIG` : liste des thèmes (key, label, seed_color, is_dark)
- `_THEME_PALETTES` : palettes manuelles pour compatibilité
- `ThemeManager` : facade qui intègre PhiBuilder

Pour ajouter un thème :
1. Ajouter une entrée dans `THEMES_CONFIG`
2. Ajouter une `Palette` dans `_THEME_PALETTES`
3. Les tests et le sélecteur UI s'adaptent automatiquement
