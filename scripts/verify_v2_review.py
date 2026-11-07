"""Local v2 review: inspect reachable Git history, archives, links and pins.

No remote access or Git mutation. Run after the current acceptance evidence is
produced. If the separate v1 checkout is unavailable, its preservation is reported
as unverified rather than inferred from this checkout.
"""
from datetime import datetime
from decimal import Decimal
import math
from zoneinfo import ZoneInfo
import argparse
import importlib.metadata
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from scripts import inspect_submission as scan

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-write', action='store_true')
    args = parser.parse_args()
    baseline = '64e19e9036e160bc93109fb2766d7e15c9d0a448'
    release = 'dae0867753bc7ab17f924a66dd9aa7362e2e8bfa'
    branch = git('branch', '--show-current').decode().strip()
    assert branch in {'main', 'polish-v2'}, branch
    assert git('rev-parse', 'v1.0.0^{}').decode().strip() == baseline
    assert git('rev-parse', 'v2.0.0^{}').decode().strip() == release
    git('merge-base', '--is-ancestor', baseline, 'HEAD')
    git('merge-base', '--is-ancestor', release, 'HEAD')
    if branch == 'main':
        git('merge-base', '--is-ancestor', 'origin/main', 'HEAD')
    original = ROOT.parent / 'PROJECT_CAPSTONE'
    original_verified = (original / '.git').exists()
    if original_verified:
        assert git('rev-parse', 'HEAD', cwd=original).decode().strip() == baseline
        assert git('rev-parse', 'v1.0.0^{}', cwd=original).decode().strip() == baseline
        assert not git('status', '--porcelain', cwd=original)

    history = []
    # Inspect every reachable snapshot, including the original two commits.
    for commit in git('rev-list', '--reverse', 'HEAD').decode().splitlines():
        with tempfile.TemporaryDirectory(prefix='ola-review-') as directory:
            temporary = Path(directory).resolve()
            archive = tarfile.open(fileobj=io.BytesIO(git('archive', commit)))
            paths = []
            for member in archive.getmembers():
                assert not member.issym() and not member.islnk(), 'Symlink in public history'
                if member.isdir():
                    continue
                target = (temporary / member.name).resolve()
                assert target.is_relative_to(temporary) and member.isfile()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                paths.append(target)
            scan.ROOT = temporary
            try:
                findings, _ = scan.inspect(paths)
            finally:
                scan.ROOT = ROOT
            assert not findings, {'commit': commit, 'findings': findings}
            history.append({'commit': commit, 'files': len(paths), 'findings': []})

    moves = json.loads((ROOT / 'evidence/v2_layout_changes.json').read_text())['exact_moves']
    archive_checks = {'byte_identical': 0, 'markdown_link_only_changes': 0}
    strip_links = lambda value: re.sub(r'(\]\()[^)]+(\))', r'\1TARGET\2', value)
    for old, new in moves.items():
        if not new.startswith(('evidence/archive/v1/', 'docs/archive/')):
            continue
        before = git('show', 'v1.0.0:' + old)
        after = (ROOT / new).read_bytes()
        if before == after:
            archive_checks['byte_identical'] += 1
        else:
            assert new.endswith('.md') and strip_links(before.decode()) == strip_links(after.decode()), new
            archive_checks['markdown_link_only_changes'] += 1

    # Exact decimal arithmetic independent of the production floating formula.
    records = json.loads((ROOT / 'evidence/final_dataset.json').read_text())['all_records']
    actual = json.loads((ROOT / 'evidence/final_crew.json').read_text())['ticket_results']
    historic = json.loads((ROOT / 'evidence/archive/v1/final_crew.json').read_text())['ticket_results']
    assert len(records) == len(actual) == len(historic) == 60
    current_scores, old_scores = [], []
    for ticket, result, old in zip(records, actual, historic):
        assert ticket['record_id'] == result['record_id'] == old['record_id']
        score = (Decimal('0.4') * int(ticket['escalated']) + Decimal(ticket['days_since_created']) / 100 + Decimal(ticket['reopen_count']) / 10).quantize(Decimal('0.000001'))
        previous = (Decimal('0.6') * int(ticket['escalated']) + Decimal('0.4') * ticket['days_since_created'] / 30).quantize(Decimal('0.000001'))
        assert Decimal(str(result['escalation_score'])) == score
        assert Decimal(str(old['escalation_score'])) == previous
        assert result['status'] == ticket['status'] and result['resolution_time_hours'] == ticket['resolution_time_hours']
        current_scores.append(score)
        old_scores.append(previous)
    rank = math.ceil(Decimal('0.8') * len(records))
    threshold = sorted(current_scores)[rank - 1]
    previous_threshold = sorted(old_scores)[rank - 1]
    for result, score in zip(actual, current_scores):
        assert Decimal(str(result['escalation_threshold'])) == threshold
        assert result['recommend_escalation'] == (score > threshold)
    escalation = {
        'method': 'independent exact Decimal calculations against all60 fresh lookup results and archived v1 results',
        'rank': rank, 'v1_threshold': float(previous_threshold), 'v2_threshold': float(threshold),
        'v1_recommended': sum(score > previous_threshold for score in old_scores),
        'v2_recommended': sum(score > threshold for score in current_scores),
        'v1_non_escalated': sum(score > previous_threshold and not t['escalated'] for t, score in zip(records, old_scores)),
        'v2_non_escalated': [
            {'record_id': t['record_id'], 'status': t['status'], 'days_since_created': t['days_since_created'], 'reopen_count': t['reopen_count'], 'score': float(score)}
            for t, score in zip(records, current_scores) if score > threshold and not t['escalated']
        ],
        'v2_ties_excluded': current_scores.count(threshold)
    }

    links = 0
    for path in [ROOT / 'README.md', *(ROOT / 'docs').rglob('*.md'), *(ROOT / 'evidence').rglob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if link.startswith(('http:', 'https:', '#')):
                continue
            target = (path.parent / link.split('#')[0]).resolve()
            assert target.is_relative_to(ROOT) and target.exists(), (path.relative_to(ROOT).as_posix(), link)
            links += 1
    pins = 0
    for line in (ROOT / 'requirements-api.lock').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, expected = line.split('==')
        assert importlib.metadata.version(name) == expected, name
        pins += 1
    findings, manifest = scan.inspect(scan.candidates())
    assert not findings, findings
    result = {
        'timestamp': datetime.now(ZoneInfo('Asia/Calcutta')).isoformat(),
        'result': 'PASSED', 'reviewed_head': git('rev-parse', 'HEAD').decode().strip(),
        'branch': branch, 'original_checkout_preservation_verified': original_verified,
        'baseline_refs_preserved': True, 'reachable_history_scans': history,
        'archived_records': archive_checks, 'escalation_comparison': escalation, 'relative_links_verified': links,
        'exact_dependency_pins_verified': pins, 'intended_files_scanned': len(manifest),
        'current_findings': [], 'README_lines': len((ROOT / 'README.md').read_text().splitlines()),
        'learnings_words': len((ROOT / 'docs/LEARNINGS.md').read_text().split()),
        'limitations': 'Pattern scanning is bounded; no remote branch or visibility verification is claimed. Archive Markdown links may change, but prose is preserved.'
    }
    if not args.no_write:
        (ROOT / 'evidence/v2_final_review.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
