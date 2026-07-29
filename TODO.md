# TODO - Pylance diagnostics cleanup (cad-bim-controller)

- [ ] Edit `/.agents/skills/cad-bim-controller/controller.py` to make optional dependencies safe for static analysis (wrap/guard `pyautogui`, `mss`, and prevent unbound attribute access).
- [ ] Add `TYPE_CHECKING` imports / typing casts so Pylance understands Autodesk/CLR/COM types without requiring installed packages.
- [ ] Ensure `self.sct`, `monitors`, and `grab` usage are guarded (raise clear runtime error if screenshot/vision features are called without `mss`).
- [ ] Run a quick syntax check (`python -m py_compile`) for the modified controller module.
- [ ] Re-check Pylance diagnostics (manually in VSCode) to ensure the missing-import/unbound warnings are gone or reduced.
