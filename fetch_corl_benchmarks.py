"""Extract selected CoRL 2026 catalogs from retained primary-source snapshots."""
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from fetch_sources import Page

ROOT = Path(__file__).parent
SOURCES = ROOT / 'sources' / 'corl2026'


def text(markup):
    return ' '.join(Page(markup).text)


def tables(name):
    html = (SOURCES / (name + '.html')).read_text()
    return [
        (table, [[text(cell) for cell in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', row, re.S)]
                 for row in re.findall(r'<tr\b.*?</tr>', table, re.S)])
        for table in re.findall(r'<table\b.*?</table>', html, re.S)
    ]


def record(family, identity, title, description, source, suite, setting='Simulation', **fields):
    return dict(id=family.lower().replace(' ', '-') + '--' + identity, family=family,
                benchmark=family, suite=suite, setting=setting, name=identity, title=title,
                instruction=description, description=description, source=source,
                evaluation_source=source, observation='', observation_scope='unavailable',
                observation_source='', setup_summary='', setup_source='', goal='',
                grading_summary='', grading_scope='unavailable', grading_evidence='',
                media=[], conference='CoRL 2026', **fields)


def build():
    rows = []
    imsource = 'https://arxiv.org/html/2607.15641'
    imtext = (SOURCES / 'imbench_paper.txt').read_text()
    imhtml = (SOURCES / 'imbench_paper.html').read_text()
    inventory = next(data for _, data in tables('imbench_paper') if data and data[0][:3] == ['ID', 'Task', 'Cat.'])
    for identity, name, category, embodiment, *_ in inventory[1:]:
        match = re.search(r'\n' + identity + r'\n' + re.escape(name) + r'\n\.\n(.*?)(?=\n[TM]\d\d\n|$)', imtext, re.S)
        if not match:
            raise ValueError('Missing IMBench task evidence ' + identity)
        block = match[1]
        setup = block.split('Setup:\n', 1)[-1].split('\nGoal:', 1)[0].strip()
        goal = block.split('Goal:\n', 1)[-1].split('\nIntuition:', 1)[0].strip()
        task = record('IMBench', identity.lower(), name.replace('-', ' ').title(),
                      goal, imsource, category)
        task.update(setup_summary=setup, setup_source=imsource, goal=goal,
                    grading_summary=goal, grading_scope='task', embodiment=embodiment,
                    grading_evidence='The paper evaluates constraint understanding, plan correctness, and closed-loop execution separately. Policy success uses the task-specific physical goal.',
                    observation='The available benchmark interface includes synchronized 2–4 RGB views, robot proprioception, gripper state and wrist force/torque. The task table specifies the arm and end-effector configuration. Inputs consumed depend on the evaluated policy; this interface description does not imply that every baseline uses force feedback.',
                    observation_scope='benchmark', observation_source=imsource)
        image_name = {'T05':'pb-hobi-plate-shelf', 'T06':'pb-hetbi-plate-shelf'}.get(identity, name)
        image = next((path for path in re.findall(r'<img[^>]*src="([^"]+)"', imhtml) if '/tasks/' in path and image_name in path), '')
        if image:
            task['media'] = [dict(type='image', url=urljoin(imsource, image), label='Published task setup', scope='task')]
        rows.append(task)
    assert len(inventory) - 1 == 35

    atomsource = 'https://arxiv.org/html/2606.16826'
    atom_count = 0
    for markup, data in tables('atom_paper'):
        if not data or data[0][:2] != ['Task_id', 'Prompt']:
            continue
        row_images = {}
        for row_html in re.findall(r'<tr\b.*?</tr>', markup, re.S):
            cells_html = re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', row_html, re.S)
            images = re.findall(r'<img[^>]*src="([^"]+)"', row_html)
            if cells_html and images:
                row_images[text(cells_html[0])] = images[0]
        for cells in data[1:]:
            identity, instruction = cells[:2]
            if not re.fullmatch(r'd?[mix]\d+', identity):
                continue
            track = 'Cobot Magic dual arm' if identity.startswith('d') else 'Franka Panda single arm'
            group = 'Composition' if 'x' in identity else ('Motor atoms' if 'm' in identity else 'Instruction atoms')
            task = record('ATOM-Bench', identity, identity + ' · ' + instruction, instruction, atomsource, track + ' · ' + group, 'Real')
            task.update(grading_summary='Complete the specified instruction. The paper reports full task success and fraction of annotated process score points achieved.',
                        grading_scope='suite', grading_evidence='Each task receives ten shared physical test seeds. Full success uses a completion predicate. Process Success Rate averages the fraction of score points achieved. The task table publishes prompts rather than a separate executable checker.',
                        observation='Three RGB camera views and robot state are recorded. Franka uses left, front, and wrist views. Cobot Magic uses left-arm, right-arm, and front views.',
                        observation_scope='benchmark', observation_source=atomsource)
            if identity in row_images:
                task['media'] = [dict(type='image', url=urljoin(atomsource, row_images[identity]), label='Published task setup', scope='task')]
            rows.append(task)
            atom_count += 1
    assert atom_count == 54

    source = 'https://chongyuzhu.github.io/wirecraft/'
    markup = (SOURCES / 'wirecraft.html').read_text()
    for block in re.findall(r'<article\b.*?</article>', markup, re.S):
        if 'task-panel' not in block:
            continue
        title = text(re.search(r'<h3[^>]*>(.*?)</h3>', block, re.S)[1])
        body = '\n'.join(Page(block).text)
        criterion = body.split('Success criterion\n', 1)[1].split('\nSimulation demo', 1)[0]
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', block, re.S)
        description = next(text(p) for p in paragraphs if len(text(p)) > 75)
        identity = re.search(r'id="task-([^"]+)"', block)[1]
        task = record('WireCraft', identity, title, description, source + '#task-' + identity, 'Industrial flexible-wire manipulation', 'Sim-to-real')
        task.update(setup_summary=description, setup_source=source, goal=criterion,
                    grading_summary=criterion, grading_scope='task',
                    grading_evidence='Task success is checked separately from reaching progress. The benchmark includes articulated and deformable wire simulation and physical UR5 evaluation.',
                    observation='The physical UR5 ACT evaluation uses side and wrist RGB views from two RealSense D405 cameras plus robot proprioception, with action commands at 30 Hz. Simulation evaluates both privileged-state and visual policy configurations.',
                    observation_scope='suite', observation_source='https://arxiv.org/html/2606.18097')
        task['media'] = [dict(type='video',url=urljoin(source, path),label='Official task demonstration',scope='task')
                         for path in dict.fromkeys(re.findall(r'(?:src|href)="([^"]+\.mp4)"',block))]
        rows.append(task)
    assert sum(t['family'] == 'WireCraft' for t in rows) == 3
    (ROOT / 'corl_tasks.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print('CoRL task entries', len(rows))


if __name__ == '__main__':
    build()
