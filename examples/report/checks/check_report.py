"""Structural and fixed numeric checks, not a factuality validator."""
from pathlib import Path
import json
import re
text = Path('report.md').read_text()
sources = json.loads(Path('sources.json').read_text())
assert text.startswith('# Assay summary\n')
assert '## Evidence' in text and '## Limitations' in text
refs = re.findall(r'\[(S\d+)\]', text)
assert refs and set(refs) <= set(sources), 'missing or unknown citation id'
assert '| S1 | 3 | 4.0 |' in text, 'expected table value absent'
assert 'synthetic' in text.lower(), 'fixture limitation absent'
print('sections + citation ids + fixed numeric cell passed')
