import urllib.request, concurrent.futures, pathlib, re, json
from html.parser import HTMLParser
from urllib.parse import urljoin
ROOT=pathlib.Path(__file__).parent
class Page(HTMLParser):
 def __init__(self,s):
  super().__init__();self.text=[];self.links=[];self.media=[];self.skip=0;self.feed(s)
 def handle_starttag(self,t,a):
  d=dict(a)
  if t in ('script','style'):self.skip+=1
  if t=='a' and d.get('href'):self.links.append(d['href'])
  if t in ('img','video','source','iframe'):self.media.append(d)
 def handle_endtag(self,t):
  if t in ('script','style'):self.skip=max(0,self.skip-1)
 def handle_data(self,s):
  if not self.skip and s.strip():self.text.append(s.strip())
def fetch(k,u):
 try:
  b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=40).read()
  (ROOT/'sources'/f'{k}.html').write_bytes(b)
  p=Page(b.decode(errors='replace'));(ROOT/'sources'/f'{k}.read.txt').write_text('\n'.join(p.text))
  (ROOT/'sources'/f'{k}.meta.json').write_text(json.dumps({'url':u,'links':[urljoin(u,v) for v in p.links],'media':p.media},indent=2))
  return k,len(b)
 except Exception as e:return k,str(e)
urls={
 'datacenter':'https://robocurve.org/datacenterbench/',
 'casa_home':'https://robocasa.ai/',
 'casa_atomic':'https://robocasa.ai/docs/build/html/tasks/atomic_tasks.html',
 'casa_composite':'https://robocasa.ai/docs/build/html/tasks/composite_tasks.html',
 'casa_multi':'https://robocasa.ai/docs/build/html/benchmarking/multi_task_learning.html',
 'casa_old':'https://robocasa.ai/docs/v0.2/tasks.html',
 'libero_home':'https://libero-project.github.io/',
 'libero_paper':'https://arxiv.org/html/2306.03310',
 'simpler_home':'https://simpler-env.github.io/',
 'simpler_paper':'https://arxiv.org/html/2405.05941',
 'dojo_home':'https://robodojo-benchmark.com/',
 'dojo_sim':'https://robodojo-benchmark.com/doc/sim-tasks/',
 'dojo_real':'https://robodojo-benchmark.com/doc/real-tasks/',
 'dojo_eval':'https://robodojo-benchmark.com/doc/usage/quick-evaluation/',
 'dojo_paper':'https://arxiv.org/html/2607.04434',
 'behavior_home':'https://behavior.stanford.edu/',
 'behavior_eval':'https://behavior.stanford.edu/challenge/evaluation.html',
 'behavior_gallery':'https://behavior.stanford.edu/challenge/demo_gallery.html',
 'behavior_kb':'https://behavior.stanford.edu/knowledgebase/',
 'behavior_paper':'https://arxiv.org/html/2403.09227',
 'behavior_old':'https://stanfordvl.github.io/behavior/activities.html',
 'bddl_tree':'https://api.github.com/repos/StanfordVL/bddl/git/trees/master?recursive=1',
 'behavior_tree':'https://api.github.com/repos/StanfordVL/BEHAVIOR-1K/git/trees/main?recursive=1',
 'casa_tree':'https://api.github.com/repos/robocasa/robocasa/git/trees/main?recursive=1',
}
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
  for r in ex.map(lambda kv:fetch(*kv),urls.items()):print(r,flush=True)
