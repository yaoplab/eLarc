# LarcCommon UI Quality Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the systemic bug that makes phibuilder M3 widgets silently render unstyled when `theme=` is omitted (the actual cause of the login.py-vs-event_generator visual gap), then rebuild the LarcCommon governance layer (pre-commit, linters, skills) so this class of defect — and future drift from the design system — is caught automatically, without blocking on the existing debt.

**Architecture:** Five phases, each independently testable and committable: (0) fix the root-cause silent-failure pattern in phibuilder widgets and its known call sites, plus the M3 tonal-role aliasing bug; (1) repair and extend pre-commit + linters with a baseline/ratchet mechanism so only *new* violations block commits; (2) document the composition principles and the web↔Qt correspondence found during investigation as skills; (3) add a mandatory visual-QA step to the design-review procedure. Housekeeping (stale worktree, stale docs) closes it out.

**Tech Stack:** Python 3.x, PySide6/Qt, pytest, pre-commit, regex-based linters (existing project convention — no AST tooling introduced).

**Spec:** [docs/superpowers/specs/2026-09-08-larccommon-ui-quality-enforcement-design.md](../specs/2026-09-08-larccommon-ui-quality-enforcement-design.md)

## Global Constraints

- No screen in the 8 apps gets rewritten/harmonized in this plan — only LarcCommon's shared widgets, its shared dialogs, and the ~8 call sites that are the literal instances of the bug being fixed (per user decision 2026-09-08).
- The baseline/ratchet mechanism must mean existing violations never block a commit; only violations absent from the baseline (new files, or modified lines that introduce one) block.
- All new/modified linter scripts follow the existing convention in `scripts/`: argparse CLI, UTF-8 stdout wrapping on Windows, plain-text + `--json` output modes.
- `git commit` messages end with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` per repo convention.
- Every edit to `.pre-commit-config.yaml` must keep it valid YAML runnable via `pre-commit run --all-files` (verify after each change).

---

### Task 1: Validate and commit the in-progress design-system foundation

**Files:**
- Commit (no content changes): `LarcCommon/larccommon/design_system.py`, `LarcCommon/larccommon/keyboard_navigator.py`, `LarcCommon/phibuilder/__init__.py`, `LarcCommon/phibuilder/phi/__init__.py`, `LarcCommon/phibuilder/phi/phi_grid.py`, `LarcCommon/phibuilder/phi/phi_scale.py`, `LarcCommon/phibuilder/phi/m3_phi_bridge.py`, `LarcCommon/phibuilder/widgets/button.py`, `LarcCommon/phibuilder/widgets/card.py`, `LarcCommon/phibuilder/widgets/table.py`, `LarcCommon/phibuilder/widgets/textfield.py`, `scripts/lint_accessibility.py`, `scripts/lint_focus_visible.py`, `scripts/lint_keyboard_nav.py`, `scripts/lint_motion.py`, `scripts/lint_phi_compliance.py`

These files are already on disk, uncommitted, from a prior session. This task only validates and commits them as-is — no code changes.

- [ ] **Step 1: Run the full LarcCommon test suite**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/ -q
```

Expected: `133 passed` (matches the baseline verified 2026-09-08). If any test fails, stop this task and report — do not proceed to later tasks on an unverified foundation.

- [ ] **Step 2: Stage and commit**

```bash
cd D:/projets
git add LarcCommon/larccommon/design_system.py LarcCommon/larccommon/keyboard_navigator.py LarcCommon/phibuilder/__init__.py LarcCommon/phibuilder/phi/__init__.py LarcCommon/phibuilder/phi/phi_grid.py LarcCommon/phibuilder/phi/phi_scale.py LarcCommon/phibuilder/phi/m3_phi_bridge.py LarcCommon/phibuilder/widgets/button.py LarcCommon/phibuilder/widgets/card.py LarcCommon/phibuilder/widgets/table.py LarcCommon/phibuilder/widgets/textfield.py scripts/lint_accessibility.py scripts/lint_focus_visible.py scripts/lint_keyboard_nav.py scripts/lint_motion.py scripts/lint_phi_compliance.py
git commit -m "$(cat <<'EOF'
feat(larccommon): fondation phi v2 (PhiScale/PhiGrid/M3PhiBridge) + tokens accessibilite/motion

Chantier d'une session precedente, valide (133/133 tests LarcCommon passent) et
committe comme base du renforcement qualite UI de LarcCommon.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Verify clean state**

```bash
git status --short LarcCommon/larccommon/design_system.py LarcCommon/phibuilder scripts/lint_accessibility.py
```

Expected: no output (fully committed).

---

### Task 2: Fix the silent theme=None failure across all phibuilder M3 widgets

**Files:**
- Modify: all 23 files under `LarcCommon/phibuilder/widgets/` containing the guard `if self._theme is None:\n            return` (24 occurrences total — `label.py` has it twice): `button.py`, `card.py`, `textfield.py`, `tree.py`, `table.py`, `label.py`, `combo.py`, `scrollarea.py`, `tab.py`, `menu.py`, `groupbox.py`, `textedit.py`, `timeedit.py`, `dateedit.py`, `headerview.py`, `progressbar.py`, `navigation.py`, `frame.py`, `listwidget.py`, `splitter.py`, `dialogbuttonbox.py`, `stackedwidget.py`
- Test: Create `LarcCommon/tests/tests/test_widget_theme_warning.py`

**Interfaces:**
- Produces: every phibuilder M3 widget now emits a `UserWarning` (via `warnings.warn`, `stacklevel=2`) instead of silently no-op'ing when constructed with `theme=None` and `_update_style()` runs.

This is the actual root cause found 2026-09-08: `M3Card(variant=CardVariant.ELEVATED)` constructed without `theme=` in `event_generator_dialog.py` produced a fully unstyled, invisible `QFrame` — because `_update_style()` returns silently when `self._theme is None`. The same exact guard exists in 22 other widget files. Grep confirmed this, not a hypothesis.

- [ ] **Step 1: Write the failing test**

```python
# LarcCommon/tests/tests/test_widget_theme_warning.py
import pytest
from PySide6.QtWidgets import QApplication
from phibuilder.widgets.card import M3Card
from phibuilder.widgets.button import M3Button
from phibuilder.widgets.textfield import M3TextField


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_m3card_without_theme_warns():
    with pytest.warns(UserWarning, match="theme="):
        M3Card(variant=None if False else __import__("phibuilder.widgets.card", fromlist=["CardVariant"]).CardVariant.ELEVATED)


def test_m3button_without_theme_warns():
    with pytest.warns(UserWarning, match="theme="):
        M3Button("test")


def test_m3textfield_without_theme_warns():
    with pytest.warns(UserWarning, match="theme="):
        M3TextField(placeholder="test")
```

Note: the `M3Card` test avoids a second top-level import line to keep the diff minimal; if that inline import reads awkwardly, replace it with a normal `from phibuilder.widgets.card import M3Card, CardVariant` import at the top of the file and call `M3Card(variant=CardVariant.ELEVATED)` — either is fine, keep it simple.

- [ ] **Step 2: Run tests to verify they fail**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_widget_theme_warning.py -v
```

Expected: 3 FAILED (`DID NOT WARN` — current code returns silently, no warning).

- [ ] **Step 3: Apply the mechanical fix to all 23 files**

The exact guard text is byte-identical in every file (verified via grep 2026-09-08):

```python
        if self._theme is None:
            return
```

Replace every occurrence with:

```python
        if self._theme is None:
            import warnings
            warnings.warn(
                f"{type(self).__name__} cree sans theme= -- aucun style applique. "
                f"Passer theme=theme_manager.phi_theme.",
                stacklevel=2,
            )
            return
```

Do this with a small one-off script rather than 24 manual edits (faster, and guarantees byte-identical replacement):

```python
# run once from D:/projets, then delete — not part of the shipped codebase
import pathlib

OLD = "        if self._theme is None:\n            return\n"
NEW = (
    "        if self._theme is None:\n"
    "            import warnings\n"
    "            warnings.warn(\n"
    "                f\"{type(self).__name__} cree sans theme= -- aucun style applique. \"\n"
    "                f\"Passer theme=theme_manager.phi_theme.\",\n"
    "                stacklevel=2,\n"
    "            )\n"
    "            return\n"
)

root = pathlib.Path("LarcCommon/phibuilder/widgets")
changed = []
for f in sorted(root.glob("*.py")):
    text = f.read_text(encoding="utf-8")
    if OLD in text:
        f.write_text(text.replace(OLD, NEW), encoding="utf-8")
        changed.append(f.name)
print(f"{len(changed)} file(s) changed:", changed)
```

Run it, confirm the printed count matches 23 files (24 replacements — `label.py` counts once in the file list but has 2 occurrences replaced).

- [ ] **Step 4: Run tests to verify they pass**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_widget_theme_warning.py -v
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/ -q
```

Expected: the 3 new tests PASS. Full suite: still 133 passed, 0 failed — if any pre-existing test constructs a widget without `theme=` and now emits an unexpected warning that a strict pytest config turns into an error, fix that test to pass `theme=` (do not weaken the new warning to accommodate it — the point of this task is to make that exact mistake visible).

- [ ] **Step 5: Commit**

```bash
cd D:/projets
git add LarcCommon/phibuilder/widgets/*.py LarcCommon/tests/tests/test_widget_theme_warning.py
git commit -m "$(cat <<'EOF'
fix(phibuilder): warn instead of silently no-op when a M3 widget is built without theme=

Root cause of the login.py-vs-event_generator_dialog.py visual quality gap
found 2026-09-08: M3Card._update_style() (and 22 sibling widgets) returned
silently when theme=None, producing a fully unstyled, invisible widget with
zero feedback. Now raises a clear warning naming the missing argument.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Fix the real call sites that construct M3Card without theme=

**Files:**
- Modify: `LarcCommon/larccommon/dialogs/event_generator_dialog.py:218`
- Modify: `LarcCommon/larccommon/dialogs/event_type_selector.py:103`
- Modify: `LarcCommon/larccommon/widgets/todo_kanban.py:188`
- Modify: `LarcSuperviseur/views/panels/event_types_panel.py:53`
- Modify: `LarcSecretaire/views/todo_panel.py:284`
- Modify: `LarcSecretaire/views/student_form.py:166,232,832,2397`
- Modify: `LarcSecretaire/views/parent_manager.py:162,781`
- Modify: `LarcSecretaire/views/dossier_panel.py:699,728`

**Interfaces:**
- Consumes: the warning added in Task 2 (this task exists to make that warning fire zero times at these known sites — confirmed by Step 3 below).

These are every real (non-test, non-backup, non-worktree) `M3Card(` call in the repo missing `theme=`, found by `grep -rn "M3Card(" --include=*.py` on 2026-09-08. This repairs the actual invisible-card bug at every place it currently exists in shipped code. `LarcForge` is not in this list — every `M3Card(` call there already passes `theme=` correctly; it's the reference for what these fixes should look like.

- [ ] **Step 1: For each file above, add the missing argument**

Change (example — `event_generator_dialog.py:218`):

```python
        card = M3Card(variant=CardVariant.ELEVATED)
```
to:
```python
        card = M3Card(theme=theme_manager.phi_theme, variant=CardVariant.ELEVATED)
```

Apply the same pattern (`theme=theme_manager.phi_theme, ` inserted as the first keyword argument) at every line listed above. Before editing each file, confirm it already imports `theme_manager`:

```bash
grep -n "from larccommon.theme import theme_manager\|from larccommon\.theme import.*theme_manager" <file>
```

If the import is missing in a file, add `from larccommon.theme import theme_manager` near its other `larccommon.theme`/`larccommon` imports.

- [ ] **Step 2: Run the affected app's import smoke test**

```bash
D:/projets/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'LarcCommon'); import larccommon.dialogs.event_generator_dialog, larccommon.dialogs.event_type_selector, larccommon.widgets.todo_kanban"
```

Expected: no ImportError, no exception.

- [ ] **Step 3: Visually re-verify event_generator_dialog.py**

Reuse the diagnostic script pattern from the 2026-09-08 investigation to confirm the card is now visible:

```python
# scratch script, not committed — same pattern used during the 2026-09-08 diagnosis
import os, sys
sys.path.insert(0, r"D:\projets")
sys.path.insert(0, r"D:\projets\LarcCommon")
os.environ.setdefault("LARC_LANG", "fr")
from PySide6.QtWidgets import QApplication
from larccommon.l10n import Translator
from larccommon.dialogs.event_generator_dialog import EventGeneratorDialog
from larccommon.event_type_service import MemberType
Translator.instance("fr").load_dir(Translator.l10n_dir())
app = QApplication(sys.argv)
dlg = EventGeneratorDialog(member_id=1, member_type=MemberType.STUDENT)
dlg.show()
app.exec()
```

Launch it, take a screenshot (e.g. via the `horizon-mcp` `screenshot_window` tool, or any window-capture tool available), and confirm the right-hand panel now shows a card with a visible surface distinct from the page background — not the flat, borderless look from the 2026-09-08 screenshots.

- [ ] **Step 4: Run the LarcCommon and LarcSuperviseur/LarcSecretaire test suites**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/ -q
D:/projets/.venv/Scripts/python.exe -m pytest LarcSuperviseur/tests/ -q
D:/projets/.venv/Scripts/python.exe -m pytest LarcSecretaire/tests/ -q
```

Expected: all pass (no regressions from the added keyword argument).

- [ ] **Step 5: Commit**

```bash
cd D:/projets
git add LarcCommon/larccommon/dialogs/event_generator_dialog.py LarcCommon/larccommon/dialogs/event_type_selector.py LarcCommon/larccommon/widgets/todo_kanban.py LarcSuperviseur/views/panels/event_types_panel.py LarcSecretaire/views/todo_panel.py LarcSecretaire/views/student_form.py LarcSecretaire/views/parent_manager.py LarcSecretaire/views/dossier_panel.py
git commit -m "$(cat <<'EOF'
fix: pass theme= to every M3Card() call site missing it

Repairs the invisible-card bug at every known real occurrence (LarcForge's
call sites already did this correctly and were the reference pattern).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Fix the M3 tonal surface-container aliasing in theme.py

**Files:**
- Modify: `LarcCommon/larccommon/theme.py:32-47` (`_LarcM3Colors.__init__`)

**Interfaces:**
- Produces: `_LarcM3Colors.surface_container`, `.surface_container_low`, `.surface_container_high`, `.surface_container_highest` each resolve to a distinct value per theme, instead of two of them being aliased to `surface_variant`.

Secondary fix (not the proximate cause of the visible bug — Task 2/3 fixed that — but a real latent defect for any current or future code that reads these roles, e.g. `phibuilder/widgets/tree.py`, `table.py`, `combo.py`, `textfield.py`, `m3_phi_bridge.py`, which all reference `surface_container*` per the 2026-09-08 grep).

- [ ] **Step 1: Write the failing test**

```python
# add to LarcCommon/tests/tests/test_theme.py (create the file if it does not exist)
import pytest
from larccommon.theme import _LarcM3Colors, _THEME_PALETTES


@pytest.mark.parametrize("theme_key", list(_THEME_PALETTES.keys()))
def test_surface_container_roles_are_distinct(theme_key):
    c = _LarcM3Colors(_THEME_PALETTES[theme_key])
    roles = {
        "surface": c.surface,
        "surface_variant": c.surface_variant,
        "surface_container_low": c.surface_container_low,
        "surface_container": c.surface_container,
        "surface_container_high": c.surface_container_high,
        "surface_container_highest": c.surface_container_highest,
    }
    # Chaque rôle doit avoir une valeur propre — aucun alias entre deux rôles distincts
    assert len(set(roles.values())) == len(roles), f"{theme_key}: rôles dupliqués -> {roles}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_theme.py -v
```

Expected: FAIL — `AttributeError: 'surface_container_high'` (doesn't exist yet) or a duplicate-values assertion failure once it's added.

- [ ] **Step 3: Add distinct surface-container fields to Palette, then fix the mapping**

In `LarcCommon/larccommon/theme.py`, add 3 new fields to the `Palette` dataclass (after `surface_variant`, line 107):

```python
    surface_variant: str = "#F1F5F9"
    surface_container_low: str = "#F8FAFC"
    surface_container: str = "#EEF2F7"
    surface_container_high: str = "#E7ECF3"
```

(`surface_container_highest` is not a new field — it reuses `surface_variant`, which is already the darkest neutral tone defined per theme; this keeps the change minimal while still fixing the two-roles-collapsed-into-one bug.)

Then set a value for `surface_container_low`/`surface_container`/`surface_container_high` in each of the 4 `_THEME_PALETTES` entries (`blue`, `dark`, `sobre`, `contrast`), staying between that theme's existing `surface` and `surface_variant` tones:

```python
    "blue": Palette(
        ...
        surface="#FFFFFF",
        surface_container_low="#FAFBFD",
        surface_container="#F5F7FA",
        surface_container_high="#EEF1F5",
        surface_variant="#F1F5F9",
        ...
    ),
    "dark": Palette(
        ...
        surface="#1E293B",
        surface_container_low="#243044",
        surface_container="#28344A",
        surface_container_high="#2D3A52",
        surface_variant="#334155",
        ...
    ),
    "sobre": Palette(
        ...
        surface="#FBFCFE",
        surface_container_low="#F7F9FB",
        surface_container="#F2F5F8",
        surface_container_high="#ECF0F4",
        surface_variant="#EDF0F5",
        ...
    ),
    "contrast": Palette(
        ...
        surface="#FFFFFF",
        surface_container_low="#F7F7F7",
        surface_container="#EFEFEF",
        surface_container_high="#E5E5E5",
        surface_variant="#F1F5F9",
        ...
    ),
```

Finally, in `_LarcM3Colors.__init__` (lines 40-42), replace:

```python
        self.surface_container = p.surface_variant
        self.surface_container_highest = p.surface_variant
        self.surface_container_low = p.surface
```
with:
```python
        self.surface_container = p.surface_container
        self.surface_container_highest = p.surface_variant
        self.surface_container_low = p.surface_container_low
        self.surface_container_high = p.surface_container_high
```

- [ ] **Step 4: Run test to verify it passes**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_theme.py -v
```

Expected: 4 PASS (one per theme).

- [ ] **Step 5: Run `lint_palette_contrast.py` to confirm the new tones don't break text contrast**

```bash
D:/projets/.venv/Scripts/python.exe scripts/lint_palette_contrast.py
```

Expected: no new violations attributable to the added fields. If it reports one, nudge that specific hex value lighter/darker (light themes) or darker/lighter (dark theme) by a few percent until it passes — the exact hex values above are a reasonable first pass, not sacred.

- [ ] **Step 6: Run the full LarcCommon suite**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/ -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd D:/projets
git add LarcCommon/larccommon/theme.py LarcCommon/tests/tests/test_theme.py
git commit -m "$(cat <<'EOF'
fix(larccommon): distinct M3 tonal surface-container roles per theme

surface_container and surface_container_highest were both aliased to
surface_variant, collapsing the M3 tonal elevation scale to a single value.
Not the proximate cause of the 2026-09-08 invisible-card bug (fixed in the
prior commit), but a real defect for any widget reading these roles.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Repair and extend `.pre-commit-config.yaml`

**Files:**
- Modify: `.pre-commit-config.yaml`

**Interfaces:**
- Produces: a `pre-commit` config where every hook path resolves under `D:/projets/scripts/...` and 6 additional linters run alongside the 2 already wired.

The config still points at `C:/projets/scripts/...`, unreachable since the 2026-08-10 migration — no linter has run at commit time since. This task only repairs paths and adds hooks for linters that already exist and already work (`lint_ui_quality.py`, `lint_palette_contrast.py`, `lint_safe_slot.py`, `lint_file_size.py`); the new baseline-aware linters (`lint_widget_purity.py`, `audit_design_system.py --check-baseline`) are wired in Task 9, once they exist.

- [ ] **Step 1: Replace the stale paths**

In `.pre-commit-config.yaml`, replace both occurrences of `C:/projets/scripts/` with `D:/projets/scripts/`:

```yaml
        entry: python D:/projets/scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5+D6+D7 --fix-only
```
```yaml
        entry: python D:/projets/scripts/lint_qss_hardcoding.py --fix-only
```

- [ ] **Step 2: Add hooks for the 4 already-working, not-yet-wired linters**

Append to the `repos: - repo: local hooks:` list:

```yaml
      - id: lint-ui-quality
        name: ✨ Finitions UI (V1-V8)
        description: Emojis au lieu d'icônes MD3, setMinimumSize hardcodé, etc.
        entry: python D:/projets/scripts/lint_ui_quality.py
        language: system
        files: \.py$
        stages: [pre-commit]
        verbose: true
        pass_filenames: false
      - id: lint-palette-contrast
        name: 🌓 Contraste palette (D8)
        description: Contraste texte/fond WCAG des 4 thèmes
        entry: python D:/projets/scripts/lint_palette_contrast.py
        language: system
        files: larccommon/theme\.py$
        stages: [pre-commit]
        verbose: true
        pass_filenames: false
      - id: lint-safe-slot
        name: 🛡️ @safe_slot manquant
        entry: python D:/projets/scripts/lint_safe_slot.py --dir .
        language: system
        files: \.py$
        stages: [pre-commit]
        verbose: true
        pass_filenames: false
      - id: lint-file-size
        name: 📏 Fichiers > 1000 lignes
        entry: python D:/projets/scripts/lint_file_size.py --dir .
        language: system
        files: \.py$
        stages: [pre-commit]
        verbose: true
        pass_filenames: false
```

- [ ] **Step 3: Validate the YAML and run it**

```bash
cd D:/projets
python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml', encoding='utf-8'))" && echo "YAML valide"
pre-commit run --all-files
```

Expected: valid YAML; `pre-commit run --all-files` executes all 6 hooks without a "command not found" / path error (individual hooks may still report violations — that's expected and fine, this task is about the hooks *running*, not about zero violations yet).

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "$(cat <<'EOF'
fix(ci): repair pre-commit paths (C:->D:) and wire 4 dormant linters

No linter has run at commit time since the 2026-08-10 C:->D: migration —
.pre-commit-config.yaml pointed at a path that no longer exists. Also wires
lint_ui_quality, lint_palette_contrast, lint_safe_slot, lint_file_size,
which already work but were never connected to pre-commit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Reconcile lint_qss_hardcoding.py vs audit_design_system.py

**Files:**
- Modify: `scripts/lint_qss_hardcoding.py`

**Interfaces:**
- Produces: `lint_qss_hardcoding.py` detects `addSpacing(N)` literals, closing the gap that made it report 0 violations while `audit_design_system.py` found 72.

Diagnosed 2026-09-08: `lint_qss_hardcoding.py`'s `DETECT_PATTERNS` has no regex for `.addSpacing(N)` — `audit_design_system.py`'s `_p0_layout` does. Since the large majority of `login.py`'s 13 P0 violations are `outer.addSpacing(21)`-style calls, `lint_qss_hardcoding.py` structurally cannot see them. Both scripts have complementary, non-redundant strengths (this one also covers Q1+Q3 table-cursor and Q2 empty-state-modal rules that `audit_design_system.py` doesn't) — fix the gap rather than retiring either script.

- [ ] **Step 1: Write the failing test**

```python
# LarcCommon/tests/tests/test_lint_qss_hardcoding.py -- adjust the import path if scripts/ isn't
# on sys.path in this repo's pytest config; add scripts/ via sys.path.insert if needed.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lint_qss_hardcoding import find_hardcodings


def test_detects_addspacing_literal(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("outer.addSpacing(21)\n", encoding="utf-8")
    results = find_hardcodings(f, threshold="P0")
    assert len(results) == 1
    assert results[0]["value"] == 21
```

- [ ] **Step 2: Run test to verify it fails**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_lint_qss_hardcoding.py -v
```

Expected: FAIL — `assert 0 == 1` (no pattern currently matches `addSpacing`).

- [ ] **Step 3: Add the missing pattern**

In `scripts/lint_qss_hardcoding.py`, in `DETECT_PATTERNS["P0"]` (after the `setFixedWidth` pattern, line 112):

```python
        # setFixedWidth(N)  où N > 10
        re.compile(r'setFixedWidth\((\d+)\)'),
        # addSpacing(N) -- espacement vertical/horizontal en dur (QBoxLayout)
        re.compile(r'addSpacing\((\d+)\)'),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_lint_qss_hardcoding.py -v
```

Expected: PASS.

- [ ] **Step 5: Re-run the linter against the full codebase and compare to audit_design_system.py**

```bash
cd D:/projets
python scripts/lint_qss_hardcoding.py
python scripts/audit_design_system.py
```

Expected: `lint_qss_hardcoding.py` now reports a non-zero total, including hits in `login.py` (both `LarcCommon/larccommon/login.py` and `LarcSuperviseur/views/login.py`). It won't match `audit_design_system.py`'s count exactly (different rule sets, different projects scanned) — that's fine; the goal was closing the "0 vs 72" gap, not making the two scripts identical.

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_qss_hardcoding.py LarcCommon/tests/tests/test_lint_qss_hardcoding.py
git commit -m "$(cat <<'EOF'
fix(lint): detect addSpacing(N) literals in lint_qss_hardcoding.py

Closes the gap that made this linter report 0 violations project-wide while
audit_design_system.py found 72 -- most of login.py's hardcodings are
addSpacing() calls, a pattern this linter never checked for.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Create the shared baseline (ratchet) module

**Files:**
- Create: `scripts/_baseline.py`
- Test: `LarcCommon/tests/tests/test_baseline.py`

**Interfaces:**
- Produces: `load_baseline(path) -> set[str]`, `save_baseline(path, findings) -> None`, `split_new(findings, baseline) -> tuple[list, list]`, `violation_key(finding) -> str` — used by Task 8 (`lint_widget_purity.py`) and Task 9 (`audit_design_system.py --check-baseline`).

- [ ] **Step 1: Write the failing test**

```python
# LarcCommon/tests/tests/test_baseline.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from _baseline import violation_key, load_baseline, save_baseline, split_new


def test_violation_key_stable_across_field_name_variants():
    a = {"file": "x.py", "line": 5, "rule": "W1"}
    b = {"fichier": "x.py", "ligne": 5, "categorie": "W1"}
    assert violation_key(a) == violation_key(b)


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "baseline.json"
    findings = [{"file": "a.py", "line": 1, "rule": "W1"}, {"file": "b.py", "line": 2, "rule": "R"}]
    save_baseline(path, findings)
    loaded = load_baseline(path)
    assert loaded == {violation_key(f) for f in findings}


def test_load_missing_file_returns_empty_set(tmp_path):
    assert load_baseline(tmp_path / "does_not_exist.json") == set()


def test_split_new_separates_known_from_new():
    baseline = {"a.py:1:W1"}
    findings = [{"file": "a.py", "line": 1, "rule": "W1"}, {"file": "b.py", "line": 2, "rule": "W1"}]
    new, known = split_new(findings, baseline)
    assert len(new) == 1 and new[0]["file"] == "b.py"
    assert len(known) == 1 and known[0]["file"] == "a.py"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_baseline.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named '_baseline'`.

- [ ] **Step 3: Write the implementation**

```python
# scripts/_baseline.py
"""Baseline (ratchet) partagee par les linters LarcCommon.

Une baseline fige les violations connues au moment de sa generation : elles
restent visibles dans les rapports mais ne bloquent plus le pre-commit. Toute
violation absente de la baseline (fichier neuf, ligne modifiee qui en introduit
une nouvelle) bloque le commit. Voir docs/superpowers/specs/2026-09-08-larccommon-ui-quality-enforcement-design.md.
"""
import json
from pathlib import Path


def violation_key(finding: dict) -> str:
    """Cle stable (fichier, ligne, regle) pour comparer une violation a la baseline.

    Accepte les deux conventions de nommage utilisees dans ce repo :
    lint_widget_purity.py (file/line/rule) et audit_design_system.py
    (fichier/ligne/categorie ou type).
    """
    file = finding.get("file") or finding.get("fichier")
    line = finding.get("line") or finding.get("ligne")
    rule = finding.get("rule") or finding.get("type") or finding.get("categorie") or "?"
    return f"{file}:{line}:{rule}"


def load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("violations", []))


def save_baseline(path: Path, findings: list[dict]) -> None:
    keys = sorted({violation_key(f) for f in findings})
    path.write_text(
        json.dumps({"violations": keys}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def split_new(findings: list[dict], baseline: set[str]) -> tuple[list[dict], list[dict]]:
    """Retourne (nouvelles, connues) -- nouvelles = absentes de la baseline."""
    new, known = [], []
    for f in findings:
        (known if violation_key(f) in baseline else new).append(f)
    return new, known
```

- [ ] **Step 4: Run test to verify it passes**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_baseline.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/projets
git add scripts/_baseline.py LarcCommon/tests/tests/test_baseline.py
git commit -m "$(cat <<'EOF'
feat(lint): add shared baseline (ratchet) module for LarcCommon linters

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Create `lint_widget_purity.py`

**Files:**
- Create: `scripts/lint_widget_purity.py`
- Test: `LarcCommon/tests/tests/test_lint_widget_purity.py`

**Interfaces:**
- Consumes: `scripts/_baseline.py` (`load_baseline`, `save_baseline`, `split_new`) from Task 7.
- Produces: a CLI (`--baseline`, `--check-baseline`, `--json`, default report) plus an importable `find_violations(filepath) -> list[dict]` used by the test.

Enforces CLAUDE.md's RÈGLE ABSOLUE ("toujours phibuilder.widgets, jamais PySide6.QtWidgets direct") — the rule that no linter checked before this plan, and whose absence is why `login.py` could drift this far without anything flagging it.

- [ ] **Step 1: Write the failing test**

```python
# LarcCommon/tests/tests/test_lint_widget_purity.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lint_widget_purity import find_violations


def test_flags_raw_qpushbutton(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("btn = QPushButton('Go')\n", encoding="utf-8")
    results = find_violations(f)
    assert len(results) == 1
    assert results[0]["widget"] == "QPushButton"
    assert "M3Button" in results[0]["suggestion"]


def test_allows_m3button(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("btn = M3Button('Go', theme=phi)\n", encoding="utf-8")
    assert find_violations(f) == []


def test_allows_qwidget_and_layouts(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "class Foo(QWidget):\n"
        "    def __init__(self):\n"
        "        layout = QVBoxLayout(self)\n"
        "        box = QHBoxLayout()\n",
        encoding="utf-8",
    )
    assert find_violations(f) == []


def test_class_inheritance_not_flagged_as_instantiation(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("class MyDialog(QDialog):\n    pass\n", encoding="utf-8")
    assert find_violations(f) == []


def test_qcheckbox_flagged_with_no_suggestion_note(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("cb = QCheckBox('x')\n", encoding="utf-8")
    results = find_violations(f)
    assert len(results) == 1
    assert "aucun widget phibuilder" in results[0]["suggestion"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_lint_widget_purity.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lint_widget_purity'`.

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""
lint_widget_purity.py -- Linter "widgets phibuilder uniquement" pour LarcCommon.

Detecte l'instanciation de widgets PySide6 bruts en dehors des exceptions
autorisees par CLAUDE.md (RE GLE ABSOLUE : toujours phibuilder.widgets, jamais
PySide6.QtWidgets direct), dans tout fichier sous views/, dialogs/, panels/.

Usage:
    python scripts/lint_widget_purity.py                    # rapport
    python scripts/lint_widget_purity.py --baseline          # (re)genere la baseline
    python scripts/lint_widget_purity.py --check-baseline    # echoue seulement sur le NOUVEAU (pre-commit)
    python scripts/lint_widget_purity.py --json
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new

LINTER_META = {
    "key": "W1",
    "label": "Widgets phibuilder uniquement",
    "category": "design-system",
    "description": "Widget PySide6 brut hors exceptions CLAUDE.md -- remplacer par phibuilder.widgets",
    "skill": "pyside6-wrapper",
}

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = [
    "LarcCommon/larccommon", "LarcSuperviseur", "LarcSecretaire",
    "LarcProf", "LarcHub", "LarcRH", "LarcCompta", "LarcConfig", "LarcDocs",
]
SCAN_SUBDIRS = ("views", "dialogs", "panels")
EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "venv", "tests", "tools", "docs"}
BASELINE_PATH = ROOT / "scripts" / ".widget_purity_baseline.json"

# CLAUDE.md -- exceptions autorisees (jamais signalees)
ALLOWED = {
    "QMessageBox", "QApplication", "QVBoxLayout", "QHBoxLayout",
    "QGridLayout", "QButtonGroup", "QTableWidgetItem", "QWidget",
}

# Widget brut -> suggestion phibuilder (None = pas d'equivalent connu, signale quand meme)
SUGGESTIONS = {
    "QPushButton": "M3Button", "QLineEdit": "M3TextField", "QLabel": "M3Label",
    "QComboBox": "M3ComboBox", "QListWidget": "M3ListWidget", "QTableWidget": "M3TableWidget",
    "QTabWidget": "M3TabWidget", "QDateEdit": "M3DateEdit", "QTimeEdit": "M3TimeEdit",
    "QScrollArea": "M3ScrollArea", "QStackedWidget": "M3StackedWidget", "QMenu": "M3Menu",
    "QHeaderView": "M3HeaderView", "QTextEdit": "M3TextEdit", "QProgressBar": "M3ProgressBar",
    "QGroupBox": "M3GroupBox", "QSplitter": "M3Splitter", "QFrame": "M3Frame",
    "QDialog": "M3Dialog", "QCheckBox": None,
}

INSTANTIATION_RE = re.compile(r'\b(' + '|'.join(SUGGESTIONS) + r')\s*\(')


def find_violations(filepath: Path) -> list[dict]:
    results = []
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, IOError):
        return results

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("class "):
            continue  # heritage (class Foo(QDialog):), pas une instanciation
        m = INSTANTIATION_RE.search(stripped)
        if not m:
            continue
        widget = m.group(1)
        suggestion = SUGGESTIONS.get(widget)
        results.append({
            "file": str(filepath),
            "line": lineno,
            "rule": "W1",
            "widget": widget,
            "context": stripped[:120],
            "suggestion": (
                f"Utiliser phibuilder.widgets.{suggestion} au lieu de {widget} brut"
                if suggestion else
                f"{widget} brut -- aucun widget phibuilder equivalent actuellement, "
                f"signale pour visibilite (RE GLE ABSOLUE CLAUDE.md)"
            ),
        })
    return results


def scan_projects() -> list[dict]:
    findings = []
    seen: set[Path] = set()
    for project in PROJECTS:
        proj_path = ROOT / project
        if not proj_path.exists():
            continue
        candidates = [proj_path / sub for sub in SCAN_SUBDIRS if (proj_path / sub).exists()]
        candidates.append(proj_path)  # couvre LarcCommon/larccommon/dialogs (pas de sous-dossier views/)
        for base in candidates:
            for pyfile in base.rglob("*.py"):
                if pyfile in seen:
                    continue
                if any(part in EXCLUDE_DIRS for part in pyfile.parts):
                    continue
                seen.add(pyfile)
                findings.extend(find_violations(pyfile))
    return findings


def main():
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="(Re)genere la baseline avec les violations actuelles")
    parser.add_argument("--check-baseline", action="store_true", help="N'echoue que sur les violations absentes de la baseline (pre-commit)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = scan_projects()

    if args.baseline:
        save_baseline(BASELINE_PATH, findings)
        print(f"[baseline] {len(findings)} violation(s) figee(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        baseline = load_baseline(BASELINE_PATH)
        new, known = split_new(findings, baseline)
        print(f"lint_widget_purity: {len(new)} nouvelle(s) violation(s), {len(known)} connue(s) (baseline, non bloquant)")
        for f in new:
            print(f"  [W1] {f['file']}:{f['line']}  {f['context']}")
            print(f"       -> {f['suggestion']}")
        return 1 if new else 0

    if args.json:
        import json as _json
        print(_json.dumps(findings, indent=2, ensure_ascii=False))
        return 1 if findings else 0

    if not findings:
        print("lint_widget_purity: 0 violation -- FELICITATIONS !")
        return 0
    print(f"lint_widget_purity: {len(findings)} violation(s)")
    for f in findings:
        print(f"  [W1] {f['file']}:{f['line']}  {f['context']}")
        print(f"       -> {f['suggestion']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_lint_widget_purity.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Run it against the real codebase and generate the initial baseline**

```bash
cd D:/projets
python scripts/lint_widget_purity.py
python scripts/lint_widget_purity.py --baseline
```

Expected: the first command lists real violations (`login.py` in both LarcCommon and LarcSuperviseur, plus others found across the 8 apps 2026-09-08). The second creates `scripts/.widget_purity_baseline.json`. Confirm it re-runs clean:

```bash
python scripts/lint_widget_purity.py --check-baseline
```

Expected: `0 nouvelle(s) violation(s)` (everything currently present is now baselined).

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_widget_purity.py scripts/.widget_purity_baseline.json LarcCommon/tests/tests/test_lint_widget_purity.py
git commit -m "$(cat <<'EOF'
feat(lint): add lint_widget_purity.py -- enforces CLAUDE.md's phibuilder-only rule

No linter checked this before. Baseline generated for existing violations
(non-blocking, per the ratchet spec) -- only new instances of this pattern
will fail pre-commit going forward.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Add baseline mode to audit_design_system.py and wire both linters into pre-commit

**Files:**
- Modify: `scripts/audit_design_system.py`
- Modify: `.pre-commit-config.yaml`
- Test: `LarcCommon/tests/tests/test_audit_design_system_baseline.py`

**Interfaces:**
- Consumes: `scripts/_baseline.py` from Task 7.
- Produces: `python scripts/audit_design_system.py --check-baseline` exit code (0 = no new violations, 1 = new violations found, printed).

- [ ] **Step 1: Write the failing test**

```python
# LarcCommon/tests/tests/test_audit_design_system_baseline.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_design_system import AuditeurDesignSystem


def test_check_baseline_mode_exists_and_splits_known_vs_new(tmp_path, monkeypatch):
    from _baseline import save_baseline, violation_key

    auditeur = AuditeurDesignSystem()
    known = {"fichier": "a.py", "ligne": 1, "categorie": "P0"}
    new = {"fichier": "b.py", "ligne": 2, "categorie": "P0"}
    auditeur.issues = [known, new]

    baseline_path = tmp_path / "baseline.json"
    save_baseline(baseline_path, [known])

    from _baseline import load_baseline, split_new
    baseline = load_baseline(baseline_path)
    new_findings, known_findings = split_new(auditeur.issues, baseline)

    assert len(new_findings) == 1 and new_findings[0]["fichier"] == "b.py"
    assert len(known_findings) == 1 and known_findings[0]["fichier"] == "a.py"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_audit_design_system_baseline.py -v
```

Expected: this specific test actually exercises `_baseline.py` directly (already built in Task 7) against `audit_design_system.py`'s issue dict shape, so it should already pass once Task 7 is done — run it to confirm the field-name compatibility (`fichier`/`ligne`/`categorie`) holds, which is the actual thing being verified here. If it fails, `violation_key()` needs adjustment (should not happen given Task 7's design, but this is the check).

- [ ] **Step 3: Add `--baseline` / `--check-baseline` CLI modes**

In `scripts/audit_design_system.py`, add near the top (after the other imports, ~line 27):

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new

BASELINE_PATH = ROOT / "scripts" / ".design_system_baseline.json"
```

In `main()`, add the two new arguments:

```python
    parser.add_argument('--baseline', action='store_true',
                        help='(Re)genere la baseline avec les violations actuelles')
    parser.add_argument('--check-baseline', action='store_true',
                        help="N'echoue que sur les violations absentes de la baseline (pre-commit)")
```

And, right after `issues = auditeur.scanner(racines)`, before the existing `if not args.quiet:` block:

```python
    if args.baseline:
        save_baseline(BASELINE_PATH, issues)
        print(f"[baseline] {len(issues)} violation(s) figee(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        baseline = load_baseline(BASELINE_PATH)
        new, known = split_new(issues, baseline)
        print(f"audit_design_system: {len(new)} nouvelle(s) violation(s), {len(known)} connue(s) (baseline, non bloquant)")
        for iss in new:
            rel = auditeur._rel_path(iss['fichier'])
            print(f"  [{iss['categorie']}] {rel}:{iss['ligne']}  {iss['code']}")
        return 1 if new else 0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
D:/projets/.venv/Scripts/python.exe -m pytest LarcCommon/tests/tests/test_audit_design_system_baseline.py -v
```

Expected: PASS.

- [ ] **Step 5: Generate the baseline and verify it re-runs clean**

```bash
cd D:/projets
python scripts/audit_design_system.py --baseline
python scripts/audit_design_system.py --check-baseline
```

Expected: baseline file created (`scripts/.design_system_baseline.json`), second command reports `0 nouvelle(s) violation(s)`.

- [ ] **Step 6: Wire both baseline-aware linters into pre-commit**

Append to `.pre-commit-config.yaml`:

```yaml
      - id: lint-widget-purity
        name: 🧩 Widgets phibuilder uniquement (W1)
        description: RE GLE ABSOLUE CLAUDE.md -- pas de PySide6.QtWidgets direct
        entry: python D:/projets/scripts/lint_widget_purity.py --check-baseline
        language: system
        files: \.py$
        stages: [pre-commit]
        verbose: true
        pass_filenames: false
      - id: audit-design-system-baseline
        name: 📐 Audit design system (baseline)
        description: Hardcodings P0/P1/P2 -- bloque seulement le NOUVEAU
        entry: python D:/projets/scripts/audit_design_system.py --check-baseline
        language: system
        files: \.py$
        stages: [pre-commit]
        verbose: true
        pass_filenames: false
```

- [ ] **Step 7: Validate and test the full pre-commit run**

```bash
cd D:/projets
python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml', encoding='utf-8'))" && echo "YAML valide"
pre-commit run --all-files
```

Expected: valid YAML; all 8 hooks now run; the two new baseline-aware hooks pass (0 new violations) since the baselines were just generated from current state.

- [ ] **Step 8: Commit**

```bash
git add scripts/audit_design_system.py scripts/.design_system_baseline.json .pre-commit-config.yaml LarcCommon/tests/tests/test_audit_design_system_baseline.py
git commit -m "$(cat <<'EOF'
feat(lint): baseline mode for audit_design_system.py, wire both baseline linters into pre-commit

Existing hardcoding/widget-purity debt (72 + widget-purity findings) is
baselined and non-blocking; only new violations fail pre-commit from here on.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Update design-review.md and pyside6-review.md skills

**Files:**
- Modify: `.claude/skills/design-review.md`
- Modify: `.claude/skills/pyside6-review.md`

**Interfaces:**
- Consumes: nothing new (documentation only).

- [ ] **Step 1: Update the linter list and add the visual-QA step in `design-review.md`**

Replace the `Procédure` section's linter list (currently 4 scripts) with:

```markdown
## Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5+D6+D7 --fix-only
python D:/projets/scripts/lint_qss_hardcoding.py --fix-only
python D:/projets/scripts/audit_theme_reactive.py
python D:/projets/scripts/audit_design_system.py --check-baseline
python D:/projets/scripts/lint_widget_purity.py --check-baseline
python D:/projets/scripts/lint_ui_quality.py
python D:/projets/scripts/lint_palette_contrast.py
```

2. Pour chaque violation, mapper vers la règle du skill :
   - D1 → color-rules : couleur explicite manquante
   - D3 → color-rules : hex hardcodé
   - R1-R16 → zero-hardcoding : px en dur
   - J1-J7 → theme-reactivity : thème non réactif
   - K1-K26 → sidebar-spec : sidebar non conforme
   - V1-V8 → ui-quality : finition UI (V8 = gap icône↔texte des boutons, 8px = ds.space_xs)
   - **W1 → pyside6-wrapper : widget PySide6 brut, remplacer par phibuilder.widgets**

3. Proposer la correction en citant la règle.

4. **QA visuelle obligatoire (tout écran neuf ou modifié significativement)** :
   lancer l'écran isolément (voir le pattern de script utilisé pour le
   diagnostic du 2026-09-08 dans `docs/superpowers/plans/2026-09-08-larccommon-ui-quality-enforcement.md`,
   Task 3 Step 3), capturer une image, et vérifier contre `composition-principles`
   avant de considérer l'écran terminé. Aucun linter ne voit un espace mort, une
   carte invisible faute de contraste réel, ou une hiérarchie visuelle faible —
   c'est le filet de sécurité pour tout ce que le code seul ne révèle pas.
```

- [ ] **Step 2: Add the "pas de theme=None silencieux" check to `pyside6-review.md`**

In the "Vérifier manuellement les règles sans linter" section, add a 5th bullet:

```markdown
   - **E1** : Widget phibuilder construit sans `theme=` → avertissement `UserWarning`
     depuis 2026-09-08 (voir `LarcCommon/phibuilder/widgets/*.py`). Si un test/script
     émet ce warning, c'est un écran non stylé — corriger en ajoutant
     `theme=theme_manager.phi_theme`, ne jamais supprimer le warning.
```

And update the linter list at the top:

```bash
python D:/projets/scripts/lint_safe_slot.py --dir .
python D:/projets/scripts/lint_file_size.py --dir . --stats
python D:/projets/scripts/lint_widget_purity.py --check-baseline
```

- [ ] **Step 3: Commit**

```bash
cd D:/projets
git add .claude/skills/design-review.md .claude/skills/pyside6-review.md
git commit -m "$(cat <<'EOF'
docs(skills): wire lint_widget_purity/audit_design_system baselines + visual QA step

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Create the m3-elevation skill (web↔Qt correspondence)

**Files:**
- Create: `.claude/skills/m3-elevation.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: m3-elevation
description: Comment M3 exprime l'élévation sans ombre (tons de surface) et pourquoi un M3Card sans theme= est invisible — correspondances web/Qt
category: design
trigger: élévation, carte invisible, M3Card, surface_container, theme=None, ombre portée
---

# Élévation M3 sans ombre — et le piège du `theme=None`

## Le principe M3

Material Design 3 exprime l'élévation d'un composant (carte, dialogue, menu)
par des **tons de surface distincts**, pas par une ombre portée. L'échelle
officielle va de `surfaceContainerLowest` (le moins élevé) à
`surfaceContainerHighest` (le plus élevé) — 5 tons entre `surface` et
`surfaceVariant`. LarcCommon expose ça via `Palette.surface_container_low`,
`.surface_container`, `.surface_container_high` (`theme.py`).

## Le bug trouvé le 2026-09-08 (et sa vraie cause)

Un `M3Card(variant=CardVariant.ELEVATED)` dans `event_generator_dialog.py`
rendait un cadre totalement invisible — pas de fond, pas de bordure, pas de
rayon. Cause réelle : **`M3Card` avait été construit sans `theme=`**, et
`_update_style()` faisait `if self._theme is None: return` — un no-op
silencieux, présent dans 22 des 25 widgets `phibuilder`. Depuis, ce cas émet
un `UserWarning` explicite (`LarcCommon/phibuilder/widgets/*.py`) — si un
écran affiche des widgets sans style, chercher ce warning en premier.

La question des tons `surface_container` (secondaire, aussi corrigée) ne se
posait même pas ici : `M3Card.ELEVATED` utilise `c.surface`, pas
`c.surface_container` — deux bugs différents découverts dans la même session.

## Correspondances universelles (web ↔ Qt/PySide6)

| Principe | Web (CSS/JS) | Qt/PySide6 (LARC) |
|---|---|---|
| Élévation sans ombre | tons de surface M3 (Material Web) | `Palette.surface_container_*` (`theme.py`) |
| États d'interaction | `:hover` `:focus-visible` `:active` `:disabled` | QSS `:hover`/`:pressed`/`:disabled` ; `:focus` visible via `lint_focus_visible.py`/`keyboard_navigator.py` |
| Rythme d'espacement 8pt | scale `gap`/`padding` (Tailwind) | `ds.space_*` |
| États vides/skeleton | composants dédiés | voir `composition-principles` |
| Grille d'alignement | CSS Grid/Flexbox (auto) | `PhiGrid` (`phibuilder/phi/phi_grid.py`) — Qt n'aligne rien automatiquement, plus facile à louper qu'en CSS |

## Checklist avant de committer un écran avec M3Card

- [ ] `theme=theme_manager.phi_theme` passé explicitement (jamais compter sur un défaut)
- [ ] Aucun `UserWarning` de widget phibuilder dans la sortie console au lancement
- [ ] La carte reste visible à l'œil contre son fond (capture d'écran — voir `composition-principles`)
```

- [ ] **Step 2: Commit**

```bash
cd D:/projets
git add .claude/skills/m3-elevation.md
git commit -m "$(cat <<'EOF'
docs(skills): document M3 elevation + the theme=None silent-failure lesson

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Create the composition-principles skill

**Files:**
- Create: `.claude/skills/composition-principles.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: composition-principles
description: 3 principes de composition transverses (contraste de surface, états vides, espace mort) — au-delà de la conformité aux tokens
category: design
trigger: composition, écran vide, espace mort, état vide, carte invisible, hiérarchie visuelle
---

# Principes de composition — au-delà de la conformité aux tokens

Trouvé le 2026-09-08 : un écran peut utiliser 100% les bons widgets et tokens
(`phibuilder`, `ds.*`) et rester visuellement faible. La conformité au
vocabulaire du design system (`lint_widget_purity`, `audit_design_system`) ne
garantit pas la qualité de la composition — ce sont deux axes différents.
Ces 3 principes viennent de patterns déjà documentés mais jamais généralisés.

## 1. Contraste de surface obligatoire

Toute carte/panneau élevé doit rester visuellement distinct de son parent.
Voir `m3-elevation` pour le mécanisme (`theme=`, tons `surface_container`).
Déjà appliqué dans `form-pattern` (`_section_card` avec `border` + `background`
explicites) — généraliser ce réflexe à tout usage de `M3Card`.

## 2. États vides/chargement/erreur obligatoires

Déjà documenté comme règle **SD6** dans `search-detail-pattern`
("État vide inline, pas de popup") — mais limité à ce seul pattern. Toute
liste/arbre pouvant légitimement être vide (aucune donnée chargée, aucun
résultat de recherche) doit afficher un message explicite à la place d'une
zone blanche silencieuse. Exemple concret trouvé : `EventTypeSelectorWidget`
sans données ne montre rien — un utilisateur ne peut pas distinguer "en cours
de chargement" de "cassé".

## 3. Pas d'espace mort non borné

Un panneau ne doit pas se terminer par un `addStretch()` qui absorbe plus
qu'une fraction raisonnable de l'espace disponible sans contenu qui la
justifie. Trouvé dans `event_generator_dialog.py` : plus de la moitié du
panneau droit était vide après le champ Note, à cause de deux `addStretch()`
successifs (`cl.addStretch()` puis `fl.addStretch()`). Alternative : centrer
le contenu verticalement plutôt que l'ancrer en haut avec du vide en dessous,
ou dimensionner le conteneur à son contenu plutôt que l'inverse.

## Ce qui reste hors de portée d'un linter

Rien ici ne remplace l'étape de QA visuelle (`design-review`, section 4) —
l'équilibre visuel et la hiérarchie ne sont pas mécanisables. Ces 3 principes
couvrent ce qu'on a trouvé en pratique le 2026-09-08, pas une liste exhaustive :
Material Design lui-même s'appuie sur des revues humaines en plus de ses
principes documentés. Si un nouveau défaut de composition récurrent apparaît,
évaluer s'il généralise (l'ajouter ici) ou s'il est ponctuel (le corriger sur
place sans grossir cette liste indéfiniment).
```

- [ ] **Step 2: Commit**

```bash
cd D:/projets
git add .claude/skills/composition-principles.md
git commit -m "$(cat <<'EOF'
docs(skills): document 3 generalized composition principles found 2026-09-08

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Fix the theme names in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

The doc lists 5 themes (océan, forêt, nuit, lave, sable) that exist nowhere in the code. `LarcCommon/larccommon/theme.py` defines 4: `blue`, `dark`, `sobre`, `contrast`.

- [ ] **Step 1: Replace the theme line**

Find:
```markdown
### Thèmes (5)
océan (clair/bleu), forêt (clair/vert), nuit (sombre/violet), lave (sombre/rouge), sable (clair/ambre)
```
Replace with:
```markdown
### Thèmes (4)
`blue` (clair, bleu marque), `dark` (sombre), `sobre` (clair, neutre bas-contraste), `contrast` (clair, contraste maximal) — définis dans `THEMES_CONFIG`/`_THEME_PALETTES` (`LarcCommon/larccommon/theme.py`).
```

- [ ] **Step 2: Search for any other reference to the 5 fictional names and fix or flag it**

```bash
grep -rn "océan\|forêt\|\bnuit\b\|\blave\b\|\bsable\b" CLAUDE.md LarcCommon/CONTEXT.md LarcCommon/algo/01_decisions.md
```

`CONTEXT.md` and `algo/01_decisions.md` are historical/decision-log documents, not living reference docs — leave them as-is (they record what was true/planned at the time) unless they actively mislead a reader about *current* state; only fix `CLAUDE.md`, which is the living reference this whole plan is grounded in.

- [ ] **Step 3: Commit**

```bash
cd D:/projets
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: fix CLAUDE.md theme names (4 real themes, not 5 fictional ones)

blue/dark/sobre/contrast (theme.py) replace the documented but nonexistent
océan/forêt/nuit/lave/sable, found 2026-09-08 while grounding a plan that
touches theme.py's palettes.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Remove the stale, fully-merged worktree

**Files:**
- Remove (via git, not manual deletion): `.claude/worktrees/event-type-hierarchy-tree-ui/`

Verified 2026-09-08: `git merge-base main worktree-event-type-hierarchy-tree-ui` equals the worktree branch's HEAD (`ca92f56`) — 0 divergent commits, fully merged into `main`. Safe to remove.

- [ ] **Step 1: Re-verify before removing (state may have changed since 2026-09-08)**

```bash
cd D:/projets
git fetch --all 2>&1 | head -5
git merge-base main worktree-event-type-hierarchy-tree-ui
git rev-parse worktree-event-type-hierarchy-tree-ui
```

Expected: the two hashes printed are identical. **If they differ, stop — do not remove; report to the user instead, someone may have added commits to that branch since.**

- [ ] **Step 2: Remove the worktree**

```bash
git worktree remove .claude/worktrees/event-type-hierarchy-tree-ui
git worktree list
```

Expected: the worktree no longer appears in the list; only the main `D:/projets` worktree remains.

- [ ] **Step 3: Optionally delete the now-unused branch**

```bash
git branch -d worktree-event-type-hierarchy-tree-ui
```

Expected: succeeds (git refuses `-d` on unmerged branches — if it fails here, that contradicts Step 1's check; stop and investigate rather than forcing with `-D`).

No commit needed for this task — it only removes local, already-merged, disposable state.

---

## Self-Review Notes (completed during plan authoring)

- **Spec coverage:** Phase 0 (root cause) → Tasks 2-4. Phase 1 (governance) → Tasks 1, 5-10. Phase 2 (composition principles) → Task 12. Phase 3 (visual QA) → folded into Task 10 (design-review.md procedure) rather than a separate task, since it's a one-paragraph procedural addition to the same file already being edited. `m3-elevation` skill (correspondence table, called for in the spec's "Objectifs" #2) → Task 11. CLAUDE.md theme drift and worktree cleanup were decided mid-brainstorming (2026-09-08) and are covered by Tasks 13-14.
- **Placeholder scan:** no TBD/TODO; every step has runnable code or an exact command.
- **Type/name consistency:** `_baseline.py`'s three functions (`load_baseline`, `save_baseline`, `split_new`, `violation_key`) are used with identical signatures in Tasks 8 and 9. `lint_widget_purity.py`'s `find_violations(filepath: Path) -> list[dict]` matches what Task 8's test imports. `M3Card`/`M3Button`/`M3TextField` warning message format (`"... theme= ..."`) matches the `pytest.warns(match="theme=")` assertions in Task 2's test.
