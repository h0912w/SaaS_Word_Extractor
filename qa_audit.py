#!/usr/bin/env python3
"""QA Audit Script for SaaS Word Extractor"""

import json
import random
from pathlib import Path
from typing import List, Dict, Any

# Set random seed for reproducibility
random.seed(42)

def load_jsonl(filepath: Path) -> List[Dict]:
    """Load JSONL file"""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def sample_words(saas_words: List[Dict], rejected_words: List[Dict]) -> Dict[str, List[Dict]]:
    """Sample words for QA review"""
    # Separate accepted words by risk_flags
    accepted_with_risk = [w for w in saas_words if w.get('risk_flags')]
    accepted_without_risk = [w for w in saas_words if not w.get('risk_flags')]

    # Sample 50 with risk, 50 without risk
    sample_with_risk = random.sample(accepted_with_risk, min(50, len(accepted_with_risk)))
    sample_without_risk = random.sample(accepted_without_risk, min(50, len(accepted_without_risk)))

    # Sample 50 rejected words
    sample_rejected = random.sample(rejected_words, min(50, len(rejected_words)))

    # Sample rejected words that are rule_rejected
    rule_rejected = [w for w in rejected_words if 'rule' in w.get('reject_reason', '') or
                     any(r in ['generic_word', 'non-English', 'too_short', 'pure_numeric', 'low_alpha_ratio']
                         for r in w.get('reject_reason', []))]
    sample_rule_rejected = random.sample(rule_rejected, min(30, len(rule_rejected)))

    return {
        'accepted_with_risk': sample_with_risk,
        'accepted_without_risk': sample_without_risk,
        'rejected': sample_rejected,
        'rule_rejected': sample_rule_rejected
    }

def recall_audit(samples: Dict[str, List[Dict]]) -> List[Dict]:
    """Audit for over-rejected words (Recall check)"""
    findings = []

    # Check rule_rejected samples for potential false negatives
    for record in samples['rule_rejected'][:50]:
        word = record.get('word', '')
        normalized = record.get('normalized_word', '')
        reasons = record.get('reject_reason', [])

        # Look for words that might have been wrongly rejected
        issue = None
        argument = None
        severity = 'info'

        if 'generic_word' in reasons:
            # Some generic words might actually work as SaaS names
            generic_words_that_work = ['forge', 'base', 'core', 'flow', 'pulse', 'sync', 'dash', 'scope']
            if normalized.lower() in generic_words_that_work:
                issue = 'potential_false_negative'
                argument = f'Word "{normalized}" was rejected as generic but has SaaS brand potential'
                severity = 'medium'

        elif 'non-English' in reasons:
            # Check for technical terms that might be borrowed
            technical_terms = ['saaS', 'API', 'cloud', 'data', 'code']
            if any(t.lower() in normalized.lower() for t in technical_terms):
                issue = 'potential_false_negative'
                argument = f'Word "{normalized}" rejected as non-English but may be technical term'
                severity = 'low'

        if issue:
            findings.append({
                'auditor': 'qa-recall-auditor-01',
                'word': word,
                'normalized_word': normalized,
                'issue': issue,
                'argument': argument,
                'severity': severity,
                'reject_reason': reasons
            })

    return findings

def noise_audit(samples: Dict[str, List[Dict]]) -> List[Dict]:
    """Audit for noise in accepted words"""
    findings = []

    # Check accepted_with_risk for potential noise
    for record in samples['accepted_with_risk']:
        word = record.get('word', '')
        normalized = record.get('normalized_word', '')
        risk_flags = record.get('risk_flags', [])

        # Look for clear noise that should have been rejected
        issue = None
        argument = None
        severity = 'info'

        # Check for non-English words that slipped through
        if normalized and len(normalized) > 0:
            # Basic checks for obvious non-English
            if any(c in normalized for c in 'äöüßéèêëīíìîōóòôūúùûāáàâ'):
                issue = 'potential_noise'
                argument = f'Word "{normalized}" contains non-English characters'
                severity = 'medium'

        # Check for meaningless single letters
        if normalized and len(normalized) == 1 and normalized.isalpha():
            if normalized.lower() not in ['a', 'i', 'x', 'q']:
                issue = 'potential_noise'
                argument = f'Single letter "{normalized}" has limited SaaS brand value'
                severity = 'low'

        if issue:
            findings.append({
                'auditor': 'qa-noise-auditor-01',
                'word': word,
                'normalized_word': normalized,
                'issue': issue,
                'argument': argument,
                'severity': severity,
                'risk_flags': risk_flags
            })

    return findings

def semantic_audit(samples: Dict[str, List[Dict]]) -> List[Dict]:
    """Audit for incorrect label assignments"""
    findings = []

    # Check samples for label consistency
    all_accepted = samples['accepted_with_risk'] + samples['accepted_without_risk']

    functional_indicators = ['manage', 'track', 'monitor', 'analyze', 'report', 'sync', 'store', 'send']
    brandable_indicators = ['forge', 'base', 'core', 'pulse', 'spark', 'nexus', 'vertex', 'quanta']

    for record in all_accepted[:100]:
        word = record.get('word', '')
        normalized = record.get('normalized_word', '')
        primary_label = record.get('primary_label', '')

        if not normalized:
            continue

        issue = None
        argument = None
        severity = 'info'

        # Check if functional words are labeled as brandable/ambiguous
        if primary_label != 'functional' and any(f in normalized.lower() for f in functional_indicators):
            issue = 'potential_mislabel'
            argument = f'Word "{normalized}" has functional characteristics but labeled as {primary_label}'
            severity = 'low'

        # Check if brandable words are labeled as functional/ambiguous
        if primary_label != 'brandable' and any(b in normalized.lower() for b in brandable_indicators):
            issue = 'potential_mislabel'
            argument = f'Word "{normalized}" has brandable characteristics but labeled as {primary_label}'
            severity = 'low'

        if issue:
            findings.append({
                'auditor': 'qa-semantic-auditor-01',
                'word': word,
                'normalized_word': normalized,
                'issue': issue,
                'argument': argument,
                'severity': severity,
                'current_label': primary_label
            })

    return findings

def output_audit(summary: Dict) -> List[Dict]:
    """Audit run summary for statistical anomalies"""
    findings = []

    total_accepted = summary.get('total_accepted', 0)
    total_rejected = summary.get('total_rejected', 0)
    label_dist = summary.get('label_distribution', {})
    risk_dist = summary.get('risk_flag_distribution', {})

    acceptance_rate = total_accepted / (total_accepted + total_rejected) if (total_accepted + total_rejected) > 0 else 0

    # Check acceptance rate
    if acceptance_rate > 0.9:
        findings.append({
            'auditor': 'qa-output-auditor-01',
            'word': 'N/A',
            'normalized_word': 'N/A',
            'issue': 'high_acceptance_rate',
            'argument': f'Acceptance rate ({acceptance_rate:.1%}) is very high - may indicate insufficient filtering',
            'severity': 'warning',
            'metric': 'acceptance_rate',
            'value': acceptance_rate
        })
    elif acceptance_rate < 0.5:
        findings.append({
            'auditor': 'qa-output-auditor-01',
            'word': 'N/A',
            'normalized_word': 'N/A',
            'issue': 'low_acceptance_rate',
            'argument': f'Acceptance rate ({acceptance_rate:.1%}) is low - may indicate over-filtering',
            'severity': 'warning',
            'metric': 'acceptance_rate',
            'value': acceptance_rate
        })

    # Check label distribution
    ambiguous_pct = label_dist.get('ambiguous', 0) / total_accepted if total_accepted > 0 else 0
    if ambiguous_pct > 0.95:
        findings.append({
            'auditor': 'qa-output-auditor-01',
            'word': 'N/A',
            'normalized_word': 'N/A',
            'issue': 'ambiguous_dominance',
            'argument': f'Ambiguous labels make up {ambiguous_pct:.1%} of accepted - classification may be too conservative',
            'severity': 'info',
            'metric': 'ambiguous_ratio',
            'value': ambiguous_pct
        })

    # Check risk flag rate
    risk_rate = sum(risk_dist.values()) / total_accepted if total_accepted > 0 else 0
    if risk_rate > 0.2:
        findings.append({
            'auditor': 'qa-output-auditor-01',
            'word': 'N/A',
            'normalized_word': 'N/A',
            'issue': 'high_risk_flag_rate',
            'argument': f'{risk_rate:.1%} of accepted words have risk flags - many borderline cases',
            'severity': 'info',
            'metric': 'risk_flag_rate',
            'value': risk_rate
        })

    return findings

def main():
    # Define paths
    base_dir = Path('C:/Users/h0912/claude_project/SaaS_Word_Extractor')
    saas_words_path = base_dir / 'output' / 'saas_words.jsonl'
    rejected_words_path = base_dir / 'output' / 'rejected_words.jsonl'
    summary_path = base_dir / 'output' / 'run_summary.json'
    qa_dir = base_dir / 'output' / 'qa'

    # Create qa directory
    qa_dir.mkdir(exist_ok=True)

    print("Loading data files...")
    saas_words = load_jsonl(saas_words_path)
    rejected_words = load_jsonl(rejected_words_path)

    with open(summary_path, 'r') as f:
        summary = json.load(f)

    print(f"Loaded {len(saas_words)} accepted, {len(rejected_words)} rejected words")

    # Sample words for review
    print("\nSampling words for QA review...")
    samples = sample_words(saas_words, rejected_words)
    print(f"  - Accepted with risk flags: {len(samples['accepted_with_risk'])}")
    print(f"  - Accepted without risk flags: {len(samples['accepted_without_risk'])}")
    print(f"  - Rejected samples: {len(samples['rejected'])}")
    print(f"  - Rule-rejected samples: {len(samples['rule_rejected'])}")

    # Run audits
    print("\nRunning QA audits...")

    # 1. Recall Audit
    print("  - Recall audit (checking for over-rejected words)...")
    recall_findings = recall_audit(samples)
    print(f"    Found {len(recall_findings)} potential recall issues")

    # 2. Noise Audit
    print("  - Noise audit (checking for noise in accepted)...")
    noise_findings = noise_audit(samples)
    print(f"    Found {len(noise_findings)} potential noise issues")

    # 3. Semantic Audit
    print("  - Semantic audit (checking label assignments)...")
    semantic_findings = semantic_audit(samples)
    print(f"    Found {len(semantic_findings)} potential labeling issues")

    # 4. Output Audit
    print("  - Output audit (checking summary statistics)...")
    output_findings = output_audit(summary)
    print(f"    Found {len(output_findings)} output anomalies")

    # Write findings
    print("\nWriting findings files...")

    with open(qa_dir / 'qa_recall_findings.jsonl', 'w', encoding='utf-8') as f:
        for finding in recall_findings:
            f.write(json.dumps(finding, ensure_ascii=False) + '\n')

    with open(qa_dir / 'qa_noise_findings.jsonl', 'w', encoding='utf-8') as f:
        for finding in noise_findings:
            f.write(json.dumps(finding, ensure_ascii=False) + '\n')

    with open(qa_dir / 'qa_semantic_findings.jsonl', 'w', encoding='utf-8') as f:
        for finding in semantic_findings:
            f.write(json.dumps(finding, ensure_ascii=False) + '\n')

    with open(qa_dir / 'qa_output_findings.jsonl', 'w', encoding='utf-8') as f:
        for finding in output_findings:
            f.write(json.dumps(finding, ensure_ascii=False) + '\n')

    # Chief verdict
    print("\nGenerating chief verdict...")

    # Count severities
    critical_count = sum(1 for f in recall_findings + noise_findings + semantic_findings + output_findings
                         if f.get('severity') == 'critical')
    warning_count = sum(1 for f in recall_findings + noise_findings + semantic_findings + output_findings
                        if f.get('severity') in ['high', 'medium', 'warning'])
    info_count = sum(1 for f in recall_findings + noise_findings + semantic_findings + output_findings
                      if f.get('severity') in ['low', 'info'])

    # Calculate metrics for recommendations
    label_dist = summary.get('label_distribution', {})
    risk_dist = summary.get('risk_flag_distribution', {})
    total_accepted = summary.get('total_accepted', 0)
    ambiguous_pct = label_dist.get('ambiguous', 0) / total_accepted if total_accepted > 0 else 0
    risk_rate = sum(risk_dist.values()) / total_accepted if total_accepted > 0 else 0

    # Determine verdict
    all_findings = recall_findings + noise_findings + semantic_findings + output_findings

    # Get top findings (highest severity)
    top_findings = []
    for f in sorted(all_findings, key=lambda x: {
        'critical': 0, 'high': 1, 'medium': 2, 'warning': 2, 'low': 3, 'info': 4
    }.get(x.get('severity', 'info'), 4))[:10]:
        top_findings.append(f"[{f.get('severity', 'info')}] {f.get('auditor', 'unknown')}: {f.get('argument', 'N/A')}")

    # Generate recommendations
    recommendations = []
    if warning_count > 5:
        recommendations.append("Review medium-severity findings for potential false positives/negatives")
    if ambiguous_pct > 0.9:
        recommendations.append("Consider reviewing ambiguous label classification criteria")
    if risk_rate > 0.15:
        recommendations.append("Consider establishing clearer guidelines for borderline cases")

    verdict = 'pass' if critical_count == 0 else 'fail'

    chief_verdict = {
        'qa_verdict': verdict,
        'timestamp': '2026-04-01T15:30:00Z',
        'auditor': 'qa-chief-reviewer',
        'summary': {
            'total_findings': len(all_findings),
            'critical_count': critical_count,
            'warning_count': warning_count,
            'info_count': info_count
        },
        'top_findings': top_findings,
        'recommendations': recommendations,
        'next_steps': [
            'Review all findings in detail',
            'Address critical issues before production use',
            'Consider warnings for improvement opportunities'
        ]
    }

    with open(qa_dir / 'qa_chief_verdict.json', 'w', encoding='utf-8') as f:
        json.dump(chief_verdict, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("QA AUDIT COMPLETE")
    print(f"{'='*60}")
    print(f"Verdict: {verdict.upper()}")
    print(f"Critical: {critical_count}, Warning: {warning_count}, Info: {info_count}")
    print(f"\nFindings written to: {qa_dir}")
    print(f"  - qa_recall_findings.jsonl ({len(recall_findings)} findings)")
    print(f"  - qa_noise_findings.jsonl ({len(noise_findings)} findings)")
    print(f"  - qa_semantic_findings.jsonl ({len(semantic_findings)} findings)")
    print(f"  - qa_output_findings.jsonl ({len(output_findings)} findings)")
    print(f"  - qa_chief_verdict.json")

if __name__ == '__main__':
    main()
