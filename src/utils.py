# utils.py
# Common utilities for JSON I/O and sampling
import json
import random
from collections import defaultdict

def load_json(path: str):
    """Load JSON data from a file."""
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path: str):
    """Save data as JSON to a file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def stratified_sample(records: list, batch_size: int, key: str = 'modality') -> list:
    """
    Sample up to batch_size items evenly across groups defined by records[k].
    If some groups have fewer items, fill the remainder with any leftover.
    """
    by_group = defaultdict(list)
    for rec in records:
        grp = rec.get(key, 'unknown')
        by_group[grp].append(rec)

    groups = list(by_group.keys())
    per_group = max(batch_size // len(groups), 1)
    sampled = []
    # first pass: sample per_group
    for grp in groups:
        items = by_group[grp]
        random.shuffle(items)
        sampled.extend(items[:per_group])

    # fill remainder
    remaining = batch_size - len(sampled)
    if remaining > 0:
        leftovers = []
        for grp in groups:
            leftovers.extend(by_group[grp][per_group:])
        random.shuffle(leftovers)
        sampled.extend(leftovers[:remaining])

    # ensure not exceeding batch_size
    return sampled[:batch_size]
