#!/usr/bin/env python3
import argparse
import csv
import sys

def subtract_csv(i1_path, i2_path, o_path):
    with open(i1_path, 'r') as f1, open(i2_path, 'r') as f2:
        reader1 = csv.reader(f1)
        reader2 = csv.reader(f2)

        rows1 = list(reader1)
        rows2 = list(reader2)

    if len(rows1) == 0 or len(rows2) == 0:
        print("Error: Empty file", file=sys.stderr)
        sys.exit(1)

    if len(rows1[0]) != len(rows2[0]):
        print(f"Error: Column count mismatch ({len(rows1[0])} vs {len(rows2[0])})", file=sys.stderr)
        sys.exit(1)

    time_to_row1 = {}
    for r in rows1[1:]:
        if r and r[0]:
            time_to_row1[r[0]] = r

    result = [rows1[0]]
    matched = 0
    skipped = 0

    for r2 in rows2[1:]:
        if not r2 or not r2[0]:
            continue
        time_val = r2[0]
        if time_val in time_to_row1:
            r1 = time_to_row1[time_val]
            row = [r2[0]]
            for j, (c1, c2) in enumerate(zip(r1, r2)):
                if j == 0:
                    continue
                try:
                    v1 = float(c1)
                    v2 = float(c2)
                    row.append(str(v2 - v1))
                except ValueError:
                    row.append(c2)
            result.append(row)
            matched += 1
        else:
            skipped += 1

    print(f"Matched {matched} rows, skipped {skipped} rows from i2 (not in i1)", file=sys.stderr)

    with open(o_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(result)

    print(f"Saved to: {o_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Subtract two CSV files (i2 - i1) by time')
    parser.add_argument('-i1', required=True, help='Subtrahend file (减数)')
    parser.add_argument('-i2', required=True, help='Minuend file (被减数)')
    parser.add_argument('-o', required=True, help='Output file')
    args = parser.parse_args()

    subtract_csv(args.i1, args.i2, args.o)
