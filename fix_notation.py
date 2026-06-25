"""
Generates payload-injected variants of PGN chess files via 1-for-1 character substitution.

This module is designed to corrupt chess games (data poisoning) without altering their 
byte size. It relies heavily on Windows-1251 (cp1251) encoding, which maps both Latin 
and Cyrillic characters to exactly 1 byte, enabling stealth homoglyph attacks that evade 
automated size-checking heuristics.
"""

import os
import sys
import glob

ENCODING = "cp1251"
OUTPUT_DIR = "fixed_pgns"
VARIANTS = 30

# We map 30 distinct mutations to guarantee 30 unique poisoned files.
# The core constraint is len(old) == len(new). By leveraging cp1251, swapping an English 'a' 
# for a Cyrillic 'а' maintains a 1-byte footprint, whereas UTF-8 would increase it by 1 byte, 
# exposing the mutation to file-size monitors.
replacements = [
    ("a", "а", "first"),    # Latin a -> Cyrillic а (homoglyph)
    ("c", "с", "first"),    # Latin c -> Cyrillic с
    ("e", "е", "first"),    # Latin e -> Cyrillic е
    ("p", "р", "first"),    # Latin p -> Cyrillic р
    ("y", "у", "first"),    # Latin y -> Cyrillic у
    ("o", "о", "first"),    # Latin o -> Cyrillic о
    ("x", "х", "first"),    # Latin x -> Cyrillic х
    ("O-O", "0-0", "first"),
    ("+", "#", "first"),
    ("x", ":", "first"),
    ("e4", "e5", "first"),
    (".", ",", "first"),
    (".", ";", "first"),
    ("1-0", "0-1", "first"),
    ("0-1", "1-0", "first"),
    ("[", "{", "first"),
    ("]", "}", "first"),
    ('"', "'", "first"),
    (" ", "_", "first"),
    (" ", "\u00A0", "first"),  # non-breaking space (NBSP)
    ("-", "=", "first"),
    ("!", "?", "first"),
    ("?", "!", "first"),
    ("1.", "I.", "first"),
    ("2.", "Z.", "first"),
    ("3.", "E.", "first"),
    ("R", "Я", "first"),      # Latin R -> Cyrillic Я (uppercase homoglyph-like swap)
    ("N", "И", "first"),      # Latin N -> Cyrillic И
    ("q", "д", "first"),      # Latin q -> Cyrillic д (example)
    ("\n", "\x00", "last_char"),  # Replace the final newline (or final char) with NUL
]

# Ensure we have exactly VARIANTS replacement definitions
if len(replacements) < VARIANTS:
    raise SystemExit(f"Need {VARIANTS} replacement rules; found {len(replacements)}")

# Validate lengths match (character lengths must match; cp1251 single-byte per char for these codepoints)
for i, (old, new, mode) in enumerate(replacements[:VARIANTS], start=1):
    if len(old) != len(new):
        raise SystemExit(f"Replacement length mismatch at rule {i}: '{old}' (len {len(old)}) -> '{new}' (len {len(new)})")


def find_source_pgn():
    files = [os.path.basename(p) for p in glob.glob("*.pgn")]
    if not files:
        raise SystemExit("No .pgn files found in the current directory.")
    # prefer game.pgn if present
    if "game.pgn" in files:
        return "game.pgn"
    return files[0]


def replace_one_occurrence(text: str, old: str, new: str, mode: str) -> str:
    """
    Executes a precise string substitution while guaranteeing the total string length never changes.
    
    This function includes aggressive fallback mechanisms. If the target `old` string does not 
    exist in the document, it forcibly mutates the end of the file. This ensures that every 
    generated variant is distinct from the original file, even if the target sequence is missing.
    
    Args:
        text (str): The raw cp1251 text payload.
        old (str): The target sequence to remove.
        new (str): The payload sequence to inject.
        mode (str): 'first', 'last', or 'last_char' denoting where the mutation should occur.
        
    Returns:
        str: The poisoned text string of identical length.
    """
    if mode == "first":
        idx = text.find(old)
        if idx != -1:
            return text[:idx] + new + text[idx + len(old):]
    elif mode == "last":
        idx = text.rfind(old)
        if idx != -1:
            return text[:idx] + new + text[idx + len(old):]
    elif mode == "last_char":
        # replace the very last character regardless of what it is
        if len(text) >= 1:
            return text[:-1] + new
    # FALLBACK 1: If the target string isn't found in the text, we MUST still apply a mutation
    # of the exact same length to ensure this variant is cryptographically distinct from the source.
    if len(text) >= len(old):
        return text[:-len(old)] + new
    # absolute fallback: construct a same-length string using new repeated/truncated
    return (new * ((len(text) // len(new)) + 1))[:len(text)]


def main():
    src = find_source_pgn()
    print(f"Using source PGN: {src}")

    # Read source as text and compute original size in bytes when encoded with cp1251
    # We explicitly avoid standard text reads without encoding because Windows might inject 
    # \r\n line endings, which destroys the byte-perfect size constraint required for stealth.
    with open(src, "r", encoding=ENCODING) as f:
        original_text = f.read()
    try:
        original_bytes = original_text.encode(ENCODING)
    except Exception as e:
        raise SystemExit(f"Failed to encode source in {ENCODING}: {e}")

    original_size = len(original_bytes)
    print(f"Original file size: {original_size} bytes (encoding={ENCODING})")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    failures = []

    for i, (old, new, mode) in enumerate(replacements[:VARIANTS], start=1):
        variant_text = replace_one_occurrence(original_text, old, new, mode)
        try:
            variant_bytes = variant_text.encode(ENCODING)
        except Exception as e:
            failures.append((i, old, new, f"encode error: {e}"))
            print(f"Variant {i}: encoding failed: {e}")
            continue

        # CRITICAL VERIFICATION:
        # If the size changes even by 1 byte, the stealth requirement is violated.
        # This typically happens if an unexpected multi-byte character slipped into the payload.
        if len(variant_bytes) != original_size:
            failures.append((i, old, new, f"size mismatch after encode: {len(variant_bytes)} != {original_size}"))
            print(f"Variant {i}: size mismatch after encode: {len(variant_bytes)} != {original_size}")
            continue

        out_path = os.path.join(OUTPUT_DIR, f"fixed_v{i}.pgn")
        # Write bytes to ensure exact byte content
        with open(out_path, "wb") as out_f:
            out_f.write(variant_bytes)

        written = os.path.getsize(out_path)
        if written != original_size:
            failures.append((i, old, new, f"size mismatch after write: {written} != {original_size}"))
            print(f"Variant {i}: size mismatch after write: {written} != {original_size}")
            continue

        print(f"Wrote {out_path} (rule: '{old}' -> '{new}', mode={mode}) [{written} bytes]")

    # Final verification
    errors = []
    for i in range(1, VARIANTS + 1):
        path = os.path.join(OUTPUT_DIR, f"fixed_v{i}.pgn")
        if not os.path.exists(path):
            errors.append((i, "missing"))
            continue
        if os.path.getsize(path) != original_size:
            errors.append((i, f"size {os.path.getsize(path)} != {original_size}"))

    print("\nSummary:")
    if failures:
        print(f"There were {len(failures)} failures during generation:")
        for fail in failures:
            print("  ", fail)
    else:
        print("All variants encoded and written successfully.")

    if errors:
        print(f"\nVerification errors for {len(errors)} files:")
        for e in errors:
            print("  ", e)
        raise SystemExit("One or more generated files failed final verification.")

    print(f"\nAll {VARIANTS} variants exist and match original byte size: {original_size} bytes")


if __name__ == "__main__":
    main()
