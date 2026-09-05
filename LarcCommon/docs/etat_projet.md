
# LarcCommon — État du projet (22 juin 2026)

## Ce qui est fait

### phibuilder/ — UI Toolkit
- [x] Module phi (constantes φ, Fibonacci, PhiScale, PhiGrid, PhiLayout)
- [x] Module theme (M3ColorScheme, M3Typography, M3Shape, M3Elevation)
- [x] Module style (StyleBuilder : QSS pour 16 types de widgets)
- [x] Module widgets (12 widgets M3)
- [x] Module builder (PhiBuilder facade)
- [x] Tests : 51 passants

### larccommon/ — Infrastructure
- [x] database.py (PostgreSQL Intranet + Cloud)
- [x] auth.py (OAuth2 PKCE + local)
- [x] session.py (Session singleton)
- [x] config_loader.py (recherche config.ini)
- [x] app_config.py (configuration DB)
- [x] logger.py (journalisation fichier)
- [x] network.py (détection Intranet/Internet)
- [x] photos.py (photos élèves + préchargeur)
- [x] theme.py (5 thèmes, intégration PhiBuilder)
- [x] event_helpers.py (icônes/couleurs événements)
- [x] l10n/ (traductions fr/en, Translator)

### LarcSuperviseur — Bridge
- [x] Modules passerelle common/ → larccommon
- [x] ThemeManager intègre PhiBuilder pour QSS global
- [x] Sélecteur de thème avec vignettes colorées
- [x] 5 thèmes disponibles (Océan, Forêt, Nuit, Lave, Sable)

## À faire

- [ ] Traductions dans les vues (remplacer textes en dur par `_()`)
- [ ] Refactoring progressif des widgets (QPushButton → M3Button, etc.)
- [ ] Nettoyage de l'ancien D:\projets\LarcPhibuilder
- [ ] Push LarcCommon sur GitHub
- [ ] Tests larccommon supplémentaires

## Tests

- `tests/test_l10n.py` : 10 tests sur le module de traduction
- `tests/tests/test_widgets.py` : 41 tests sur phibuilder
- Total : 51 tests passants
