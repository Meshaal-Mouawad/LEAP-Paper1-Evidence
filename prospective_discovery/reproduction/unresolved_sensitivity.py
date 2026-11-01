"""Predeclared all-positive/all-negative source-oracle uncertainty scenarios, separate from primary scores."""
import argparse,csv,copy
from common import load,write
from score import evaluate

def scenarios(gold,predictions,audit,possible,system,language):
    positive=copy.deepcopy(gold);negative=copy.deepcopy(gold);negative['unresolved']=[];positive['unresolved']=[]
    relevant=[r for r in gold.get('unresolved',[]) if r['file'].endswith('.py' if language=='python' else '.sql')]
    for r in relevant:
        positive['gold'].append(dict(r,language=language,name=r.get('name','UNRESOLVED_SOURCE_IDENTITY')))
    unresolved_ids={r['id'] for r in relevant};pred_ids={r['id'] for r in predictions}
    extra=[]
    for r in possible:
        if r['system']!=system:continue
        if r['prediction_id'] not in pred_ids or r['unresolved_id'] not in unresolved_ids:raise ValueError('Invalid possible edge')
        if not r['rationale'].strip() or r['identity_possible'] not in {'YES','NO'}:raise ValueError('Source-based possibility judgment required')
        if r['identity_possible']=='YES':extra.append(dict(prediction_id=r['prediction_id'],gold_id=r['unresolved_id'],identity_corresponds='YES',rationale=r['rationale'],scorer_variant='primary'))
    return dict(unresolved_source_identities=len(relevant),all_unresolved_negative=evaluate(negative,predictions,audit,'primary',language),all_unresolved_positive=evaluate(positive,predictions,audit+extra,'primary',language),interpretation='Predeclared scenarios, not population confidence bounds; report full unresolved register and source-audited possible edges')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gold',required=True);p.add_argument('--prediction',action='append',required=True);p.add_argument('--audit',required=True);p.add_argument('--possible-edges',required=True);p.add_argument('--system',required=True);p.add_argument('--language',default='python',choices=['python','sql']);p.add_argument('--output',required=True);a=p.parse_args()
    preds=[]
    for path in a.prediction:
        obj=load(path)
        if obj['system']!=a.system:raise ValueError('Use one system per sensitivity run')
        preds.extend(obj['records'])
    def rows(path):
        with open(path,newline='') as f:return list(csv.DictReader(f))
    write(a.output,scenarios(load(a.gold),preds,[r for r in rows(a.audit) if r['system']==a.system],rows(a.possible_edges),a.system,a.language))
