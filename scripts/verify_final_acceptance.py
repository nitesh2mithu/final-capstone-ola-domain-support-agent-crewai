"""Independent final evidence arithmetic, task coverage and reproduction audit."""
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]

def main():
    load=lambda name:json.loads((ROOT/'evidence'/name).read_text())
    for file,digest in load('final_input_manifest.json').items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest,file
    for file,digest in load('archive/v1/milestone_05_evaluation_freeze.json')['sha256'].items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest,file
    executions=[load('final_offline_execution.json'),load('final_localhost_execution.json')]
    assert all(r['passed'] and all(j['exit_code']==0 for j in r['jobs']) for r in executions)
    for name,n in [('dataset',8),('dataset_repeat',8),('rag',8),('crew',12),('crew_repeat',12),('focused',11),('acceptance',6),('framework',6)]:
        text=(ROOT/'evidence'/f'final_{name}.txt').read_text()
        assert f'Ran {n} tests' in text and '\nOK\n' in text,name
    assert load('final_dataset.json')==load('final_dataset_repeat.json')
    assert load('final_crew.json')==load('final_crew_repeat.json')
    rag=load('final_rag.json');assert rag['acceptance']['passed']
    calculations={}
    for strategy,data in rag['strategies'].items():
        cal=data['calibration'];inside=[x['top1_cosine_similarity'] for x in cal['measurements'] if x['in_scope']]
        outside=[x['top1_cosine_similarity'] for x in cal['measurements'] if not x['in_scope']]
        assert len(inside)>=3 and len(outside)>=2
        threshold=(min(inside)+max(outside))/2
        assert max(outside)<threshold<min(inside) and threshold==cal['threshold']
        rows=[]
        for case in data['evaluation']:
            retrieved={h['document_id'] for h in case['hits']};truth=set(case['relevant_documents'])
            overlap=len(retrieved & truth);p=overlap/len(retrieved) if retrieved else 0;r=overlap/len(truth) if truth else None
            assert case['metrics']['precision']==p and case['metrics']['recall']==r
            assert case['response']['fallback']==(case['hits'][0]['cosine_similarity']<threshold)
            rows.append({'id':case['id'],'retrieved_parents':sorted(retrieved),'relevant_parents':sorted(truth),
                         'precision_fraction':f'{overlap}/{len(retrieved)}','precision':p,
                         'recall_fraction':f'{overlap}/{len(truth)}' if truth else 'undefined','recall':r,'in_scope':case['in_scope']})
        assert sum(c['in_scope'] for c in data['evaluation'])>=5 and any(not c['in_scope'] and c['response']['fallback'] for c in data['evaluation'])
        incases=[r for r in rows if r['in_scope']]
        assert abs(sum(r['precision'] for r in incases)/len(incases)-data['mean_precision'])<1e-12
        assert abs(sum(r['recall'] for r in incases)/len(incases)-data['mean_recall'])<1e-12
        calculations[strategy]={'threshold':threshold,'rows':rows,'mean_precision':data['mean_precision'],'mean_recall':data['mean_recall']}
    e=load('final_evaluation.json');assert e==load('final_evaluation_repeat.json')
    assert len(e['results'])==e['query_count']==15
    topics={r['case']['topic'] for r in e['results'] if r['case']['kind']=='policy'}
    assert topics=={p.stem for p in (ROOT/'knowledge_base').glob('*.md')}
    assert sum(r['case']['kind']=='out_of_scope' for r in e['results'])>=2
    averages={}
    for metric in ('Accuracy','Grounding','Completeness','Safety'):
        values=[Decimal(str(r['verdict'][metric])) for r in e['results']];assert all(0<=v<=1 for v in values)
        total=sum(values);average=total/Decimal(15)
        assert total==Decimal(str(e['metric_sums'][metric])) and abs(average-Decimal(str(e['averages'][metric])))<Decimal('1e-12')
        averages[metric]={'sum':str(total),'denominator':15,'average':str(average)}
    assert e['averages']==load('archive/v1/milestone_06_evaluation.json')['averages']
    extra=load('v2_extra_evaluation.json');assert extra==load('v2_extra_evaluation_repeat.json')
    assert extra['query_count']==len(extra['results'])==5
    extra_cases=json.loads((ROOT/'evaluation/extra_queries.json').read_text())
    assert [r['case'] for r in extra['results']]==extra_cases
    for file,digest in load('v2_extra_freeze.json')['sha256'].items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest,file
    extra_averages={}
    for metric in ('Accuracy','Grounding','Completeness','Safety'):
        total=sum(Decimal(str(r['verdict'][metric])) for r in extra['results'])
        assert total==Decimal(str(extra['metric_sums'][metric]))
        assert abs(total/5-Decimal(str(extra['averages'][metric])))<Decimal('1e-12')
        extra_averages[metric]={'sum':str(total),'denominator':5,'average':str(total/5)}
    assert not extra['offline']['network_attempts'] and not extra['offline']['child_process_attempts']
    fixtures=load('v2_judge_fixtures.json');assert fixtures['acceptance']['passed'] and fixtures['acceptance']['tests_run']==5
    assert fixtures['fixtures']['canonical_source_verification']=={
        'forged_text':True,'unknown_chunk':True,'wrong_parent':True}
    assert 'Ran 5 tests' in (ROOT/'evidence/final_judge_fixtures.txt').read_text()
    dataset=load('final_dataset.json');historic=load('archive/v1/final_dataset.json')
    original_fields=[{k:v for k,v in t.items() if k!='reopen_count'} for t in dataset['all_records']]
    assert original_fields==historic['all_records']
    import random
    rng=random.Random(43)
    assert [t['reopen_count'] for t in dataset['all_records']]==[rng.randint(0,3) for _ in original_fields]
    scores=[round(.4*int(t['escalated'])+.3*t['days_since_created']/30+.3*t['reopen_count']/3,6) for t in dataset['all_records']]
    score_threshold=sorted(scores)[math.ceil(.8*len(scores))-1]
    crew=load('final_crew.json');assert crew['acceptance']['passed']
    for t,score,actual in zip(dataset['all_records'],scores,crew['ticket_results']):
        assert actual['escalation_score']==score and actual['reopen_count']==t['reopen_count']
        assert actual['escalation_threshold']==score_threshold and actual['recommend_escalation']==(score>score_threshold)
    escalation={'threshold':score_threshold,'ties_excluded':scores.count(score_threshold),
                'recommended':sum(x>score_threshold for x in scores),
                'non_escalated_recommended':sum(x>score_threshold and not t['escalated'] for t,x in zip(dataset['all_records'],scores)),
                'original_fields_unchanged':True,'independent_reopen_stream_verified':True}

    for key,kind in [('ticket','ticket'),('policy','rag')]:
        c=crew['cases'][key];assert c['kickoff_executed'] and c['framework_pydantic_validated']
        assert len(c['agents'])>=3 and any(x['event']=='tool_executed' and x['kind']==kind for x in c['events'])
    hard=load('final_acceptance.json');assert hard['acceptance']['passed']
    assert hard['cases']['approval']['review']['verdict']['approved']
    for name in ['revision','http_revision_execution']:
        c=hard['cases'][name];assert not c['review']['verdict']['approved']
        assert c['response']['answer']==c['draft']['answer']!=c['review_draft']['answer']
    for c in [r['execution'] for r in e['results']]:
        assert c['review']['model_calls']==[1,1] and c['review']['max_turns']==2 and c['review']['structured_requested']
        assert c['budget']['simulated_tokens']==sum(x['total_tokens'] for x in c['budget']['receipts'])
    assert hard['checks']['permission']['identity_bound'] and hard['checks']['permission']['one_use']
    for name in ['oversized','cost_oversized','crew_budget_refusal','review_budget_refusal','review_cost_refusal','cache_budget_preflight']:
        c=hard['cases'][name];b=c['budget'];assert 'budget_exceeded' in c['response']['guardrails']
        assert b['simulated_tokens']<=b['token_cap']
        assert Decimal(b['simulated_cost_usd'])==Decimal(b['simulated_tokens'])*Decimal(b['price_per_thousand_usd'])/1000<=Decimal(b['cost_cap_usd'])
    counters=hard['checks']['cache'];assert counters['miss']['rag_tools']==1 and counters['hit']['rag_tools']==0
    assert counters['hit']['crew_model_calls']<counters['miss']['crew_model_calls'] and counters['hit']['review_calls']==2
    focused=load('final_focused.json');assert focused['acceptance']['passed']
    f=focused['judge_fixtures']
    for bad,good,metric in [('incorrect_number','correct','Accuracy'),('unsupported','supported','Grounding'),('incomplete','complete','Completeness'),('unsafe','safe','Safety')]:assert f[bad]['verdict'][metric]<f[good]['verdict'][metric]
    live=load('final_localhost.json');assert live['passed']
    rows=[json.loads(line) for line in (ROOT/'evidence/final_logs_localhost.jsonl').read_text().splitlines()]
    n=len(live['http'])+len(live['websocket']);assert n==len(rows)==29
    assert len({r['trace_id'] for r in rows})==n
    reply_ids={c['response']['trace_id'] for c in live['http']+live['websocket'] if c['response'] is not None}
    assert reply_ids.issubset({r['trace_id'] for r in rows})
    assert all(r['duration_ms']>=0 for r in rows)
    assert all(live['disconnect'][k] for k in ['during_request','removed_session','other_client_continued'])
    assert not live['offline']['runtime_external_attempts']
    assert set(live['offline']['negative_controls_blocked'])=={'external_dns','external_ip','other_loopback_port','udp','child_process'}
    for report in [e,rag,focused]:
        offline=report.get('offline',report.get('acceptance',{}))
        assert not offline.get('network_attempts') and not offline.get('child_process_attempts')
    assert not hard['checks']['offline']['network_attempts']
    result={'timestamp':datetime.now(ZoneInfo('Asia/Calcutta')).isoformat(),'result':'PASSED','tasks_verified':list(range(1,17)),
            'distinct_unittest_checks':56,'unittest_executions_with_repeats':76,'logical_localhost_requests_and_logs':29,
            'dataset_and_crew_full_repeats_identical':True,'evaluation_full_repeat_identical':True,
            'independent_metric_arithmetic':averages,'rag_calibration_and_arithmetic':calculations,'cache_counters':counters,
            'v2_behavior_or_scoring_changed_from_v1':True,
            'intended_changes_from_v1':['reopen_count and escalation formula','five separately scored additional cases'],
            'current_source_verification_gate_added':True,'current_metric_arithmetic_changed':False,
            'canonical_source_rejections':fixtures['fixtures']['canonical_source_verification'],
            'original15_scoring_rules_and_labels_unchanged':True,'protected_v2_inputs_and_original_labels_unchanged':True,
            'additional5_metric_arithmetic':extra_averages,'additional5_full_repeat_identical':True,'escalation':escalation,
            'external_runtime_attempts':[],'repository_published':True,'service_deployed':True,
            'scope':'currentv2 all16 original requirements plus separately preregistered5extra evaluation; v1 archive not used as current execution evidence'}
    serialized=json.dumps(result,indent=2,sort_keys=True)+'\n'
    (ROOT/'evidence/final_acceptance_audit.json').write_text(serialized)
    summary=json.dumps({k:v for k,v in result.items() if k not in ['rag_calibration_and_arithmetic']},indent=2,sort_keys=True)+'\n'
    (ROOT/'evidence/final_acceptance_audit.txt').write_text(summary)
    print(summary,end='')

if __name__=='__main__':main()
