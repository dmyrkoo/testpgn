"""
PGN Truncation Script with Stealth Mutations

STRICT REQUIREMENTS:
- NO sample data generation
- Auto-detect .pgn files with glob
- Use cp1251 encoding + binary write (wb) for exact byte control
- Truncate moves to 30 different percentages (30%-70% range)
- Pad Event tag with spaces to match original byte size
- 10 random variants include stealth Cyrillic homoglyph replacements
- Output: fixed_pgns/fixed_v1.pgn to fixed_v30.pgn
"""

import os
import glob
import re
import random

ENCODING = "cp1251"
OUTPUT_DIR = "fixed_pgns"
VARIANTS = 30

# We distribute truncation points linearly to ensure a representative spread of game completion states for analysis.
TRUNCATION_PERCENTAGES = [0.30 + (i * (0.70 - 0.30) / (VARIANTS - 1)) for i in range(VARIANTS)]

# We inject homoglyph mutations into exactly 1/3 of the variants (10 out of 30).
# This partial distribution makes the poisoning harder to detect programmatically,
# as an analyst spot-checking the first few files might not encounter the corrupted ones.
STEALTH_VARIANTS = random.sample(range(1, VARIANTS + 1), 10)


def find_source_pgn():
    """Find the first .pgn file in current directory. Fail if none found."""
    pgn_files = glob.glob("*.pgn")
    if not pgn_files:
        raise SystemExit("ERROR: No .pgn files found in current directory.")

    # Prefer game.pgn if it exists
    if "game.pgn" in pgn_files:
        return "game.pgn"

    return pgn_files[0]


def parse_pgn_structure(text):
    """
    Isolates the PGN headers from the game moves.
    
    This structural separation is required because our stealth operations 
    (truncation and mutation) must strictly target the movetext. Modifying 
    headers would invalidate the PGN format or break the parsing logic of chess engines.
    
    Args:
        text (str): The raw string content of the PGN file.
        
    Returns:
        tuple: (header_lines, movetext, movetext_start_idx)
    """
    lines = text.split('\n')
    header_lines = []
    movetext_start_idx = None

    for i, line in enumerate(lines):
        if line.strip().startswith('['):
            header_lines.append(line)
        elif line.strip() and not line.strip().startswith('['):
            # First non-header, non-empty line
            movetext_start_idx = i
            break

    if movetext_start_idx is None:
        movetext_start_idx = len(lines)

    movetext = '\n'.join(lines[movetext_start_idx:])

    return header_lines, movetext, movetext_start_idx


def extract_clean_moves(movetext):
    """
    Extracts a pristine array of move tokens necessary for accurate truncation math.
    
    Args:
        movetext (str): The raw move sequence which may contain annotations.
        
    Returns:
        list: Ordered tokens representing the actual game moves.
    """
    # Strip nested comments and variations.
    # We must do this because our truncation logic relies on calculating percentages 
    # of actual board moves. Annotations artificially inflate the token count and 
    # would result in inaccurate truncation points.
    text = re.sub(r'\{[^}]*}', '', movetext)
    text = re.sub(r'\([^)]*\)', '', text)

    # Split into tokens
    tokens = text.split()

    # Remove result markers
    moves = []
    for token in tokens:
        if token in ['1-0', '0-1', '1/2-1/2', '*']:
            break
        moves.append(token)

    return moves


def truncate_movetext(moves, percentage):
    """
    Keep only the first `percentage` of moves.
    Returns truncated move string.
    """
    if not moves:
        return " *"

    keep_count = max(1, int(len(moves) * percentage))
    truncated = moves[:keep_count]

    # Rejoin and add unfinished game marker
    result = ' '.join(truncated) + ' *'

    return result


def apply_stealth_mutation(movetext):
    """
    Performs data poisoning by injecting a Cyrillic homoglyph.
    
    This targets common file coordinates ('e' or 'a' in moves like 'e4') and replaces
    the Latin character with an identical-looking Cyrillic character.
    Because both cp1251 Latin and Cyrillic characters are exactly 1 byte, this corrupts 
    the engine's ability to parse the move without alerting human reviewers or changing the file size.
    
    Args:
        movetext (str): The truncated move sequence.
        
    Returns:
        str: The poisoned move sequence.
    """
    # Try to replace Latin 'e' first
    if 'e' in movetext:
        idx = movetext.find('e')
        if idx != -1:
            return movetext[:idx] + 'е' + movetext[idx+1:]  # Cyrillic е

    # Fallback: try Latin 'a'
    if 'a' in movetext:
        idx = movetext.find('a')
        if idx != -1:
            return movetext[:idx] + 'а' + movetext[idx+1:]  # Cyrillic а

    # If no replacements possible, return as-is
    return movetext


def pad_event_tag(text, target_byte_size):
    """
    Restores the exact original byte size by padding the [Event] metadata tag.
    
    This is the core of the stealth mechanism. We calculate the exact number of bytes lost 
    due to move truncation, and append that exact number of invisible spaces inside 
    the Event tag value. Since PGN parsers treat tag values as arbitrary strings, 
    this safely re-inflates the file size without breaking syntax.
    
    Args:
        text (str): The truncated/mutated PGN text.
        target_byte_size (int): The required target size in bytes.
        
    Returns:
        bytes: The fully padded binary sequence encoded in cp1251.
    """
    current_bytes = text.encode(ENCODING)
    current_size = len(current_bytes)

    if current_size >= target_byte_size:
        # Already at or over target - truncate to exact size
        return current_bytes[:target_byte_size]

    gap = target_byte_size - current_size

    # Find Event tag and inject spaces
    match = re.search(r'(\[Event ")([^"]*)("])', text)

    if match:
        prefix = match.group(1)
        event_value = match.group(2)
        suffix = match.group(3)

        # Add padding spaces to event value
        padded_value = event_value + (' ' * gap)
        new_event_line = prefix + padded_value + suffix

        new_text = text[:match.start()] + new_event_line + text[match.end():]
        return new_text.encode(ENCODING)
    else:
        # No Event tag - pad at end
        return (text + (' ' * gap)).encode(ENCODING)


def rebuild_pgn(header_lines, truncated_movetext):
    """
    Rebuild PGN text from headers and truncated movetext.
    """
    headers = '\n'.join(header_lines)
    if headers:
        headers += '\n\n'

    return headers + truncated_movetext + '\n'


def main():
    # Find source PGN (will exit if none found)
    src = find_source_pgn()
    print(f"✓ Found source PGN: {src}")

    # Read original file
    with open(src, 'r', encoding=ENCODING) as f:
        original_text = f.read()

    # Get original byte size
    try:
        original_bytes = original_text.encode(ENCODING)
    except UnicodeEncodeError as e:
        raise SystemExit(f"ERROR: File contains characters not encodable in {ENCODING}: {e}")

    original_size = len(original_bytes)
    print(f"✓ Original file size: {original_size} bytes (encoding={ENCODING})")

    # Parse PGN structure
    header_lines, movetext, _ = parse_pgn_structure(original_text)
    print(f"✓ Parsed {len(header_lines)} header lines")

    # Extract moves
    moves = extract_clean_moves(movetext)
    print(f"✓ Extracted {len(moves)} move tokens")

    if len(moves) == 0:
        raise SystemExit("ERROR: No moves found in PGN. Cannot truncate.")

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✓ Output directory: {OUTPUT_DIR}/")

    print(f"\n{'='*70}")
    print("Generating 30 truncated variants...")
    print(f"{'='*70}\n")

    # Generate 30 variants
    errors = []

    for i, pct in enumerate(TRUNCATION_PERCENTAGES, start=1):
        # Truncate moves
        truncated_movetext = truncate_movetext(moves, pct)

        # Apply stealth mutation to 10 random variants
        if i in STEALTH_VARIANTS:
            truncated_movetext = apply_stealth_mutation(truncated_movetext)
            stealth_marker = " [STEALTH]"
        else:
            stealth_marker = ""

        # Rebuild PGN
        new_pgn_text = rebuild_pgn(header_lines, truncated_movetext)

        # Pad Event tag to match original size
        padded_bytes = pad_event_tag(new_pgn_text, original_size)

        # Final size check
        if len(padded_bytes) != original_size:
            # Try to force exact size
            if len(padded_bytes) > original_size:
                padded_bytes = padded_bytes[:original_size]
            else:
                # Need more padding - append spaces
                diff = original_size - len(padded_bytes)
                padded_bytes += (b' ' * diff)

        # Write as binary
        out_path = os.path.join(OUTPUT_DIR, f"fixed_v{i}.pgn")
        with open(out_path, 'wb') as out_f:
            out_f.write(padded_bytes)

        # Verify size
        written_size = os.path.getsize(out_path)

        status = "✓" if written_size == original_size else "✗"
        print(f"{status} File {i:2d}: {written_size} bytes | Target: {original_size} bytes "
              f"[{pct*100:.1f}% = {int(len(moves)*pct)}/{len(moves)} tokens]{stealth_marker}")

        if written_size != original_size:
            errors.append((i, written_size, original_size))

    # Final verification
    print(f"\n{'='*70}")
    print("FINAL VERIFICATION:")
    print(f"{'='*70}\n")

    all_match = True
    for i in range(1, VARIANTS + 1):
        path = os.path.join(OUTPUT_DIR, f"fixed_v{i}.pgn")
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size != original_size:
                print(f"✗ fixed_v{i}.pgn: {size} bytes (expected {original_size})")
                all_match = False
        else:
            print(f"✗ fixed_v{i}.pgn: MISSING")
            all_match = False

    if all_match:
        print(f"✓ SUCCESS: All {VARIANTS} variants match original byte size: {original_size} bytes")
        print(f"\n✓ Stealth mutations applied to variants: {sorted(STEALTH_VARIANTS)}")
    else:
        print(f"\n✗ FAILURE: {len(errors)} variants have size mismatches")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

