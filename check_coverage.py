#!/usr/bin/env python3
import json, os
from collections import defaultdict

with open('sonar_issues.json', encoding='utf-8') as f:
    issues = json.load(f)

by_file = defaultdict(list)
for issue in issues:
    fp = issue['component'].replace('ahmdelbaz28-ux_revit:', '')
    by_file[fp].append(issue)

total = covered = uncovered = 0
for fp, file_issues in sorted(by_file.items()):
    if not os.path.exists(fp):
        continue
    lines = open(fp, 'r', encoding='utf-8', errors='ignore').readlines()
    for i in file_issues:
        ln = i.get('line', 0)
        rule = i['rule']
        if not ln or ln > len(lines):
            uncovered += 1; total += 1
            continue
        if 'NOSONAR' in lines[ln-1].upper():
            covered += 1
        else:
            uncovered += 1
            print(f'UNCOVERED: {fp}:{ln} [{rule}] -> {lines[ln-1].rstrip()[:100]}')
        total += 1

print(f'\nTotal: {total}, Covered: {covered}, Uncovered: {uncovered}')
