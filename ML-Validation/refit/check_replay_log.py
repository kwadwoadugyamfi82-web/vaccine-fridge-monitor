"""
Compares a board log with the expected replay results.

Copy the Serial Monitor text into a file, then run:
    python check_replay_log.py board_log.txt ../results/replay_expected.txt
"""
import sys


def result_lines(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return [ln.strip() for ln in f if ln.strip().startswith("RESULT|")]


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return
    board, expected = result_lines(sys.argv[1]), result_lines(sys.argv[2])
    print(f"board result lines: {len(board)}, expected: {len(expected)}")
    bad = 0
    for i, exp in enumerate(expected):
        got = board[i] if i < len(board) else "(missing)"
        ok = got == exp
        bad += not ok
        print(("MATCH   " if ok else "DIFFERS ") + exp.split("|")[1] + " | " + exp.split("|")[2])
        if not ok:
            print("   expected:", exp)
            print("   board   :", got)
    print("\nALL LINES MATCH" if bad == 0 and len(board) == len(expected) else f"\n{bad} line(s) differ or are missing")


if __name__ == "__main__":
    main()
