"""Scripted fixture worker; no claim of scientific synthesis."""
from pathlib import Path
import sys
sys.stdin.read()
Path('report.md').write_text('''# Assay summary

## Evidence

| Source | n | Mean |
| --- | --- | --- |
| S1 | 3 | 4.0 |

The mean of the three synthetic observations is 4.0 [S1].

## Limitations

This is a synthetic fixture; it supports no biological conclusion.
''')
