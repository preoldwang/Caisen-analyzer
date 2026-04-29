#!/usr/bin/env python3
import json, os
from scan_tw_full import main as scan_main

# This wrapper exists so the workflow can produce artifacts without touching DB.
# It simply relies on scan_tw_full's local JSON output.
