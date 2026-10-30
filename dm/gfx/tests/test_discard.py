"""Discard entry points preserve vertex side effects and compile on both platforms."""
import ast
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / 'tools/dmsh_build.py'
sys.path.insert(0, str(path.parent))
import dmsh_abi
nodes = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in ('vs_discard', 'writes_memory')]
scope = {'re': re, 'abi': dmsh_abi}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)

SOURCE = '''#include <metal_stdlib>
using namespace metal;
struct main0_out { float4 p [[position]]; };
struct Args { device uint* values [[id(0)]]; };
vertex main0_out main0(uint n [[vertex_id]], constant Args& a [[buffer(0)]])
{
    main0_out out = {};
    a.values[n] = n + 17;
    if (n == 0) return out;
    a.values[n] = n + 29;
    return out;
}
'''


class WritesMemoryTests(unittest.TestCase):
    def writes(self, **binding): return scope['writes_memory'](binding)

    def test_storage_buffer_by_its_write_flag(self):
        self.assertTrue(self.writes(kind=dmsh_abi.KIND_SBUF, rw=True))
        self.assertFalse(self.writes(kind=dmsh_abi.KIND_SBUF, rw=False))

    def test_image_by_its_msl_access(self):   # Metroid Prime Remastered's fog writer: image stores are the only thing it does
        self.assertTrue(self.writes(kind=dmsh_abi.KIND_IMG, msl_type='texture3d<float, access::write>'))
        self.assertTrue(self.writes(kind=dmsh_abi.KIND_IMG, msl_type='texture2d<uint, access::read_write>'))
        self.assertFalse(self.writes(kind=dmsh_abi.KIND_IMG, msl_type='texture2d<float, access::read>'))

    def test_image_atomics_are_writes(self):
        self.assertTrue(self.writes(kind=dmsh_abi.KIND_IMG, msl_type='texture2d<uint>', atomic=True))

    def test_a_texture_is_no_write(self):
        self.assertFalse(self.writes(kind=dmsh_abi.KIND_TEX, msl_type='texture2d<float>'))


class DiscardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('xcrun'), 'requires Metal compilers')
    def test_side_effects_before_both_returns_compile_as_void_vertex(self):
        src = SOURCE + scope['vs_discard'](SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); msl = root / 'discard.metal'; msl.write_text(src)
            for sdk in ('macosx', 'iphoneos'):
                with self.subTest(sdk=sdk):
                    r = subprocess.run(['xcrun', '-sdk', sdk, 'metal', '-c', '-fmodules-cache-path=' + str(root / sdk), str(msl), '-o', str(root / (sdk + '.air'))], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main()
