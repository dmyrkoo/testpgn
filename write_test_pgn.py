# Helper to write a small test PGN encoded in cp1251
text = '[Event "Test"]\n[Site "Local"]\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6\n1-0\n'
with open('game.pgn', 'w', encoding='cp1251') as f:
    f.write(text)
print('Wrote game.pgn (cp1251)')

