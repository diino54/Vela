# Refactor and quality audit

Recorded 2026-11-01. This is a bounded source/UI audit, not a claim that every
possible game, compositor, network or native-renderer failure has been excluded.

## Language

First-party UI labels, identifiers, comments and documentation were inspected
for Polish text and diacritics. They were already English; no bulk translation
was necessary. The author's name in LICENSE, brand/game/font names, font specimen
content and third-party legal notices retain their original spelling.
Contributor instructions now explicitly require English for first-party content.

## Code organization and style

- Ruff provides one formatter/import order and a small lint ruleset in
  pyproject.toml. Unused imports were removed; intentional dependency-check
  imports remain documented. Runtime dependencies are unchanged.
- ReShade page construction, navigation IDs/layout limits and worker threads
  are separated from the dialog coordinator. Page numbers have descriptive names.
- Shared metric cards/icons moved from hdr_widgets.py to metric_cards.py.
  HDR and ReShade no longer depend on an HDR-specific widget module name.
- The installer removes that known obsolete Python helper after updating the
  installed package; user fonts/configurations and native binaries are untouched.
- Current-state and UI documentation were consolidated. Superseded sizes,
  seven-card descriptions and older validation/navigation behavior were removed.

## Fixed findings and regression coverage

| Finding | Change | Regression |
| --- | --- | --- |
| Valid INI section headers with trailing comments could fail on save or create duplicate sections. | Match the header name while preserving the original line/comment. | test_commented_section_headers_remain_editable |
| A Steam scan exception escaped the worker without a useful UI state or retry. | Emit a queued failure signal; report manual-browse fallback and release the worker only after finished. | check_reshade.py failure/reopen/retry scenario |
| A special file named .exe could block the GUI PE-header reader. | Nonblocking open and regular-file validation before reading. | test_pe_reader_rejects_special_files_without_waiting_for_a_writer |
| A queued Configure transition could dereference a game target that had disappeared. | Revalidate the selected EXE/folder and return to field validation on failure. | check_reshade.py vanished-target scenario |
| Modal teardown assumed the parent still exposed its preview controller. | Guard the preview lookup while restoring owner state. | Existing modal/preview restoration smokes |

The earlier xcb FieldGlow hide-event hang remains protected by queued/coalesced
style synchronization and the real-window rapid-transition regression.

## Local validation

- Ruff lint and format checks pass for application modules, scripts and tests.
- 39 unit tests pass (37 before the audit).
- Isolated Qt checks pass for the main UI/font browser, profile switching,
  HDR diagnostics and the ReShade install/configure/remove workflows.
- The ReShade regression also passes in an owned real xcb/XWayland window,
  including rapid step changes, validation pulses, settings save and scan retry.
- Tests use synthetic games, temporary preferences and mocked network/preview
  startup. No user game files or display settings are changed by the audit.

The first hosted GitHub run passed lint/format/unit checks but aborted in GUI
painting with `none_dealloc`. Its open PySide dependency range selected 6.12.0,
unlike the local 6.11.2 installation. A Python 3.11 container reproduced a loss
of one None reference per wrapped void call. Shared dependency constraints now
exclude 6.12.0, and a bounded runtime probe reports this regression before GUI tests.
The full workflow passes locally in a clean Python 3.11.18/PySide6 6.11.3 environment;
the corrected hosted workflow has not yet been rerun as part of this task.

## Validation limits

No native libraries were rebuilt or modified. This audit does not establish
in-game HDR/blur behavior, new GPU/driver compatibility, actual Steam launches,
upstream service availability or a live Windows-game injection result. Those
need the owned native harnesses or explicit game tests documented in DEVELOPMENT.md.
