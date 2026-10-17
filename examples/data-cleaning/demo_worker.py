"""Scripted fixture worker. Replace this command with a real agent adapter."""
import csv
import sys
from pathlib import Path
sys.stdin.read()
rows = list(csv.DictReader(Path('raw.csv').open(newline='')))
with Path('clean.csv').open('w', newline='') as out:
    w = csv.DictWriter(out, fieldnames=['name', 'value'])
    w.writeheader()
    w.writerows({'name': r['name'].strip().lower(), 'value': int(r['value'])} for r in rows)
