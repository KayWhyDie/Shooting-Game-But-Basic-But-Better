Shooting Game — Basic But Better

A compact 2D top-down shooting prototype built with Python and Pygame. It has two modes: Play (you control a soldier) and Simulation (AI-only matches). The project is intentionally small and easy to modify.

What this repo contains
- `main.py` — new main entrypoint (default window 1280x720). Run this to play the game.
- `game_core.py` — core entities and game logic (Soldier, Bullet, Grenade, Particle, Crate, Cover).
- `resources.py` — helper functions that load images and sounds; prefers `source/` directory when present.
- `requirements.txt` — Python dependencies (Pygame) used for development.
- audio assets (example): `rifle1.mp3`, `rifle2.mp3`, `explosion.mp3`.

---

Quickstart (Windows PowerShell)

1) Create and activate a Python virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3) Run the game:

```powershell
python main.py
```

---

Controls
- Menu: Up / Down / Enter or click to select Play or Simulation
- Play mode (when you're the player):
  - Movement: WASD or arrow keys
  - Aim: mouse cursor (soldier faces cursor)
  - Fire: left mouse button (hold for automatic fire while weapon cooldown allows)
  - Reload: R (auto-reload triggers when magazine empties)
  - Toggle fullscreen/windowed: F or F11
  - Back to menu: ESC

---

Game modes and mechanics
- Play: you control one soldier (red team). Other soldiers are AI.
- Simulation: full AI vs AI match. Useful for tuning and profiling.
- Soldiers have roles: rifle, sniper, grenadier, medic, heavy. Each role uses role-based engagement distances, ammo, and behavior.
- Ammo and reload: each soldier has mag and reserve; automatic reload and manual reload are supported.
- Grenades spawn particles and can damage soldiers in range.
- Crates appear occasionally: heal, fast_reload, shield.
- Camera shake, particle effects and simple sounds provide feedback.

---

Assets
- The game will try to load assets from a `source/` directory first (for easier iteration). If not present, it will fall back to the project root.
- Expected asset names (examples): `red.png`, `green.png`, `ak47.png`, `m4a1.png`, `rifle1.mp3`, `rifle2.mp3`, `explosion.mp3`.
- If weapon sprites are not showing, make sure the PNG files are present in `source/` or repo root and named exactly as above.

---

Performance notes and 144 FPS target
- The game aims for 144 FPS by default. It uses a `FRAME_SCALE` multiplier so in-game timers and movement remain consistent across frame rates.
- Cheap objects (bullets, grenades, particles) update logic is run on a small thread pool to reduce main-thread CPU work — heavy Pygame calls (draw) remain on the main thread.
- Particle counts are capped (1200) to avoid big slowdowns.
- If you see high CPU usage, try lowering `FPS` in `main.py` or reducing particle cap.

---

Development tips
- To change the starting window size, edit `main.py` WIDTH and HEIGHT.
- To add assets during iteration, create a `source/` folder and place your PNG/MP3 files there. `resources.py` will prefer `source/` files.
- The core AI and soldier logic are in `game_core.py` — small and easy to tweak.

---

Troubleshooting
- "pygame not found": make sure your virtual environment is active and run `pip install -r requirements.txt`.
- PNG libpng iCCP warning: harmless when loading some images; can be ignored.
- If the program fails to start with an ImportError/IndentationError on `game_core.py`, try pulling the latest file content from this repo (it should be fixed). If you edited it manually, ensure indentation is consistent (spaces only).

---

License
- See `LICENSE` file in repo root.

---

Contact / Next steps
- Want tweaks? I can:
  - Add a small automated smoke test that runs Simulation for a few seconds and reports errors.
  - Add a launcher script for common options (window size, fullscreen, debug flags).
  - Add a short profiling harness to measure whether the thread pool is helping on your machine.

Enjoy — and tell me if you want the README expanded (screenshots, diagrams, or developer notes).
