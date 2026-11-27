"""Check complete mobile design coverage, local assets and navigation references."""
import hashlib
import json
import csv
import re
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

# Phase 2 frames are a separate design review inventory, never an extension of
# the approved 108-screen shipped catalogue or proof of live Figma acceptance.
frame_register = ROOT / 'docs/design/PHASE-02_Figma_Frame_Register.csv'
frames = list(csv.DictReader(frame_register.open()))
assert len({f['screen_id'] for f in frames}) == len(frames), 'Duplicate Phase 2 screen id'
assert len({f['node_id'] for f in frames}) == len(frames), 'Duplicate Phase 2 Figma node'
assert {f'M-{i}' for i in range(109, 145)} <= {f['screen_id'] for f in frames}, 'Business design inventory incomplete'
for frame in frames:
    assert frame['file_key'] == 'ANaV0jnwjZ0LEcByTc98HP'
    assert re.fullmatch(r'\d+:\d+', frame['node_id']), frame
    assert frame['requirement'] and frame['design_status']
    assert frame['owner_approval'] == 'Pending', 'Owner approval requires a dated decision reference and gate review'
readback = json.loads((ROOT / 'docs/evidence/phase2-2026-11-27/figma-readback.json').read_text())
assert readback['frame_count'] == len(frames), 'Register differs from recorded Figma read-back'
assert not readback['unexpected_fonts'] and not readback['root_child_overflow']
print(f'Phase 2 design register OK: {len(frames)} recorded draft frames; live owner approval remains pending')
