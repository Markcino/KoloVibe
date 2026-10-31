"""Check complete mobile design coverage, local assets and navigation references."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'apps/mobile'

def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)

screens = [screen for path in sorted((APP / 'assets/design').glob('*.json'))
           for screen in json.loads(path.read_text())]
assert sorted(screen['number'] for screen in screens) == list(range(1, 109)), 'Incomplete or duplicate design IDs'
used = set()
for screen in screens:
    assert screen['node'] and screen['name']
    for node in walk(screen['root']):
        assert 'source' not in node, 'Temporary design URL must not ship'
        if node['kind'] == 'image':
            path = node['asset']
            assert path.startswith('assets/images/') and '..' not in path
            assert (APP / path).is_file() and (APP / path).stat().st_size > 0, path
            used.add(path)
        action = node.get('action', '')
        if action.startswith('go:'):
            assert 1 <= int(action[3:]) <= 108, action
manifest = json.loads((ROOT / 'docs/mobile-asset-manifest.json').read_text())
assert {entry['asset'] for entry in manifest} == used
for entry in manifest:
    assert hashlib.sha256((APP / entry['asset']).read_bytes()).hexdigest() == entry['sha256']
    assert all(slot['node'] for slot in entry['slots']), 'Every asset needs a design slot'
entry = (APP / 'lib/main.dart').read_text()
assert 'demo/' not in entry and 'main_demo' not in entry
assert not (APP / 'lib/main_demo.dart').exists()
assert not (APP / 'lib/demo/demo_repository.dart').exists()
exports = {int(str(path.relative_to(ROOT / 'docs/designed')).split('M-')[1][:3])
           for path in (ROOT / 'docs/designed').rglob('*.png')}
assert exports == set(range(1, 109)), 'Local screenshot archive incomplete'
print(f'Mobile design integrity OK: {len(screens)} entries, {len(used)} local assets, valid routes and source slots')
