from fetch_sources import *
media={
 'libero':'https://arxiv.org/html/2306.03310v2/libero_fig1.png',
 'libero_suites':'https://arxiv.org/html/2306.03310v2/figures/libero_fig2.png',
 'libero_metrics':'https://arxiv.org/html/2306.03310v2/figures/metric.png',
 'casa':'https://arxiv.org/html/2603.04356v1/Figure1.png',
 'casa_scenes':'https://arxiv.org/html/2603.04356v1/Robocasa365_Scenes_v6.png',
 'simpler':'https://simpler-env.github.io/static/images/teaser.png',
 'behavior':'https://arxiv.org/html/2403.09227v1/pull-new.png',
 'behavior_physics':'https://arxiv.org/html/2403.09227v1/scene_features.png',
 'dojo':'https://arxiv.org/html/2607.04434v3/teaser.png',
 'dojo_tasks':'https://arxiv.org/html/2607.04434v3/tasks.png',
 'dojo_real':'https://arxiv.org/html/2607.04434v3/real_highlight.png',
}
for x in json.loads((ROOT/'sources/dc_tasks.html').read_text())['tasks']:media[x['id']]=urljoin('https://robocurve.org/datacenterbench/',x['top'])
(ROOT/'media').mkdir(exist_ok=True)
def dl(k,u):
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=40);b=r.read();ext='.jpg' if '.jpg' in u else '.png';(ROOT/'media'/(k+ext)).write_bytes(b);return k,len(b)
 except Exception as e:return k,str(e)
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:print(list(ex.map(lambda x:dl(*x),media.items())))
(ROOT/'media/credits.json').write_text(json.dumps(media,indent=2))
