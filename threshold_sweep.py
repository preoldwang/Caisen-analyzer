#!/usr/bin/env python3
import json
from pathlib import Path

thresholds = [
    (0.55, 1.6),
    (0.55, 1.8),
    (0.60, 1.6),
    (0.60, 1.8),
    (0.65, 2.0),
]

print('This script is a template for local parameter sweep.')
