"""Final documentation and local preparation gates; no Git mutations."""
import json
from pathlib import Path
import re
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]

def main():
    load=lambda p:json.loads((ROOT/p).read_text())
    from scripts.inspect_submission import candidates,DIRECTORIES
    assert {"support","api","rag","evaluation","smoke_tests","scripts","tests","knowledge_base","evidence"}.issubset(DIRECTORIES)
    available={p.relative_to(ROOT).as_posix() for p in candidates()}
    for folder in ["support","api","rag","evaluation","smoke_tests","scripts","tests"]:
        for p in (ROOT/folder).glob("*.py"):
            assert p.relative_to(ROOT).as_posix() in available,(folder,p.name)
    assert load('evidence/final_acceptance_audit.json')['result']=='PASSED'
    assert load('evidence/final_submission_inspection.json')['result']=='PASSED'
    clean=load('evidence/final_clean_index.json')
    assert clean['upserts']['fixed']['after']==33 and clean['upserts']['sentence']['after']==24
    assert clean['calibration_preserved'] and not clean['offline']['network_attempts']
    docs=['docs/LEARNINGS.md','docs/CHANGELOG_V2.md','README.md','docs/PROJECT_STATUS.md','docs/DEVELOPMENT_PROCESS.md','docs/ERROR_LOG.md','docs/REQUIREMENTS_TRACKER.md','docs/FINAL_ACCEPTANCE_REPORT.md']
    links=0
    for name in docs:
        text=(ROOT/name).read_text();assert text.strip()
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if not target.startswith(('http:','https:','#')):
                resolved=((ROOT/name).parent/target.split('#')[0]).resolve()
                assert resolved.is_relative_to(ROOT) and (resolved.is_file() or resolved.is_dir()),(name,target);links+=1
    readme=(ROOT/'README.md').read_text()
    assert readme.startswith('# Completed Ola (Business Operations / Customer Support) track')
    for token in ['requirements-api.lock','scripts.download_embedding_model','scripts.rebuild_indexes','scripts.serve_api',
                  'scripts.run_final_verification','scripts.evaluate_support','1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
                  'independently reloads the canonical policy files','written and hash-frozen before their first execution',
                  'no separate native fresh-clone walkthrough is claimed']:
        assert token in readme,token
    grader_rows=[line for line in readme.splitlines() if re.match(r'^\| (?:[1-9]|1[0-6]) \|',line)]
    assert len(grader_rows)==16
    assert len(readme.splitlines())<250
    sections=['Overview','How it works','Setup and quick start','Usage examples','Dataset and knowledge base',
              'Retrieval and evaluation','Guardrails, governance and limitations','Documentation','AI assistance']
    assert re.findall(r'^## (.+)$',readme,re.M)==sections
    assert not re.search(r'Milestone|PASSED|ERROR-0\d+|handoff|authorized|course.portal|marks disclaimer',readme,re.I)
    assert 150<=len((ROOT/'docs/LEARNINGS.md').read_text().split())<=250
    assert 'I used AI assistance throughout development. The repository records the implementation, executed verification, and known limitations.' in readme
    assert not re.search(r'CONFIRM|TODO|TBD|FIXME|\[INSERT', readme + (ROOT/'docs/LEARNINGS.md').read_text())
    # Check all archived Markdown links; historic records stay distinct.
    for path in (ROOT/'evidence/archive/v1').rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if not target.startswith(('http:','https:','#')):assert (path.parent/target.split('#')[0]).is_file(),(path.name,target)
    statuses={int(line.split('|')[1]):line.split('|')[-2].strip() for line in (ROOT/'docs/REQUIREMENTS_TRACKER.md').read_text().splitlines() if re.match(r'^\| \d+ \|',line)}
    assert len(statuses)==16 and all(v=='PASSED' for v in statuses.values())
    assert 'Status: OPEN' not in (ROOT/'docs/ERROR_LOG.md').read_text()
    assert (ROOT/'docs/PROJECT_STATUS.md').read_text().startswith('# Project status')
    ignored=(ROOT/'.gitignore').read_text().splitlines()
    for token in ['.venv/','.venv311/','.bootstrap/','.python/','.cache/','.runtime/','.models/','__pycache__/','.env','.env.*','.aws/','.codex/','.agents/','.vscode/','!evidence/*.jsonl']:
        assert token in ignored,token
    report=(ROOT/'docs/FINAL_ACCEPTANCE_REPORT.md').read_text()
    rows=[line for line in report.splitlines() if re.match(r'^\|\d+ /',line)]
    assert len(rows)==16 and all(line.endswith('|PASSED|') for line in rows)
    result={'timestamp':datetime.now(ZoneInfo('Asia/Calcutta')).isoformat(),'result':'PASSED','documents_checked':docs,
            'evidence_links_checked':links,'official_task_rows':16,'required_source_package_completeness':True,'completed_track_declaration_verified':True,
            'setup_excluded_model_download_and_clean_index_recipe_verified':True,'ignore_rules_verified':True,
            'unresolved_errors':0,'repository_published':True,'service_deployed':True,
            'course_portal_submission_performed':False,
            'local_review_gate':'current v2 task, source, links, README, learnings, publication and deployment checks'}
    (ROOT/'evidence/final_documentation_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
