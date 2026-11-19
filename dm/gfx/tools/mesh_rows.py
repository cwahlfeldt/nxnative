#!/usr/bin/env python3
# Task / mesh pipelines for the pipeline prebuild beyond those a prewarm list recorded: every mesh / pixel pair of the game's own programs (shader_pairs.tsv, which shader_split.py
# takes from each BNSH variation) whose task shader and render states the list already shows. A mesh pipeline has no stand-in to draw with while it compiles (nvn_geometry.inc
# mtk_pso), so the first draw of each one the bundle lacks waits for the compiler on the submit thread: Ocarina of Time's Kakariko Village on a base M5, 19 of them in one visit,
# 158 ms to 1.5 s each, every one a pair the game's programs list with a render state the bundle already had (docs/reference/shaders.md, "Mesh pipelines the bundle lacks").
#
# An M row is `M <TAB> task key <TAB> pipeline key` (nvn_pso_skey.h pso_skey as hex: the mesh and pixel shader names, 24 bytes each, then the stages and the render state). For each
# pair (mesh m, pixel f) in shader_pairs.tsv whose m is a mesh shader:
#   task: the tasks the list shows with m; for an m it never shows, the one task the list shows with every other mesh shader of m's file (the shader archive before '#' in the shader
#         map's column 5), else none and the pair is left out (a file whose meshes the list shows with several tasks: Ocarina of Time's foliage);
#   render states: those the list shows with f under that task; for an f it never shows, the states that at least a tenth of the task's pixel shaders in the list use (the blend
#         state belongs to the material, not to the shader, so an unseen material is built opaque and blended: Ocarina of Time's model pass, 78 and 46 of 130 pixel shaders).
# Rows the list has already are not repeated. Only the prebuild reads these (build_ipa_from_nsp.py mac_prebake, pso_offline.py --prewarm-host): the list shipped in the app stays
# as recorded, so a start without the bundle does not build them all first; a draw finds them in the bundle by their key (nvn_mtl.m arch_lookup).
# Usage: mesh_rows.py <shader_map.tsv> <prewarm list> [...]  → the extra rows on stdout, a summary on stderr
import collections, sys
from pathlib import Path

NAME = 24   # bytes of each shader name in the key
SHARE = 0.1   # the share of a task's pixel shaders a render state needs to be built for pixel shaders the list never shows


def _name(b):
    return b.split(b'\0')[0].decode('ascii', 'replace')


def _bare(n):
    return n.split('_')[0]


def _tables(shader_map):
    stage, where = {}, {}
    if not shader_map or not Path(shader_map).is_file(): return stage, where, []   # no map: no pairs to add
    for line in Path(shader_map).read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('#'): continue
        c = line.split('\t')
        if len(c) >= 5: stage[c[3]] = c[2]; where[c[3]] = c[4].split('#')[0]
    pairs = []
    p = Path(shader_map).with_name('shader_pairs.tsv')
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            c = line.split('\t')
            if line.startswith('#') or len(c) < 2: continue
            pairs.append((c[0], c[1]))
    return stage, where, pairs


def extra_rows(shader_map, list_text):
    """The M rows the prebuild should build besides list_text's own, as text (one row a line), and a summary dict"""
    stage, where, pairs = _tables(shader_map)
    rows = []   # (task, mesh name, pixel name, state bytes, raw key bytes)
    for line in list_text.splitlines():
        c = line.split('\t')
        if len(c) != 3 or c[0] != 'M': continue
        try: b = bytes.fromhex(c[2])
        except ValueError: continue
        if len(b) <= 2 * NAME: continue
        rows.append((c[1], _name(b[:NAME]), _name(b[NAME:2 * NAME]), b[2 * NAME:], b))
    if not rows or not pairs: return '', {'rows': 0}
    width = max(len(r[3]) for r in rows)
    pad = lambda s: s + bytes(width - len(s))   # a row from before the key's last fields reads them as 0 (pso_skey_parse)
    have = {(t, _bare(m), _bare(f), pad(s)) for t, m, f, s, _ in rows}
    tasks = collections.defaultdict(set)                    # mesh → tasks
    file_tasks = collections.defaultdict(set)              # mesh shader file → tasks of its meshes in the list
    frag_states = collections.defaultdict(dict)            # (task, pixel) → {state: a row's key with it}
    task_frags = collections.defaultdict(lambda: collections.defaultdict(set))   # task → state → pixel shaders
    suffix = {}
    for t, m, f, s, b in rows:
        bm, bf = _bare(m), _bare(f)
        tasks[bm].add(t); file_tasks[where.get(bm, '?')].add(t)
        frag_states[(t, bf)].setdefault(pad(s), b); task_frags[t][pad(s)].add(bf)
        suffix.setdefault(t, (m[len(bm):], f[len(bf):]))
    common = {}
    for t, by_state in task_frags.items():
        nf = len({f for fs in by_state.values() for f in fs})
        common[t] = {s: next(iter(frag_states[(t, next(iter(fs)))].values())) for s, fs in by_state.items() if len(fs) >= max(1, SHARE * nf)}
    out, left, made = [], collections.Counter(), collections.Counter()
    for m, f in sorted(set(pairs)):
        if stage.get(m) != 'mesh' or stage.get(f) != 'pixel': continue
        ts = tasks.get(m) or (file_tasks[where.get(m, '?')] if len(file_tasks[where.get(m, '?')]) == 1 else set())
        if not ts: left['no task'] += 1; continue
        for t in sorted(ts):
            states = frag_states.get((t, f)) or common.get(t, {})
            sm, sf = suffix.get(t, ('_b', '_b'))
            for s, tmpl in sorted(states.items()):
                if (t, m, f, s) in have: continue
                key = (m + sm).encode().ljust(NAME, b'\0') + (f + sf).encode().ljust(NAME, b'\0') + tmpl[2 * NAME:]
                have.add((t, m, f, s)); made['seen pixel' if (t, f) in frag_states else 'unseen pixel'] += 1
                out.append(f'M\t{t}\t{key.hex()}\n')
    return ''.join(out), {'rows': len(out), **made, **{f'pairs left out ({k})': v for k, v in left.items()}}


def main():
    if len(sys.argv) < 3: sys.exit('usage: mesh_rows.py <shader_map.tsv> <prewarm list> [...]')
    text = ''.join(Path(p).read_text(encoding='utf-8') for p in sys.argv[2:] if Path(p).is_file())
    rows, summary = extra_rows(sys.argv[1], text)
    sys.stdout.write(rows)
    print('mesh rows: ' + ', '.join(f'{k} {v}' for k, v in summary.items()), file=sys.stderr)


if __name__ == '__main__':
    main()
