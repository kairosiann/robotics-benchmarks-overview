"""Retain and ingest ContactBench's published reference task definitions."""
import ast
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urljoin
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / 'sources' / 'contactbench'
HOME = 'https://jingyi-xiang.github.io/contactbench/'
PAPER = 'https://arxiv.org/html/2610.24512'


def fetch(path):
    local = SOURCES / path
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(urlopen(urljoin(HOME, path), timeout=40).read())
    return local.read_text()


def literal_call(source, name):
    """Parse literal data only, without executing the downloaded JavaScript."""
    body = source.split(name + '(', 1)[1].rsplit(')', 1)[0]
    pattern = re.compile(r'''\s+|//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?|[A-Za-z_$][\w$]*|[{}\[\],:]''')
    tokens = []
    offset = 0
    for match in pattern.finditer(body):
        if match.start() != offset:
            raise ValueError('Unsupported JavaScript literal syntax')
        offset = match.end()
        token = match[0]
        if token.isspace() or token.startswith(('//', '/*')):
            continue
        tokens.append(token)
    if body[offset:].strip():
        raise ValueError('Trailing nonliteral content')
    converted = []
    for index, token in enumerate(tokens):
        if re.fullmatch(r'[A-Za-z_$][\w$]*', token):
            if index + 1 < len(tokens) and tokens[index + 1] == ':':
                token = repr(token)
            else:
                token = {'true': 'True', 'false': 'False', 'null': 'None'}[token]
        converted.append(token)
    return ast.literal_eval(' '.join(converted))


def build():
    fetch('index.html')
    fetch('tasks.html')
    index = fetch('config/tasks/index.js')
    names = literal_call(index, 'defineTaskList')
    skills = literal_call(fetch('config/skills.js'), 'defineSkills')['skills']
    skill_names = {skill['key']: skill['name'] for skill in skills}
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, ['config/tasks/' + name + '.js' for name in names]))
    experiment_names = {'Thread nut onto screw', 'Tighten screw with Allen key', 'Plug in charger',
                        'Turn doorknob to open door', 'Retrieve single utensil from bin', 'Pick up object from platform'}
    rows = []
    manifest = []
    for name in names:
        path = 'config/tasks/' + name + '.js'
        code = fetch(path)
        task = literal_call(code, 'defineTask')
        evaluated = task['name'] in experiment_names
        # The website's object template and the paper's experimental card variant share this task.
        evaluated = evaluated or task['id'] == '06'
        record = dict(
            id='contactbench--reference-' + task['id'].lower(), family='ContactBench',
            benchmark='ContactBench 1.0 reference tasks', suite='Long-horizon challenges' if task.get('challenge') else 'Base reference tasks',
            split='Six-task policy study' if evaluated else 'Reference catalog outside policy study',
            name=task['id'], title=task['name'], description=task['description'], instruction=task['description'],
            source=HOME + 'tasks.html?' + urlencode({'q': task['name']}), setting='Real',
            setup_summary=task['description'], setup_source=urljoin(HOME, path),
            goal=task['success'], grading_summary=task['success'], grading_scope='task',
            grading_evidence='The published reference task criterion specifies completion and any release, stability, force-probe or disengagement requirements. The six-task policy study additionally measures progress checkpoints, peak wrist force and completion time.',
            evaluation_source=urljoin(HOME, path), observation='', observation_scope='unavailable', observation_source='',
            activity=', '.join(skill_names[key] for key in task['skills']), skills=task['skills'],
            assets=task.get('assetCards', []), task_variations=task.get('variations', []), media=[],
            record_kind='reference-task', catalog_scope='One of36 published reference tasks:31 base tasks and5 long-horizon challenges. Simulation release rows are separate records.',
            source_note='Reference-task website numbering differs from the paper and simulation numbering. Physical task criteria are preserved as published. Policy inputs and rollout settings were evaluated on six selected tasks, not on the full reference catalog.',
        )
        record['catalog_scope'] = record['catalog_scope'].replace('of36', 'of 36').replace(':31', ': 31').replace('and5', 'and 5')
        if evaluated:
            tactile = task['id'] not in ('02', '06')
            record.update(
                observation='The policy study uses wrist RGB and robot proprioception. ' + ('RDP and FTP-1 add GelSight Mini tactile input on this task.' if tactile else 'Only the vision policies are evaluated on this task, using Fin-Ray fingers.'),
                observation_scope='suite', observation_source=PAPER,
                evaluation_protocol='Thirty rollouts per evaluated policy with a one-minute limit. The same sampled object and robot initial poses are shared across policies. Object origins are sampled in a 0.15m ×0.15m region on a Velcro-covered board. Average progress is the fraction of task checkpoints reached, with force and time reported separately.',
            )
            if task['id'] == '06':
                record['source_note'] += ' The policy experiment evaluates the card variant of this general object-from-platform reference task.'
        if task.get('thumbnail'):
            record['media'].append(dict(type='image', url=urljoin(HOME, 'website_assets/images/thumbnails/' + task['thumbnail']), label='Official reference-task thumbnail', scope='task'))
        if task.get('video'):
            record['media'].append(dict(type='video', url=urljoin(HOME, 'website_assets/videos/tasks/' + task['video']), label='Official human task demonstration', scope='task'))
        for axis in task.get('variations', []):
            for variant in axis.get('instances', []):
                if variant.get('video'):
                    record['media'].append(dict(type='video', url=urljoin(HOME, 'website_assets/videos/tasks/' + variant['video']), label=axis['axis'] + ' · ' + variant['label'], scope='variant'))
        rows.append(record)
        manifest.append(dict(path=path, url=urljoin(HOME, path), sha256=sha256(code.encode()).hexdigest()))
    assert len(rows) == 36 and len(skill_names) == 8
    assert sum(row['split'] == 'Six-task policy study' for row in rows) == 6
    (ROOT / 'contactbench_tasks.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    (SOURCES / 'manifest.json').write_text(json.dumps(dict(home=HOME, paper=PAPER, files=manifest), indent=2))
    print('ContactBench reference tasks:', len(rows))


if __name__ == '__main__':
    build()
