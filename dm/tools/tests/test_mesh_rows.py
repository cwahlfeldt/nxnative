#!/usr/bin/env python3
# dm/gfx/tools/mesh_rows.py: the task / mesh pipelines the pipeline prebuild adds to a prewarm list from the game's own programs (shader_pairs.tsv)
import os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'gfx', 'tools'))
import mesh_rows


def key(mesh, pixel, state):
    return (mesh + '_b').encode().ljust(24, b'\0') + (pixel + '_b').encode().ljust(24, b'\0') + state


OPAQUE, BLEND, OTHER = b'\x04\x01' + bytes(14), b'\x04\x01\x01' + bytes(13), b'\x04\x01\x02' + bytes(13)


class MeshRows(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        rows = [('mesh', 'm1', 'Model.bfsha'), ('mesh', 'm2', 'Model.bfsha'), ('mesh', 'm3', 'Model.bfsha'), ('mesh', 'f1', 'Foliage.bfsha'), ('mesh', 'f2', 'Foliage.bfsha'),
                ('task', 't1', 'Model.bfsha'), ('task', 'ta', 'Foliage.bfsha'), ('task', 'tb', 'Foliage.bfsha')] + \
               [('pixel', f'p{i}', 'Model.bfsha') for i in range(1, 13)] + [('pixel', 'q1', 'Foliage.bfsha'), ('pixel', 'q2', 'Foliage.bfsha'), ('vertex', 'v1', 'Model.bfsha')]
        (self.dir / 'shader_map.tsv').write_text('# map\n' + ''.join(f'x.bin\t{i}\t{s}\t{k}\t/Shader/{f}#BNSH@0x10#var{i}\n' for i, (s, k, f) in enumerate(rows)))
        pairs = [('m1', f'p{i}') for i in range(1, 11)] + [('m2', 'p11'), ('m3', 'p12'), ('m3', 'p1'), ('f2', 'q2'), ('v1', 'p1')]
        (self.dir / 'shader_pairs.tsv').write_text('# pairs\n' + ''.join(f'{a}\t{b}\n' for a, b in pairs))
        # the list: t1 with m1 and ten pixel shaders, six opaque, three blended, one in a rare state; the foliage meshes with two tasks
        seen = [('p1', OPAQUE), ('p2', OPAQUE), ('p3', OPAQUE), ('p4', OPAQUE), ('p5', OPAQUE), ('p6', OPAQUE), ('p7', BLEND), ('p8', BLEND), ('p9', BLEND)] + \
               [(f'p{i}', OPAQUE) for i in range(13, 30)] + [('p10', OTHER)]
        self.text = ''.join(f'M\tt1_b\t{key("m1", p, s).hex()}\n' for p, s in seen) + f'M\tta_b\t{key("f1", "q1", OPAQUE).hex()}\nM\ttb_b\t{key("f1", "q1", OPAQUE).hex()}\nR\tdead\n'
        self.out, self.summary = mesh_rows.extra_rows(self.dir / 'shader_map.tsv', self.text)
        self.made = set()
        for line in self.out.splitlines():
            t, k = line.split('\t')[1:]; b = bytes.fromhex(k)
            self.made.add((t, b[:24].split(b'\0')[0].decode(), b[24:48].split(b'\0')[0].decode(), b[48:]))

    def test_seen_pixel_keeps_its_state(self):
        self.assertIn(('t1_b', 'm3_b', 'p1_b', OPAQUE), self.made)
        self.assertNotIn(('t1_b', 'm3_b', 'p1_b', BLEND), self.made)

    def test_unseen_pixel_gets_the_common_states(self):
        # m2 never appears in the list: its file's one task; p11 never appears: opaque and blended (each used by a tenth of t1's pixel shaders or more), not the rare state
        self.assertEqual({s for t, m, p, s in self.made if m == 'm2_b' and p == 'p11_b' and t == 't1_b'}, {OPAQUE, BLEND})

    def test_rows_in_the_list_are_not_repeated(self):
        for i in range(1, 10): self.assertFalse(any(m == 'm1_b' and p == f'p{i}_b' for t, m, p, s in self.made))

    def test_a_file_with_several_tasks_gives_none(self):
        self.assertFalse(any(m == 'f2_b' for t, m, p, s in self.made))
        self.assertEqual(self.summary.get('pairs left out (no task)'), 1)

    def test_vertex_pairs_are_not_mesh_rows(self):
        self.assertFalse(any(m == 'v1_b' for t, m, p, s in self.made))

    def test_a_list_without_mesh_rows_adds_nothing(self):
        self.assertEqual(mesh_rows.extra_rows(self.dir / 'shader_map.tsv', 'R\tdead\n')[0], '')


if __name__ == '__main__':
    unittest.main()
