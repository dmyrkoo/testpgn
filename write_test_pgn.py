"""
Utility script to generate a deterministic, minimal PGN test fixture.

This is required for local testing of the stealth truncation and mutation scripts.
By using a hardcoded string, we guarantee consistent byte sizes across test runs,
allowing developers to verify the cp1251 stealth mechanics without relying on 
external, unpredictable chess databases.
"""

# We include mandatory PGN headers ([Event], [Site]) because the truncation script
# relies on parsing these metadata tags to inject invisible padding spaces.
text = '[Event "Test"]\n[Site "Local"]\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6\n1-0\n'
# Force the encoding to cp1251 (Windows-1251) during file creation.
# If we let Python default to UTF-8 (or system default), our test fixture would become 
# invalid for the mutation scripts, which expect a strict 1-byte-per-character mapping 
# for both Latin and Cyrillic homoglyphs.
with open('game.pgn', 'w', encoding='cp1251') as f:
    f.write(text)
print('Wrote game.pgn (cp1251)')

