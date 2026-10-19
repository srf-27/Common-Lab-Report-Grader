"""加强版完整性审计：非不及格档必须有【思考和讨论】章且结尾完整。"""
import json, re, pathlib

ROOT = pathlib.Path('tests/fixtures/bench/cn_lab')
teacher = json.loads((ROOT / 'teacher_grades.json').read_text(encoding='utf-8'))
TAIL_OK = re.compile(r'[。）)”"】\]]\s*$|\\\]\s*$|\$[^$]*\$\s*$|\)\s*$|[0-9a-zA-Z]\.?\s*$')
bad = []
for fn, entry in teacher.items():
    md = ROOT / 'reports_md' / fn.replace('.docx', '.md')
    text = md.read_text(encoding='utf-8')
    band = entry['总分']
    problems = []
    if band != 'E':
        if not ('思考' in text and '讨论' in text):
            problems.append('缺思考和讨论章')
        tail = text.rstrip()
        if not TAIL_OK.search(tail):
            problems.append('结尾截断:' + tail[-22:])
        if band in ('A', 'B') and ('应用' not in text):
            problems.append('优/良缺工程应用讨论')
    if problems:
        print(f'{fn:16s} {band} {len(text):5d}字  {"；".join(problems)}')
        bad.append(fn)
print()
print('需重生成:', bad)
pathlib.Path('_regen_list.json').write_text(json.dumps(bad), encoding='utf-8')
