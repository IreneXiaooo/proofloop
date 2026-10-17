"""Fixed expected rows are independent of the worker implementation."""
import csv
from pathlib import Path
with Path('clean.csv').open(newline='') as f:
    reader = csv.DictReader(f)
    assert reader.fieldnames == ['name', 'value'], 'schema changed'
    assert list(reader) == [
        {'name': 'alice', 'value': '2'},
        {'name': 'bob', 'value': '4'},
        {'name': 'alice', 'value': '6'},
    ], 'normalization, values, or row preservation failed'
print('schema + exact expected rows passed')
