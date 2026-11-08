"""Read-only scan of an explicit code/text submission allowlist; no secret values."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'.gitignore','.dockerignore','Dockerfile','vercel.json','Problem_Statement.md','README.md',
            'docs/DEVELOPMENT_PROCESS.md','docs/PROJECT_STATUS.md','docs/ERROR_LOG.md',
            'docs/REQUIREMENTS_TRACKER.md','docs/FINAL_ACCEPTANCE_REPORT.md','dataset.py'}
DIRECTORIES={'docs','support','api','evaluation','knowledge_base','rag','scripts','smoke_tests','tests','evidence'}
FORBIDDEN_PARTS={'.git','.venv','.venv311','.bootstrap','.python','.cache','.runtime','.models',
                 '__pycache__','.aws','.codex','.agents','.vscode'}

def candidates():
    found=[ROOT/p for p in ROOT_FILES if (ROOT/p).is_file()]
    found += list(ROOT.glob('requirements-*.txt'))+list(ROOT.glob('requirements-*.lock'))
    for d in DIRECTORIES:
        found.extend(p for p in (ROOT/d).rglob('*') if p.is_file() and not any(x in FORBIDDEN_PARTS for x in p.relative_to(ROOT).parts))
    return sorted(set(found))

def inspect(paths):
    rules={'personal_absolute_path':re.compile(r'/'+'Users/[^/\s\"\']+|/'+r'home/[^/\s\"\']+|[A-Z]:\\Users\\'),
           'credential_material':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[A-Z0-9]{16}\b|\bsk-[A-Za-z0-9_-]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b'),
           'credential_assignment':re.compile(r'''(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*["'][A-Za-z0-9/+_=.-]{16,}["']'''),
           'credential_url':re.compile(r'https?://[^\s/:]+:[^\s/@]+@'),
           'raw_fabricated_phone':re.compile('98765'+'43210')}
    findings=[];manifest=[]
    phone_pattern=re.compile(r"(?<!\d)(?:(?:\+91|91)[ -]?)?[6-9](?:[ -]?\d){9}(?!\d)")
    uuid_pattern=re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    classified_phone_matches=0
    for p in paths:
        name=p.relative_to(ROOT).as_posix()
        if p.is_symlink() or any(x in FORBIDDEN_PARTS for x in Path(name).parts):
            findings.append({'path':name,'rule':'forbidden_artifact_or_symlink'});continue
        data=p.read_bytes()
        try:text=data.decode('utf-8')
        except UnicodeError:findings.append({'path':name,'rule':'non_text_binary'});continue
        if b'\0' in data:findings.append({'path':name,'rule':'binary_null'})
        if p.suffix not in {'.py','.md','.txt','.lock','.json','.jsonl'} and p.name not in {'.gitignore','.dockerignore','Dockerfile'}:
            findings.append({'path':name,'rule':'unnecessary_format'})
        for rule,pattern in rules.items():
            if pattern.search(text):findings.append({'path':name,'rule':rule})
        for match in phone_pattern.finditer(text):
            a,b=match.span();left=text[max(0,a-80):a];right=text[b:b+80]
            token=re.search(r'[A-Za-z0-9_.-]+$',left)
            combined=(token.group() if token else '')+match.group()+re.match(r'[A-Za-z0-9_.-]*',right).group()
            if (re.fullmatch(r'[0-9a-fA-F]{24,}',combined) or re.fullmatch(r'\d+\.\d+',combined)
                    or uuid_pattern.search(combined)):
                classified_phone_matches+=1
            else:findings.append({'path':name,'rule':'unclassified_fixed_phone_pattern','line':text[:a].count('\n')+1})
        if p.suffix=='.jsonl'  and Path(name).parts[0]!='evidence':findings.append({'path':name,'rule':'noncurated_live_log'})
        manifest.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return findings,manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--staged',action='store_true');parser.add_argument('--list',action='store_true');parser.add_argument('--no-write',action='store_true');args=parser.parse_args()
    paths=candidates()
    for folder in DIRECTORIES:
        if folder not in {"docs","evidence","knowledge_base"}:
            required=set((ROOT/folder).glob("*.py"))
            assert required and required.issubset(set(paths)),"Missing source package: "+folder
    if args.staged:
        names=subprocess.check_output(['git','diff','--cached','--name-only','--diff-filter=ACM','-z'],cwd=ROOT).decode().split('\0')
        paths=[ROOT/n for n in names if n]
        allowed={p.relative_to(ROOT).as_posix() for p in candidates()}
        assert all(p.relative_to(ROOT).as_posix() in allowed for p in paths),'Unexpected staged artifact'
        for p in paths:
            index=subprocess.check_output(['git','show',':'+p.relative_to(ROOT).as_posix()],cwd=ROOT)
            assert index==p.read_bytes(),'Staged content differs from inspected working file: '+p.name
    if args.list:
        for p in paths:print(p.relative_to(ROOT).as_posix())
        return
    findings,manifest=inspect(paths)
    report={'timestamp':datetime.now(ZoneInfo('Asia/Calcutta')).isoformat(),'scope':'staged' if args.staged else 'intended allowlist',
            'result':'PASSED' if not findings else 'FAILED','files_inspected':len(paths),
            'total_text_bytes':sum(m['bytes'] for m in manifest),'findings':findings,
            'checks':['credential signatures and high-entropy assignment literals','credential URLs','personal absolute paths',
                      'raw fabricated phone test sequence','full fixed phone pattern with digest/decimal false-positive classification','binary/unknown formats','runtime/secret directories','noncurated live logs'],
            'limitations':'Static patterns are not exhaustive secret detection. Fixed phone-pattern runs inside long hexadecimal digests or decimal metrics are classified as numeric false positives; runtime masking verified separately.',
            'manifest':manifest}
    suffix='staged_inspection' if args.staged else 'submission_inspection'
    if not args.no_write:
        (ROOT/f'evidence/final_{suffix}.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='manifest'},indent=2))
    if findings:raise SystemExit(1)

if __name__=='__main__':main()
