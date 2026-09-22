#!/usr/bin/env python3
"""Resumable import of public election pages into Vibori v1."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from urllib.parse import parse_qs, quote, urljoin, urlparse, urlunparse
from urllib.request import Request, ProxyHandler, build_opener
import hashlib, json, os, re, socket

SPACE=re.compile(r'\s+')
def clean(x): return SPACE.sub(' ',unescape(x or '')).strip()
def stable(x): return re.sub('[^a-z0-9]+','-',x.lower()).strip('-')+'-'+hashlib.sha1(x.encode()).hexdigest()[:8]
class Page(HTMLParser):
 def __init__(self): super().__init__(); self.links=[];self.assets=[];self.base=None;self.text=[];self.rows=[];self.href=None;self.row=None;self.cell=None
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=='a': self.href=a.get('href')
  if t=='base' and a.get('href'): self.base=a['href']
  if t=='script' and a.get('src'): self.assets.append(a['src'])
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
def load_dotenv(path=Path('.env')):
 if not path.exists(): return
 for line in path.read_text().splitlines():
  key,sep,value=line.partition('=')
  if sep and key and not key.startswith('#'): os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
def fetch(url,cfg,raw,emit,opener):
 path=raw/(hashlib.sha256(url.encode()).hexdigest()+'.html')
 if path.exists():
  emit('cached',url=url,file=str(path));return path.read_text(errors='replace')
 req=Request(url,headers={'User-Agent':cfg['request']['user_agent'],'Accept':'text/html,application/xhtml+xml'})
 for attempt in range(cfg['request'].get('retries',1)):
  try:
   emit('fetch',url=url,attempt=attempt+1,retries=cfg['request'].get('retries',1))
   with opener.open(req,timeout=cfg['request']['timeout_seconds']) as r: body=r.read().decode(r.headers.get_content_charset()or'utf-8',errors='replace')
   break
  except Exception as error:
   if attempt+1 == cfg['request'].get('retries',1): raise
   emit('retry',url=url,attempt=attempt+1,error=str(error))
   sleep(cfg['request'].get('retry_delay_seconds',2)*(attempt+1))
 path.write_text(body);path.with_suffix('.source.json').write_text(json.dumps({'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'publisher':'Central Election Commission of Russia'},ensure_ascii=False,indent=2)+'\n');emit('saved',url=url,file=str(path));sleep(cfg['request']['delay_seconds']);return body
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
  if not hit and len(row)>=2 and not re.search(cfg['protocol']['non_entity_pattern'],line,re.I):
   name=clean(row[0])
   if len(name)>2 and not re.fullmatch(r'\d+',name):entities.append((name,votes))
 if any(x is None for x in turnout.values()) or len(entities)<cfg['protocol']['minimum_entities']:return None
 n=m.group(1);reg=(re.search(cfg['protocol']['region_pattern'],text,re.I)or[campaign['name']])[0];tik=(re.search(cfg['protocol']['tik_pattern'],text,re.I)or['Not specified'])[0];eid=campaign['id']
 return {'standard':'vibori-election-result/v1','source':{'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'publisher':'Central Election Commission of Russia'},'election':{'id':eid,'name':campaign['name'],'country':'RU','date':'1970-01-01','scope':'other'},'unit':{'id':f'{eid}-uik-{n}','name':f'Precinct {n}','number':n,'kind':'precinct','administrative_path':[{'id':'ru','name':'Russian Federation','kind':'national'},{'id':'region-'+stable(reg),'name':reg,'kind':'region'},{'id':'tik-'+stable(tik),'name':tik,'kind':'territorial_commission'}]},'ballot':{'id':'main','title':campaign['name'],'kind':'other'},'turnout':turnout,'results':[{'entity':{'id':'candidate-'+stable(name),'name':name,'type':'candidate'},'votes':votes}for name,votes in entities]}
def main():
 load_dotenv();a=ArgumentParser();a.add_argument('--config',default='config/izbirkom.json');a.add_argument('--out',default='public/data');a.add_argument('--raw',default='raw/izbirkom');a.add_argument('--max-pages',type=int);a.add_argument('--only-vrn');a.add_argument('--proxy',help='HTTP(S) or SOCKS5 proxy URL');a.add_argument('--dry-run',action='store_true');args=a.parse_args();cfg=json.loads(Path(args.config).read_text());raw=Path(args.raw);raw.mkdir(parents=True,exist_ok=True);out=Path(args.out);limit=args.max_pages or cfg['discovery']['max_pages'];queue=[canonical(x)for x in cfg['seed_urls']];seen=set();campaigns={};imported=0
 proxy=args.proxy or os.environ.get('VIBORI_PROXY') or cfg['request'].get('proxy') or None
 if proxy and urlparse(proxy).scheme not in ('http','https','socks5','socks5h'):raise SystemExit('Proxy must use http://, https://, socks5://, or socks5h://')
 if proxy and urlparse(proxy).scheme.startswith('socks'):
  import socks
  parsed=urlparse(proxy);socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5,parsed.hostname,parsed.port or 1080,rdns=parsed.scheme=='socks5h');socket.socket=socks.socksocket;opener=build_opener(ProxyHandler({}))
 else: opener=build_opener(ProxyHandler({'http':proxy,'https':proxy}) if proxy else ProxyHandler({}))
 def emit(event,**data): print(json.dumps({'event':event,**data},ensure_ascii=False),flush=True)
 proxy_public=(urlparse(proxy).scheme+'://'+urlparse(proxy).hostname) if proxy else None
 emit('start',limit=limit,seeds=len(queue),dry_run=args.dry_run,proxy=proxy_public)
 while queue and len(seen)<limit:
  url=queue.pop(0)
  if url in seen or(args.only_vrn and vrn(url)!=args.only_vrn):continue
  seen.add(url)
  if len(seen)==1 or len(seen)%cfg['discovery'].get('progress_every_pages',25)==0: emit('progress',pages=len(seen),queued=len(queue),campaigns=len(campaigns),protocols=imported,limit=limit)
  try:body=fetch(url,cfg,raw,emit,opener)
  except Exception as e:emit('fetch_error',url=url,error=str(e));continue
  page=Page();page.feed(body);key=vrn(url);text=clean(' '.join(page.text))
  if key:campaigns.setdefault(key,{'id':'izbirkom-'+key,'name':text[:cfg['discovery']['campaign_title_length']]or'Campaign '+key})
  if key:
   rec=protocol(page,url,campaigns[key],cfg)
   if rec:
    target=out/rec['election']['id']/'precincts'/(rec['unit']['id']+'.json');target.parent.mkdir(parents=True,exist_ok=True)
    if not args.dry_run:target.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    imported+=1;emit('protocol',file=str(target),url=url,protocols=imported)
  for href in page.links:
   target=canonical(urljoin(url,href));host=urlparse(target).netloc
   if host in cfg['allowed_hosts'] and(len(queue)+len(seen)<limit)and(vrn(target)or re.search(cfg['discovery']['follow_pattern'],target)):queue.append(target)
  asset_base=urljoin(url,page.base) if page.base else url
  for href in page.assets:
   target=canonical(urljoin(asset_base,href));host=urlparse(target).netloc
   if host in cfg['allowed_hosts'] and re.search(cfg['discovery']['asset_pattern'],urlparse(target).path) and target not in seen:
    queue.append(target);emit('spa_asset',url=target)
  for endpoint in re.findall(cfg['discovery']['api_url_pattern'],body):
   target=canonical(urljoin(url,endpoint));host=urlparse(target).netloc
   if host in cfg['allowed_hosts'] and target not in seen:
    queue.append(target);emit('api_candidate',url=target)
 event={'event':'complete','pages':len(seen),'campaigns':len(campaigns),'protocols':imported,'next':'nix run .#build-index'}
 if not campaigns:event['warning']='No campaign page was received. Check DNS/routing to www.izbirkom.ru or a CEC CAPTCHA.'
 print(json.dumps(event,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
