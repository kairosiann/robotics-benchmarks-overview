import ast, json, re, pathlib, html
from fetch_sources import Page
from task_details import BEHAVIOR_GALLERY, SIMPLER_MEDIA, casa_setup_summary, enrich_task, readable_name
from urllib.parse import urljoin
ROOT=pathlib.Path(__file__).parent; P=ROOT/'sources'
def read(n):return (P/n).read_text()
def goal(s):
 start=s.find('(:goal')
 if start<0:return ''
 depth=0
 for i in range(start,len(s)):
  if s[i]=='(':depth+=1
  if s[i]==')':depth-=1
  if depth==0:return s[start:i+1]
 return s[start:]
rows=[]
def add(b,s,n,d='',g='',u='',*,details=None,**kw):
 task=dict(benchmark=b,suite=s,name=n,description=d,goal=g,source=u,**kw)
 enrich_task(task,**(details or {}))
 rows.append(task)
lib=ast.literal_eval(read('libero.txt').split('=',1)[1])
for suite,names in lib.items():
 for name in names:
  f=P/f'libddl_{suite}_{name}.raw';code=f.read_text() if f.exists() else ''
  scene_match=re.match(r'^(KITCHEN|STUDY|LIVING_ROOM)_SCENE(\d+)_',name)
  scene=f'{readable_name(scene_match[1].lower())} scene {scene_match[2]}.' if scene_match else ''
  add('LIBERO',suite,name,re.sub(r'^(KITCHEN|STUDY|LIVING_ROOM)_SCENE\d+_','',name).replace('_',' '),goal(code),'https://github.com/Lifelong-Robot-Learning/LIBERO/blob/master/libero/libero/bddl_files/'+suite+'/'+name+'.bddl',details={'code':code,'scene':scene})
attrs=json.loads(read('casa_raw_attributes.raw'))['tasks']
classes={}
for f in P.glob('current_*.py'):
 code=f.read_text()
 try:tree=ast.parse(code)
 except SyntaxError:continue
 path=f.name[len('current_'):].replace('__','/')
 for node in tree.body:
  if isinstance(node,ast.ClassDef):
   methods={method.name:method for method in node.body if isinstance(method,ast.FunctionDef)}
   checker=ast.get_source_segment(code,methods['_check_success']) if '_check_success' in methods else None
   classes[node.name]=(checker,[ast.unparse(b) for b in node.bases],path,node.lineno,methods)
def checker_for(name,visited=None):
 visited=set() if visited is None else visited
 if name in visited or name not in classes:return None
 visited.add(name);check,bases,path,line,_=classes[name]
 if check:return check,path,line,name
 for base in bases:
  result=checker_for(base,visited)
  if result:return result
 return None
paper=read('casa_paper.read.txt');parts=paper.split('E.2\n')[-1].split('Appendix F')[0]
# Class names in each of the three appendix tables, terminated by their figure captions.
atomicpart=parts.split('Post-training Atomic-Seen Tasks')[0]
seenpart=parts.split('Post-training Atomic-Seen Tasks')[1].split('Post-training Composite-Seen Tasks')[0]
unseenpart=parts.split('Post-training Composite-Seen Tasks')[1].split('Post-training Composite-Unseen Tasks')[0]
for t in attrs:
 n=t['name'];s='Atomic' if t['activity']=='Atomic' else 'Composite'
 split=next((label for label,part in [('Atomic-Seen',atomicpart),('Composite-Seen',seenpart),('Composite-Unseen',unseenpart)] if re.search(r'^'+re.escape(n)+r'$',part,re.M)), 'Library / pretraining')
 check=checker_for(n)
 source='https://github.com/robocasa/robocasa/blob/'+json.loads(read('casa_tree.html'))['sha']+'/'+classes[n][2]+'#L'+str(classes[n][3]) if n in classes else 'https://robocasa.ai/docs/build/html/tasks/composite_tasks.html'
 goaltext=('Executable success check'+(' (inherited from '+check[3]+')' if check[3]!=n else '')+':\n'+check[0]+'\n\nHelper methods and fixture-state functions in the linked source define the referenced geometric thresholds and semantics.') if check else ''
 catalog='https://robocasa.ai/docs/build/html/tasks/'+('atomic_tasks.html' if s=='Atomic' else 'composite_tasks.html')
 setup=casa_setup_summary(classes[n][4]) if n in classes else ''
 add('RoboCasa365',s,n,t.get('description',''),goaltext,source,details={'demo_page':catalog},activity=t['activity'],mobile=t['moma_required'],steps=t['num_subtasks'],split=split,setup=setup)
for typ in ['atomic','composite']:
 text=read('casa_old_'+typ+'.html');category=''
 for line in text.splitlines():
  if line.startswith('### '):category=line[4:]
  m=re.match(r'\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|.*?\[Source\]\((.*?)\)',line)
  if m:
   sentences=re.split(r'(?<=[.?!])\s+',m[2])
   setup=' '.join(sentence for sentence in sentences if re.search(r'\b(?:already|starts? (?:on|in|open|closed)|initially|there (?:is|are))\b',sentence,re.I))
   add('RoboCasa v0.2',typ.title(),m[1],m[2],'',m[3],activity=category,setup=setup)
simple=ast.parse(read('simpler_init.raw'))
envs=ast.literal_eval(next(n.value for n in simple.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='ENVIRONMENTS' for x in n.targets)))
env_map=ast.literal_eval(next(n.value for n in simple.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='ENVIRONMENT_MAP' for x in n.targets)))
for n in envs:
 desc=n.replace('google_robot_','').replace('widowx_','').replace('_',' ')
 if 'pick' in n:g='Simulator grasp/lift success for the specified object.'
 elif 'move_near' in n:g='Source object moved near the target under the environment’s geometric distance check; grasping alone is insufficient.'
 elif 'place_' in n:g='Complete the open-drawer then object-placement sequence; the apple/top-drawer specialization is the paper evaluation.'
 elif 'open_' in n:g='Target drawer joint reaches the open-state condition.'
 elif 'close_' in n:g='Target drawer joint reaches the closed-state condition.'
 elif 'stack' in n:g='Green block rests on the yellow block under the stacking checker.'
 else:g='Correct object placed on/in the specified target with the environment’s placement/release checks.'
 environment,parameters=env_map[n]
 setup=''
 if n.endswith('horizontal_coke_can'):setup='Coke-can grasping with the can in the horizontal configuration.'
 if n.endswith('vertical_coke_can'):setup='Coke-can grasping with the can in the vertical configuration.'
 if n.endswith('standing_coke_can'):setup='Coke-can grasping with the can upright.'
 if 'in_closed' in n:setup='The target drawer starts closed.'
 add('SIMPLER','Google robot' if n.startswith('google') else 'WidowX',n,desc,g,'https://github.com/simpler-env/SimplerEnv/blob/main/simpler_env/__init__.py',details={'demo_page':SIMPLER_MEDIA},setup=setup,sim_environment=environment,sim_parameters=parameters)

def dojo_levels(rubric):
 sections=re.split(r'(?m)^\s*(\d+(?:\.\d+)?)\s*\n',rubric)
 return [{'score':float(score),'description':condition.strip()} for score,condition in zip(sections[1::2],sections[2::2]) if condition.strip()]

for typ in ['sim','real']:
 for f in sorted(P.glob('dojo_'+typ+'_*.read.txt')):
  if f.name in ['dojo_sim_domain-randomization.read.txt']:continue
  text=f.read_text();start=text.find('Your browser does not support the video tag.')
  if start<0:continue
  body=text[start:];name=text[:start].strip().splitlines()[-1]
  def field(a,b):
   return body.split('\n'+a+'\n',1)[-1].split('\n'+b+'\n',1)[0].strip() if '\n'+a+'\n' in body else ''
  instruction=field('Instruction','Description');desc=field('Description','Platform')
  category=field('Category','Data Source') if typ=='sim' else field('Embodiment','Data Source')
  score=body.split('Condition\n',1)[-1].rsplit('\n',2)[0] if 'Condition\n' in body else 'Auxiliary demonstration data; not a core scored task.'
  meta=json.loads((P/f.name.replace('.read.txt','.meta.json')).read_text())
  videos=[urljoin(meta['url'],m['src']) for m in meta['media'] if m.get('src','').endswith('.mp4')]
  clips=[(url,'Randomized demonstration' if '-random.mp4' in url else 'Standard demonstration' if len(videos)>1 else 'Official task demonstration','variant' if len(videos)>1 else 'task') for url in videos]
  add('RoboDojo',('Simulation · '+category) if typ=='sim' else ('Real · '+category),name,instruction+' '+desc,score,meta['url'],details={'scoring_levels':dojo_levels(score),'task_videos':clips,'demo_page':meta['url']},instruction=instruction,setup=desc)
dc=json.loads(read('dc_tasks.html'))['tasks']
for t in dc:
 base='https://robocurve.org/datacenterbench/'
 setup_url=base+'setups.html#'+t['id']
 model_images={view:urljoin(base,path) for view,path in t['model'].items()}
 add('DataCenterBench','Tier 1',t['name'],t['instruction'],'\n'.join(str(x['score'])+': '+x['description'] for x in t['levels']),setup_url,details={'scoring_levels':t['levels'],'model_images':model_images,'demo_page':setup_url},setup=t['setup'],reset=t['reset'],image=t['id'],guidance=t.get('guidance',''))
challenge=re.search(r'const tasks = (\[.*?\]);',read('behavior_challenge.html'),re.S)
ch=json.loads(challenge[1]);chmap={x['id']:x for x in ch}
catalog=read('behavior_catalog.html')
catalogrows=re.findall(r'<tr>(.*?)</tr>',catalog,re.S)
for row in catalogrows:
 m=re.search(r'/knowledgebase/tasks/([^"/]+)\.html',row)
 if not m:continue
 ident=m[1];name,num=ident.rsplit('-',1);f=P/f'bddl_{name}_problem{num}.raw';code=f.read_text() if f.exists() else ''
 cols=re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)
 clean=lambda s:' '.join(Page(s).text)
 c=chmap.get(name,{})
 add('BEHAVIOR-1K','2026 challenge' if name in chmap else 'Full library',name,c.get('instruction',name.replace('_',' ')),goal(code),'https://behavior.stanford.edu/knowledgebase/tasks/'+ident+'.html',details={'code':code,'demo_page':BEHAVIOR_GALLERY if c else ''},objects=clean(cols[1]) if len(cols)>1 else '',predicates=clean(cols[3]) if len(cols)>3 else '',video=c.get('video',''),definition_id=num)
# Original BEHAVIOR-100 registry from its own version of BDDL.
old=json.loads(read('bddl_tree.html'))
for x in old['tree']:
 if x['path'].endswith('/problem0.bddl'):
  n=x['path'].split('/')[-2];f=P/('legacy_'+n+'.bddl');code=f.read_text() if f.exists() else '';add('BEHAVIOR-100','Original 100',n,n.replace('_',' '),goal(code),'https://github.com/StanfordVL/bddl/blob/'+old['sha']+'/'+x['path'],details={'code':code})
for additional_catalog in ('standard_tasks.json', 'physical_tasks.json', 'corl_tasks.json', 'mesa_tasks.json', 'harp_tasks.json', 'mobile_transfer_tasks.json', 'liquidlab_tasks.json', 'contactbench_tasks.json', 'contactbench_sim_tasks.json'):
 rows.extend(json.loads((ROOT / additional_catalog).read_text()))
if len({row['id'] for row in rows}) != len(rows):
 raise ValueError('Task IDs must be unique')
(ROOT/'tasks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
from collections import Counter
print('Task entries',Counter(x['benchmark'] for x in rows));print('RoboCasa splits',Counter(x.get('split') for x in rows if x['benchmark']=='RoboCasa365'));print('Challenge',len(ch))
