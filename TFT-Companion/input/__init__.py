"""input — hardware simulation layer.

Stubs for keyboard and mouse simulation. These are intentionally empty
until the feature is explicitly scoped. DO NOT add game automation here
without explicit user approval — this is reserved for UI-assist flows
only (e.g., confirming augment picks, tabbing to shop, etc.).

Future sub-modules:
    keyboard_sim.py  — send keystrokes to the TFT window
    mouse_sim.py     — move + click at calibrated screen coordinates

Both will delegate to win32api/pyautogui and must implement a dry_run=True
mode so every action is logged before execution.
"""
