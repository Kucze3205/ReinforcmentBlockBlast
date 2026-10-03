import json,glob,subprocess,re,os,datetime as dt
def adate(p):
    o=subprocess.run(['git','log','--diff-filter=A','--format=%aI','--',p],capture_output=True,text=True).stdout.split()
    return o[-1] if o else None
rec=[]
for f in glob.glob('bench/*.json'):
    try: j=json.load(open(f))
    except: continue
    if not isinstance(j,dict): continue
    c=(j.get('arms') or {}).get('candidate')
    if not c or 'fixed' not in c: continue
    d=adate(f)
    if d: rec.append(dict(t=d,issue=j.get('issue'),mean=c['fixed']['mean'],capped=c['fixed'].get('capped_pct'),cap=j['config'].get('move_cap'),spec=c.get('spec')))
rec.sort(key=lambda r:r['t'])
ser=[]
for s in range(1,8):
    cnt={'cel':0,'przegrana':0,'przerwanie':0};lic=[]
    for f in glob.glob(f'docs/seria/s{s}/partia-*/pomiar.json'):
        j=json.load(open(f));z=j.get('zakonczenie','przerwanie')
        cnt[z]=cnt.get(z,0)+1
        v=(j.get('licznik_apki') or {}).get('wartosc')
        if v: lic.append(v)
    ser.append(dict(s=s,**cnt,lic=lic))
cyc={}
for f in glob.glob('docs/journal/cykl-*.md'):
    d=adate(f)
    if d: cyc[d[:10]]=cyc.get(d[:10],0)+1
com={}
for d in subprocess.run(['git','log','--format=%ad','--date=short'],capture_output=True,text=True).stdout.split():
    if d>='2026-09-20': com[d]=com.get(d,0)+1
json.dump(dict(rec=rec,ser=ser,cyc=cyc,com=com),open('docs/prototypes/strona-dane.json','w'),ensure_ascii=False)
print(len(rec),ser,cyc,com)
