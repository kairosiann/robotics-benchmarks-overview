from fetch_sources import *
p=ROOT/'sources'
urls={
 'dc_methods':'https://robocurve.org/datacenterbench/methods.html',
 'dc_setups':'https://robocurve.org/datacenterbench/setups.html',
 'casa_atomic_data':'https://robocasa.ai/docs/build/html/static/atomic_task_attributes.js',
 'casa_atomic_index':'https://robocasa.ai/docs/build/html/static/atomic_task_index.js',
 'casa_composite_data':'https://robocasa.ai/docs/build/html/static/composite_task_attributes.js',
 'casa_composite_ui':'https://robocasa.ai/docs/build/html/static/composite_tasks_dropdown.js',
 'casa_atomic_ui':'https://robocasa.ai/docs/build/html/static/atomic_tasks.js',
 'casa_multi':'https://robocasa.ai/docs/build/html/benchmarking/multitask_learning.html',
 'casa_old_atomic':'https://raw.githubusercontent.com/robocasa/robocasa/main/docs/_versions/v0.2/tasks_scenes_assets/atomic_tasks.md',
 'casa_old_composite':'https://raw.githubusercontent.com/robocasa/robocasa/main/docs/_versions/v0.2/tasks_scenes_assets/composite_tasks.md',
 'casa_details':'https://raw.githubusercontent.com/robocasa/robocasa/main/docs/tasks/_generated/composite_tasks_details.md',
 'behavior_catalog':'https://behavior.stanford.edu/knowledgebase/tasks/index.html',
 'behavior_challenge':'https://behavior.stanford.edu/challenge/tasks/index.html',
 'behavior_100':'https://stanfordvl.github.io/behavior/benchmark.html',
}
for n in ['dojo_sim','dojo_real']:
 m=json.loads((p/(n+'.meta.json')).read_text())
 for u in dict.fromkeys(m['links']):
  if '/doc/'+('sim-tasks/' if n=='dojo_sim' else 'real-tasks/') in u and '#' not in u and u.rstrip('/')!=m['url'].rstrip('/') and not any(t in u for t in ['domain-randomization','parallel-environments']):urls[n+'_'+u.strip('/').split('/')[-1]]=u
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
 for r in ex.map(lambda kv:fetch(*kv),urls.items()):print(r,flush=True)
