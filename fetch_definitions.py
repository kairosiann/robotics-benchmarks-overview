from fetch_sources import *
p=ROOT/'sources'
jobs={
 'dc_setup_js':'https://robocurve.org/datacenterbench/setups.c67e16b622.js',
 'casa_raw_attributes':'https://raw.githubusercontent.com/robocasa/robocasa/main/docs/composite_tasks/task_attributes.json',
 'libero_eval':'https://raw.githubusercontent.com/Lifelong-Robot-Learning/LIBERO/master/libero/lifelong/metric.py',
 'simpler_init':'https://raw.githubusercontent.com/simpler-env/SimplerEnv/main/simpler_env/__init__.py',
}
tree=json.loads((p/'behavior_tree.html').read_text())
for x in tree['tree']:
 if x['path'].endswith('.bddl') and '/activity_definitions/' in x['path'] and '/problem' in x['path']:
  name=x['path'].split('/')[-2]+'_'+x['path'].split('/')[-1].replace('.bddl','')
  jobs['bddl_'+name]='https://raw.githubusercontent.com/StanfordVL/BEHAVIOR-1K/'+tree['sha']+'/'+x['path']
libtree='https://api.github.com/repos/Lifelong-Robot-Learning/LIBERO/git/trees/master?recursive=1'
try:
 d=json.load(urllib.request.urlopen(libtree));(p/'libero_tree.json').write_text(json.dumps(d))
 for x in d['tree']:
  if x['path'].endswith('.bddl') and '/bddl_files/' in x['path']:jobs['libddl_'+x['path'].split('/')[-2]+'_'+x['path'].split('/')[-1][:-5]]='https://raw.githubusercontent.com/Lifelong-Robot-Learning/LIBERO/'+d['sha']+'/'+x['path']
except Exception as e:print(e)
def raw(k,u):
 f=p/(k+'.raw')
 if f.exists():return True
 try:f.write_bytes(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=40).read());return True
 except Exception as e:print(k,str(e),flush=True);return False
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
 results=list(ex.map(lambda kv:raw(*kv),jobs.items()));print('Definitions fetched',sum(results),'of',len(jobs))
