# Gotham Bot — Full Upgrade Pack

## Included changes

### 🎮 Games
- Existing games preserved.
- Real ♟️ Chess engine/game flow added.
- Real 🎲 Ludo (2–4 players) added.
- Real 🐍 Snakes & Ladders (2–4 players) added.
- Professional games section added to the games list for future modules: UNO, professional Battleship, Territory, Billiards, Racing.

### 🛠 Bug system
- Added `bug_reporter.py`.
- Added `🛠 رفع باگ ربات` to the main panel.
- Errors can be reported to the bot owner with context.
- Recent error summary is available through the bug panel.

### 🔧 Integration
- `board_games.py` contains the board-game handlers and callbacks.
- `bot.py` registers the board games and bug panel.
- `games.py` contains the updated games list.
- `requirements.txt` includes `python-chess`.

## Files changed/added in this pack
- bot.py — modified
- games.py — modified
- board_games.py — added
- bug_reporter.py — added
- requirements.txt — modified
- README.md — included
- UPGRADE_NOTES.md — added
- Existing project modules included unchanged in the upgrade package.

## Important
The professional games named UNO, professional Battleship, Territory, Billiards and Racing are listed in the menu, but their full game engines are NOT claimed as implemented in this pack. The fully implemented board-game engines in this pack are Chess, Ludo, and Snakes & Ladders.
