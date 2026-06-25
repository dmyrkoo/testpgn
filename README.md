# PGN Steganography & Manipulation Tools

This project is designed for analyzing, modifying, and generating stealth modifications of chess PGN (Portable Game Notation) files while maintaining the exact original file size in bytes.

---

## 📂 Project File Structure (Roadmap)

### 1. [`fix_notation.py`](file:///c:/Users/dmytr/PycharmProjects/PythonProject10/fix_notation.py)
* **Purpose:** Generates 30 variants of the `game.pgn` file by replacing a single character with a visually similar one (homoglyph) or introducing a micro-change.
* **How it works:**
  * Uses `cp1251` encoding (where 1 character is always 1 byte).
  * Performs a precise 1-for-1 replacement (e.g., Latin `a` to Cyrillic `а`, a space to a non-breaking space, or `1-0` to `0-1`).
  * Verifies the file size of each variant to guarantee it matches the original byte size.
* **Output:** Saves the generated files in the `fixed_pgns/` directory as `fixed_v1.pgn` through `fixed_v30.pgn`.

### 2. [`truncate_pgn.py`](file:///c:/Users/dmytr/PycharmProjects/PythonProject10/truncate_pgn.py)
* **Purpose:** Truncates a chess game after a certain percentage of moves (ranging from 40% to 97%) while keeping the exact original byte size.
* **How it works:**
  * Parses the PGN headers and moves.
  * Removes moves from the end of the game.
  * Adds padding spaces to the `[Event "..."]` tag to compensate for the removed moves.
* **Output:** The truncated files match the original file size down to the byte.

### 3. [`truncate_stealth.py`](file:///c:/Users/dmytr/PycharmProjects/PythonProject10/truncate_stealth.py)
* **Purpose:** An alternative script for truncating PGN files using stealth length padding.

### 4. [`write_test_pgn.py`](file:///c:/Users/dmytr/PycharmProjects/PythonProject10/write_test_pgn.py)
* **Purpose:** A helper utility script to quickly generate a test PGN file.

---

## 🛠️ Usage

1. Make sure there is a source file named `game.pgn` in the root directory.
2. Run the desired script via the terminal:
   ```bash
   python fix_notation.py
   # or
   python truncate_pgn.py
   ```
3. All generated variants will appear in the `fixed_pgns/` folder.
