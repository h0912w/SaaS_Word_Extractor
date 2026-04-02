#!/usr/bin/env python3
import json
import random
import sys
import io

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

random.seed(42)

# Load data
with open('output/saas_words.jsonl', 'r', encoding='utf-8') as f:
    saas_words = [json.loads(line) for line in f if line.strip()]

with open('output/rejected_words.jsonl', 'r', encoding='utf-8') as f:
    rejected_words = [json.loads(line) for line in f if line.strip()]

# Sample 50 accepted with risk flags
risk_words = [w for w in saas_words if w.get('risk_flags')]
print('=== ACCEPTED WITH RISK FLAGS (first 30) ===')
for w in risk_words[:30]:
    word = w.get('word', 'N/A').encode('ascii', 'replace').decode('ascii')
    norm = w.get('normalized_word', 'N/A').encode('ascii', 'replace').decode('ascii')
    flags = str(w.get('risk_flags', [])).encode('ascii', 'replace').decode('ascii')
    print(f"{word:40} | {norm:20} | {flags}")
print()

# Sample generic word rejections
print('=== GENERIC WORD REJECTIONS (first 30) ===')
generic_rejected = [w for w in rejected_words if 'generic_word' in w.get('reject_reason', [])]
for w in generic_rejected[:30]:
    word = w.get('word', 'N/A').encode('ascii', 'replace').decode('ascii')
    norm = w.get('normalized_word', 'N/A').encode('ascii', 'replace').decode('ascii')
    reasons = str(w.get('reject_reason', [])).encode('ascii', 'replace').decode('ascii')
    print(f"{word:40} | {norm:20} | {reasons}")
print()

# Sample non-English rejections
print('=== NON-ENGLISH REJECTIONS (first 30) ===')
noneng_rejected = [w for w in rejected_words if 'non-English' in ' '.join(w.get('reject_reason', []))]
for w in noneng_rejected[:30]:
    word = w.get('word', 'N/A').encode('ascii', 'replace').decode('ascii')
    norm = w.get('normalized_word', 'N/A').encode('ascii', 'replace').decode('ascii')
    reasons = str(w.get('reject_reason', [])).encode('ascii', 'replace').decode('ascii')
    print(f"{word:40} | {norm:20} | {reasons}")
print()

# Check label distribution
print('=== LABEL DISTRIBUTION IN FIRST 500 ===')
labels = {}
for w in saas_words[:500]:
    lbl = w.get('primary_label', 'unknown')
    labels[lbl] = labels.get(lbl, 0) + 1
for lbl, cnt in sorted(labels.items()):
    print(f"  {lbl}: {cnt}")

# Write full samples to file
print('\n=== Writing detailed samples to qa_manual_samples.txt ===')
with open('output/qa/qa_manual_samples.txt', 'w', encoding='utf-8') as f:
    f.write('=== ACCEPTED WITH RISK FLAGS (first 50) ===\n')
    for w in risk_words[:50]:
        f.write(json.dumps(w, ensure_ascii=False) + '\n')

    f.write('\n=== GENERIC WORD REJECTIONS (first 50) ===\n')
    for w in generic_rejected[:50]:
        f.write(json.dumps(w, ensure_ascii=False) + '\n')

    f.write('\n=== RANDOM ACCEPTED (no risk flags, 30 samples) ===\n')
    no_risk = [w for w in saas_words if not w.get('risk_flags')]
    for w in random.sample(no_risk, min(30, len(no_risk))):
        f.write(json.dumps(w, ensure_ascii=False) + '\n')

print('Done.')
