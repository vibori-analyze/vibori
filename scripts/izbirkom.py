#!/usr/bin/env python3
"""Возобновляемый импорт публичных страниц ЦИК/ГАС «Выборы» в Vibori v1."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from urllib.parse import parse_qs, quote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
import hashlib, json, re

SPACE=re.compile(r'\s+')
def clean(x): return SPACE.sub(' ',unescape(x or '')).strip()
def stable(x): return re.sub('[^a-z0-9]+','-',x.lower()).strip('-')+'-'+hashlib.sha1(x.encode()).hexdigest()[:8]
class Page(HTMLParser):
 def __init__(self): super().__init__(); self.links=[];self.text=[];self.rows=[];self.href=None;self.row=None;self.cell=None
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=='a': self.href=a.get('href')
  if t=='tr': self.row=[]
  if t in ('td','th') and self.row is not None:self.cell=[]
 def handle_data(self,d):
  self.text.append(d)
  if self.cell is not None:self.cell.append(d)
 def handle_endtag(self,t):
  if t=='a' and self.href:self.links.append(self.href);self.href=None
  if t in ('td','th') and self.cell is not None:self.row.append(clean(''.join(self.cell)));self.cell=None
  if t=='tr' and self.row is not None:
   if self.row:self.rows.append(self.row)
   self.row=None
def canonical(u):
 p=urlparse(u);q=parse_qs(p.query,keep_blank_values=True); qs='&'.join(f'{quote(k)}={quote(v)}' for k in sorted(q) for v in sorted(q[k]));return urlunparse((p.scheme,p.netloc,p.path,'',qs,''))
def vrn(u):return (parse_qs(urlparse(u).query).get('vrn')or[None])[0]
def number(s):
 m=re.search(r'(?<!\d)(\d[\d\s ]*)(?!\d)',s);return int(re.sub(r'\D','',m.group(1))) if m else None
def fetch(url,cfg,raw,emit):
 path=raw/(hashlib.sha256(url.encode()).hexdigest()+'.html')
 if path.exists():
  emit('cached',url=url,file=str(path));return path.read_text(errors='replace')
 req=Request(url,headers={'User-Agent':cfg['request']['user_agent'],'Accept':'text/html,application/xhtml+xml'})
 for attempt in range(cfg['request'].get('retries',1)):
  try:
   emit('fetch',url=url,attempt=attempt+1,retries=cfg['request'].get('retries',1))
   with urlopen(req,timeout=cfg['request']['timeout_seconds']) as r: body=r.read().decode(r.headers.get_content_charset()or'utf-8',errors='replace')
   break
  except Exception as error:
   if attempt+1 == cfg['request'].get('retries',1): raise
   emit('retry',url=url,attempt=attempt+1,error=str(error))
   sleep(cfg['request'].get('retry_delay_seconds',2)*(attempt+1))
 path.write_text(body);path.with_suffix('.source.json').write_text(json.dumps({'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'publisher':'ЦИК России / ГАС «Выборы»'},ensure_ascii=False,indent=2)+'\n');emit('saved',url=url,file=str(path));sleep(cfg['request']['delay_seconds']);return body
def protocol(page,url,campaign,cfg):
 text=clean(' '.join(page.text));m=re.search(cfg['protocol']['precinct_pattern'],text,re.I)
 if not m:return None
 turnout={k:None for k in ('registered','issued','valid','invalid')}; entities=[]
 for row in page.rows:
  line=' '.join(row); votes=number(row[-1]) if row else None
  if votes is None:continue
  hit=False
  for key,patterns in cfg['protocol']['turnout_aliases'].items():
   if any(re.search(x,line,re.I) for x in patterns):turnout[key]=votes;hit=True;break
  if not hit and len(row)>=2 and not re.search(r'итог|сведения|участк|протокол',line,re.I):
   name=clean(row[0])
   if len(name)>2 and not re.fullmatch(r'\d+',name):entities.append((name,votes))
 if any(x is None for x in turnout.values()) or len(entities)<cfg['protocol']['minimum_entities']:return None
 n=m.group(1);reg=(re.search(cfg['protocol']['region_pattern'],text,re.I)or[campaign['name']])[0];tik=(re.search(cfg['protocol']['tik_pattern'],text,re.I)or['Не указана'])[0];eid=campaign['id']
 return {'standard':'vibori-election-result/v1','source':{'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'publisher':'ЦИК России / ГАС «Выборы»'},'election':{'id':eid,'name':campaign['name'],'country':'RU','date':'1970-01-01','scope':'other'},'unit':{'id':f'{eid}-uik-{n}','name':f'УИК №{n}','number':n,'kind':'precinct','administrative_path':[{'id':'ru','name':'Российская Федерация','kind':'national'},{'id':'region-'+stable(reg),'name':reg,'kind':'region'},{'id':'tik-'+stable(tik),'name':tik,'kind':'territorial_commission'}]},'ballot':{'id':'main','title':campaign['name'],'kind':'other'},'turnout':turnout,'results':[{'entity':{'id':'candidate-'+stable(name),'name':name,'type':'candidate'},'votes':votes}for name,votes in entities]}
def main():
 a=ArgumentParser();a.add_argument('--config',default='config/izbirkom.json');a.add_argument('--out',default='public/data');a.add_argument('--raw',default='raw/izbirkom');a.add_argument('--max-pages',type=int);a.add_argument('--only-vrn');a.add_argument('--dry-run',action='store_true');args=a.parse_args();cfg=json.loads(Path(args.config).read_text());raw=Path(args.raw);raw.mkdir(parents=True,exist_ok=True);out=Path(args.out);limit=args.max_pages or cfg['discovery']['max_pages'];queue=[canonical(x)for x in cfg['seed_urls']];seen=set();campaigns={};imported=0
 def emit(event,**data): print(json.dumps({'event':event,**data},ensure_ascii=False),flush=True)
 emit('start',limit=limit,seeds=len(queue),dry_run=args.dry_run)
 while queue and len(seen)<limit:
  url=queue.pop(0)
  if url in seen or(args.only_vrn and vrn(url)!=args.only_vrn):continue
  seen.add(url)
  if len(seen)==1 or len(seen)%cfg['discovery'].get('progress_every_pages',25)==0: emit('progress',pages=len(seen),queued=len(queue),campaigns=len(campaigns),protocols=imported,limit=limit)
  try:body=fetch(url,cfg,raw,emit)
  except Exception as e:emit('fetch_error',url=url,error=str(e));continue
  page=Page();page.feed(body);key=vrn(url);text=clean(' '.join(page.text))
  if key:campaigns.setdefault(key,{'id':'izbirkom-'+key,'name':text[:cfg['discovery']['campaign_title_length']]or'Кампания '+key})
  if key:
   rec=protocol(page,url,campaigns[key],cfg)
   if rec:
    target=out/rec['election']['id']/'precincts'/(rec['unit']['id']+'.json');target.parent.mkdir(parents=True,exist_ok=True)
    if not args.dry_run:target.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    imported+=1;emit('protocol',file=str(target),url=url,protocols=imported)
  for href in page.links:
   target=canonical(urljoin(url,href));host=urlparse(target).netloc
   if host in cfg['allowed_hosts'] and(len(queue)+len(seen)<limit)and(vrn(target)or re.search(cfg['discovery']['follow_pattern'],target)):queue.append(target)
 event={'event':'complete','pages':len(seen),'campaigns':len(campaigns),'protocols':imported,'next':'nix run .#build-index'}
 if not campaigns:event['warning']='Не получено ни одной страницы кампании: проверьте DNS/маршрут до www.izbirkom.ru или капчу ЦИК.'
 print(json.dumps(event,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
