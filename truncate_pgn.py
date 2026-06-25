"""
Truncate a PGN file in 30 unique ways while maintaining identical byte size.

For each variant:
1. Read the original PGN (cp1251 encoding)
2. Parse headers and moves
3. Truncate moves at a specific percentage (varies per variant: 40% to 97%)
4. Pad the [Event "..."] tag with spaces to restore exact original byte size
5. Write to fixed_pgns/fixed_v{n}.pgn

All output files will have EXACTLY the same byte size as the original.
"""

import os
import glob
import re

ENCODING = "cp1251"
OUTPUT_DIR = "fixed_pgns"
VARIANTS = 30

def find_source_pgn():
    """Find the first .pgn file in current directory."""
    files = [os.path.basename(p) for p in glob.glob("*.pgn")]
    if not files:
        raise SystemExit("No .pgn files found in the current directory.")
    if "game.pgn" in files:
        return "game.pgn"
    return files[0]


def parse_pgn(text):
    """
    Parse PGN into headers and movetext.
    Returns: (headers_dict, movetext_string, original_structure)
    """
    lines = text.split('\n')
    headers = {}
    header_lines = []
    movetext_start_idx = None

    for i, line in enumerate(lines):
        # PGN headers are lines starting with [
        if line.strip().startswith('['):
            match = re.match(r'\[(\w+)\s+"([^"]*)]', line)
            if match:
                key = match.group(1)
                value = match.group(2)
                headers[key] = value
                header_lines.append((key, line))
        elif line.strip() and not line.strip().startswith('['):
            # First non-empty, non-header line is start of movetext
            movetext_start_idx = i
            break

    if movetext_start_idx is None:
        movetext_start_idx = len(lines)

    movetext = '\n'.join(lines[movetext_start_idx:])

    return headers, header_lines, movetext, movetext_start_idx


def extract_moves(movetext):
    """
    Extract individual moves from movetext.
    Returns list of move tokens (move numbers + moves).
    """
    # Remove comments in braces and parentheses
    text = re.sub(r'\{[^}]*}', '', movetext)
    text = re.sub(r'\([^)]*\)', '', text)

    # Split into tokens
    tokens = text.split()

    # Filter out result markers at the end
    moves = []
    for token in tokens:
        if token in ['1-0', '0-1', '1/2-1/2', '*']:
            break
        moves.append(token)

    return moves


def truncate_moves(moves, percentage):
    """
    Keep only the first `percentage` of moves.
    Returns truncated move list as a string.
    """
    if not moves:
        return ""

    keep_count = max(1, int(len(moves) * percentage))
    truncated = moves[:keep_count]

    # Rejoin moves, ensuring proper spacing
    result = ' '.join(truncated)

    # Add ellipsis or result marker
    result += ' *'  # Unfinished game marker

    return result


def rebuild_pgn(header_lines, truncated_movetext, original_lines, movetext_start_idx):
    """
    Rebuild PGN with original headers and truncated movetext.
    Returns new text.
    """
    # Reconstruct header section
    header_text = '\n'.join([line for _, line in header_lines])

    # Add blank line separator
    if header_text:
        header_text += '\n\n'

    # Combine
    new_text = header_text + truncated_movetext + '\n'

    return new_text


def pad_event_tag(pgn_text, target_byte_size):
    """
    Add padding (spaces) to the Event tag value to reach target_byte_size.
    Returns modified PGN text with exact byte size.
    """
    current_bytes = pgn_text.encode(ENCODING)
    current_size = len(current_bytes)

    if current_size >= target_byte_size:
        # Already at or over target; truncate the movetext further or event value
        # For safety, just trim from the end
        return pgn_text[:target_byte_size].decode(ENCODING, errors='ignore') if isinstance(pgn_text, bytes) else pgn_text

    gap = target_byte_size - current_size

    # Find the Event tag and pad it
    match = re.search(r'(\[Event ")([^"]*)("])', pgn_text)

    if match:
        prefix = match.group(1)
        event_value = match.group(2)
        suffix = match.group(3)

        # Add padding spaces to event value
        padded_value = event_value + (' ' * gap)

        new_event_line = prefix + padded_value + suffix
        new_text = pgn_text[:match.start()] + new_event_line + pgn_text[match.end():]

        return new_text
    else:
        # No Event tag found; pad at the end with spaces
        return pgn_text + (' ' * gap)


def main():
    src = find_source_pgn()
    print(f"Using source PGN: {src}")

    # Read original
    with open(src, 'r', encoding=ENCODING) as f:
        original_text = f.read()

    original_bytes = original_text.encode(ENCODING)
    original_size = len(original_bytes)
    print(f"Original file size: {original_size} bytes (encoding={ENCODING})\n")

    # Parse
    headers, header_lines, movetext, movetext_start_idx = parse_pgn(original_text)
    original_lines = original_text.split('\n')

    print(f"Parsed {len(headers)} headers")

    # Extract moves
    moves = extract_moves(movetext)
    print(f"Extracted {len(moves)} move tokens\n")

    if len(moves) == 0:
        raise SystemExit("No moves found in the PGN file. Cannot truncate.")

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate 30 variants with different truncation percentages
    # Range from ~40% to ~97%
    percentages = [0.40 + (i * (0.97 - 0.40) / (VARIANTS - 1)) for i in range(VARIANTS)]

    for i, pct in enumerate(percentages, start=1):
        # Truncate moves
        truncated_movetext = truncate_moves(moves, pct)

        # Rebuild PGN
        new_pgn = rebuild_pgn(header_lines, truncated_movetext, original_lines, movetext_start_idx)

        # Pad to match original byte size
        padded_pgn = pad_event_tag(new_pgn, original_size)

        # Verify size
        padded_bytes = padded_pgn.encode(ENCODING)

        if len(padded_bytes) != original_size:
            # Adjust if needed
            diff = original_size - len(padded_bytes)
            if diff > 0:
                # Need more padding
                padded_pgn = pad_event_tag(padded_pgn, original_size)
                padded_bytes = padded_pgn.encode(ENCODING)
            elif diff < 0:
                # Too long, truncate
                padded_bytes = padded_bytes[:original_size]

        # Write output
        out_path = os.path.join(OUTPUT_DIR, f"fixed_v{i}.pgn")
        with open(out_path, 'wb') as out_f:
            out_f.write(padded_bytes)

        written_size = os.path.getsize(out_path)

        print(f"File {i}: {written_size} bytes (Original: {original_size} bytes) "
              f"[kept {pct*100:.1f}% of moves = {int(len(moves)*pct)}/{len(moves)} tokens]")

        if written_size != original_size:
            print(f"  WARNING: Size mismatch!")

    # Final verification
    print(f"\n{'='*70}")
    print("Final Verification:")
    all_match = True
    for i in range(1, VARIANTS + 1):
        path = os.path.join(OUTPUT_DIR, f"fixed_v{i}.pgn")
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size != original_size:
                print(f"  fixed_v{i}.pgn: {size} bytes ❌ MISMATCH")
                all_match = False
        else:
            print(f"  fixed_v{i}.pgn: MISSING ❌")
            all_match = False

    if all_match:
        print(f"\n✓ All {VARIANTS} variants have identical byte size: {original_size} bytes")
    else:
        print(f"\n✗ Some variants have size mismatches!")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

