"""Regenerate discovery metrics from frozen source gold and independently audited matching edges."""
import argparse,csv,random,math
from collections import defaultdict,Counter
from common import load,write

def metrics(tp,fp,fn):
    return dict(TP=tp,FP=fp,FN=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
def matching(preds,gold,edges):
    owner={};chosen={}
    def visit(pid,seen):
        for gid in sorted(edges[pid]):
            if gid in seen:continue
            seen.add(gid)
            if gid not in owner or visit(owner[gid],seen):
                owner[gid]=pid;chosen[pid]=gid;return True
        return False
    for p in sorted(preds,key=lambda p:(p['channel']!='PROMOTED',p['id'])):visit(p['id'],set())
    # The owner map is authoritative after augmenting paths.
    return {pid:gid for gid,pid in owner.items()}
def percentile(xs,q):
    xs=sorted(xs);i=(len(xs)-1)*q;lo=math.floor(i);hi=math.ceil(i)
    return xs[lo]+(xs[hi]-xs[lo])*(i-lo)
def evaluate(gold,predictions,audit,variant='primary',language='python'):
    repositories=gold['repositories']
    if len(set(repositories))!=len(repositories) or not repositories:raise ValueError('Invalid repository inventory')
    def index(rows):
        d={r['id']:r for r in rows}
        if len(d)!=len(rows):raise ValueError('Duplicate identity')
        return d
    g=index([r for r in gold['gold'] if r['language']==language]);allg=index(gold['gold'])
    members={(r['repository'],r['file']) for r in gold['files']}
    if not members:raise ValueError('Frozen file inventory required')
    p=index([r for r in predictions if r['file'].endswith('.py' if language=='python' else '.sql')])
    if any(r['repository'] not in repositories for r in [*allg.values(),*p.values()]):raise ValueError('Unknown repository')
    if any((r['repository'],r['file']) not in members for r in [*allg.values(),*p.values()]):raise ValueError('Outside frozen file inventory')
    if any(r.get('channel') not in {'PROMOTED','REVIEW'} for r in p.values()):raise ValueError('Invalid prediction channel')
    dispositions=defaultdict(list)
    for r in audit:
        if r['scorer_variant']!=variant:continue
        if r['prediction_id'] in p:dispositions[r['prediction_id']].append(r)
    if set(dispositions)!=set(p):raise ValueError('Every prediction requires an audited disposition')
    edges=defaultdict(set);ambiguous=[]
    for pid,pr in p.items():
        if not isinstance(pr['line'],int) or pr['line']<1:raise ValueError('Invalid anchor')
        unresolved=[u for u in gold.get('unresolved',[]) if (u['repository'],u['file'])==(pr['repository'],pr['file']) and u['start_line']<=pr.get('end_line',pr['line']) and pr['line']<=u['end_line']]
        if unresolved:ambiguous.append(pid)
        for row in dispositions[pid]:
            if not row.get('rationale','').strip():raise ValueError('Missing audit rationale')
            gid=row['gold_id']
            if not gid:continue
            if gid not in g:raise ValueError('Unknown or wrong-language gold')
            target=g[gid]
            if row['identity_corresponds']!='YES':continue
            if (target['repository'],target['file'])!=(pr['repository'],pr['file']):raise ValueError('Cross-source edge')
            valid=(target['start_line']<=pr['line']<=target['end_line']) if variant=='primary' else (pr['line']==target['start_line']) if variant=='exact_start' else (pr['line']<=target['end_line'] and pr.get('end_line',pr['line'])>=target['start_line'])
            if not valid:raise ValueError('Edge violates frozen matching variant')
            edges[pid].add(gid)
    result={}
    for channel in ['PROMOTED','REVIEW','COMBINED']:
        selected=[r for pid,r in p.items() if pid not in ambiguous and (channel=='COMBINED' or r['channel']==channel)]
        matches=matching(selected,g,edges)
        per={}
        for repo in repositories:
            ids={r['id'] for r in selected if r['repository']==repo};gids={gid for gid,r in g.items() if r['repository']==repo}
            found={gid for pid,gid in matches.items() if pid in ids};tp=len(found)
            per[repo]=metrics(tp,len(ids)-tp,len(gids)-tp)
        pooled=metrics(sum(x['TP'] for x in per.values()),sum(x['FP'] for x in per.values()),sum(x['FN'] for x in per.values()))
        loo={repo:metrics(*(sum(v[k] for key,v in per.items() if key!=repo) for k in ['TP','FP','FN'])) for repo in repositories}
        macro=[v['f1'] for v in per.values() if v['f1'] is not None]
        result[channel]=dict(pooled=pooled,per_repository=per,leave_one_repository_out=loo,macro_f1=sum(macro)/len(macro) if macro else None,accepted_matches=matches,fp_prediction_ids=sorted({r['id'] for r in selected}-set(matches)),fn_gold_ids=sorted(set(g)-set(matches.values())),unresolved_prediction_ids=sorted(ambiguous),review_count=sum(r['channel']=='REVIEW' for r in p.values()))
    return result

def bootstrap(a,b,repos,n=10000):
    rng=random.Random(20261028);values=[];undefined=0
    for _ in range(n):
        sampled=rng.choices(repos,k=len(repos));rates=[]
        for table in [a,b]:rates.append(metrics(*(sum(table[r][k] for r in sampled) for k in ['TP','FP','FN']))['f1'])
        if None in rates:undefined+=1
        else:values.append(rates[0]-rates[1])
    return dict(seed=20261028,replicates=n,undefined=undefined,lower=percentile(values,.025) if values else None,upper=percentile(values,.975) if values else None)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gold',required=True);p.add_argument('--prediction',action='append',required=True);p.add_argument('--audit',required=True);p.add_argument('--language',choices=['python','sql'],default='python');p.add_argument('--variant',choices=['primary','exact_start','span_overlap'],default='primary');p.add_argument('--output',required=True);a=p.parse_args()
    gold=load(a.gold);systems=defaultdict(list)
    for path in a.prediction:
        obj=load(path);systems[obj['system']].extend(obj['records'])
    with open(a.audit,newline='') as f:audit=list(csv.DictReader(f))
    tables={system:evaluate(gold,rows,[r for r in audit if r['system']==system],a.variant,a.language) for system,rows in systems.items()}
    result={'variant':a.variant,'language':a.language,'systems':tables}
    if {'leap_next','structural'}<=set(tables):
        left=tables['leap_next']['PROMOTED'];right=tables['structural']['PROMOTED']
        result['primary_f1_difference']=None if None in [left['pooled']['f1'],right['pooled']['f1']] else left['pooled']['f1']-right['pooled']['f1']
        result['paired_repository_bootstrap']=bootstrap(left['per_repository'],right['per_repository'],gold['repositories'])
    write(a.output,result)
