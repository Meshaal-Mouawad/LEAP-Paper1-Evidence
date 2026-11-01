#!/usr/bin/env python3
import csv,re,sys
from collections import defaultdict

def norm(s): return re.sub(r'[^a-z0-9]+',' ',(s or '').lower()).strip()
def toks(s): return set(norm(s).split())
def load_gold(path):
    rows=[]
    with open(path,newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get('adjudicated','yes').strip().lower() in {'yes','true','1',''}:
                rows.append(r)
    return rows
def load_pred(path):
    with open(path,newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def match(p,g):
    if p['path']!=g['path']: return False
    try: line=int(p['line']); lo=int(g['calculation_start_line']); hi=int(g['calculation_end_line'])
    except: return False
    region=(lo-3)<=line<=(hi+3)
    nt=toks(p.get('name','')) & toks(g.get('kpi_name',''))
    return region and bool(nt)
def metrics(pred,gold):
    used=set();tp=0
    for p in pred:
        for i,g in enumerate(gold):
            if i not in used and match(p,g): used.add(i);tp+=1;break
    fp=len(pred)-tp;fn=len(gold)-tp
    pr=tp/(tp+fp) if tp+fp else 0; rc=tp/(tp+fn) if tp+fn else 0; f1=2*pr*rc/(pr+rc) if pr+rc else 0
    return tp,fp,fn,pr,rc,f1
if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: score_predictions.py predictions.csv gold_instances.csv')
    tp,fp,fn,p,r,f=metrics(load_pred(sys.argv[1]),load_gold(sys.argv[2]));print(f'TP={tp}\nFP={fp}\nFN={fn}\nprecision={p:.6f}\nrecall={r:.6f}\nF1={f:.6f}')
