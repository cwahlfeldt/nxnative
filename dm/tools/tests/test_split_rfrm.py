"""shader_split's reader of Retro Studios' RFRM files in both forms. Tropical Freeze's are big-endian, with 36-byte ADIR entries directly in the pack; Metroid Prime Remastered's are little-endian,
with 52-byte entries in a 'TOCC' form inside the pack, and on its SDK 12 a control section can end in a table past its own length, padded to 16 bytes when another section follows.
Synthetic files, no game files needed."""
import os
import struct
import sys
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
_had = os.environ.get('DM_GAME'); os.environ['DM_GAME'] = '0100C1F0051B6000'   # shader_split loads a profile at import; other tests expect no default
import shader_split as ss
if _had is None: del os.environ['DM_GAME']
else: os.environ['DM_GAME'] = _had

BIG, LITTLE = '>', '<'
GUID = bytes(range(16))


def control(ncode, size, table=b'', entries=0):
    c = bytearray(size)
    c[:4] = ss.CTL_MAGIC
    struct.pack_into('<I', c, 0x20, size)
    struct.pack_into('<I', c, 0x704, ncode)
    struct.pack_into('<IIII', c, 0x7e8, size, len(table), entries, 12)
    return bytes(c) + table


def code(fill, ncode=0x100):   # a graphics code area: the header magic, a fill byte to tell areas apart, and SPH word 0 of a vertex shader at +0x30
    return ss.GFX_MAGIC + bytes([fill]) * 0x2c + struct.pack('<I', 0x0461) + bytes(ncode - 0x34)


def record(order, sections):
    """A program record: sections are (code, control), the controls padded to 16 bytes except the last"""
    body = b''.join(k for k, _ in sections)
    ncode = len(body)
    for i, (_, c) in enumerate(sections):
        body += c + (bytes(-len(c) & 0xf) if i + 1 < len(sections) else b'')
    z = zlib.compress(body)
    return struct.pack(order + 'IIBI', ncode, len(body) - ncode, 0, len(z)) + z


def chunk(order, cc, data):
    return cc + struct.pack(order + 'QIII', len(data), 1, 0, 0) + data


def form(order, kind, data, version=1):
    return ss.RFRM + struct.pack(order + 'QQ', len(data), 0) + kind + struct.pack(order + 'II', version, version) + data


def snvn(order, *records):
    return chunk(order, ss.SNVN, bytes(12) + b''.join(records))


def pack_big(resource):
    """Tropical Freeze: PACK { ADIR of 36-byte entries } with the resource after it"""
    head = 0x20 + 0x18 + 4 + 36 * 2
    entry = lambda kind, off, n: kind + GUID + struct.pack('>QQ', off, n)
    adir = chunk(BIG, b'ADIR', struct.pack('>I', 2) + entry(b'TXTR', head, 4) + entry(b'MTRL', head + 4, len(resource)))
    return form(BIG, b'PACK', adir + b'\0\0\0\0' + resource)


def pack_little(resource):
    """Metroid Prime Remastered: PACK { TOCC { ADIR of 52-byte entries } } with the resource after it"""
    head = 0x20 + 0x20 + 0x18 + 4 + 52 * 2
    entry = lambda kind, off, n: kind + GUID + struct.pack('<IIQQQ', 168, 168, off, n, n)
    adir = chunk(LITTLE, b'ADIR', struct.pack('<I', 2) + entry(b'TXTR', head, 4) + entry(b'MTRL', head + 4, len(resource)))
    return form(LITTLE, b'PACK', form(LITTLE, b'TOCC', adir, 3) + b'\0\0\0\0' + resource)


def stages(found):
    return [(s[2][:4], len(s[2]), s[3][4]) for s in found]


class ByteOrder(unittest.TestCase):
    def test_the_smaller_reading_of_the_length_wins(self):
        self.assertEqual(ss.rfrm_order(form(BIG, b'MTRL', bytes(0x300)), 0), BIG)
        self.assertEqual(ss.rfrm_order(form(LITTLE, b'MTRL', bytes(0x300)), 0), LITTLE)


class Records(unittest.TestCase):
    def roundtrip(self, order, size=0x840):
        rec = record(order, [(code(1), control(0x100, size)), (code(2), control(0x100, size))])
        return ss.snvn_records(snvn(order, rec), 0x18, 0x18 + 12 + len(rec), 'test', order)

    def test_both_byte_orders(self):
        for order in (BIG, LITTLE):
            with self.subTest(order=order):
                (_, st), = self.roundtrip(order)
                self.assertEqual([(len(c), k[4]) for c, k in st], [(0x840, 1), (0x840, 2)])

    def test_the_other_order_finds_nothing(self):
        rec = record(LITTLE, [(code(1), control(0x100, 0x880))])
        self.assertEqual(ss.snvn_records(snvn(LITTLE, rec), 0x18, 0x18 + 12 + len(rec), 'test', BIG), [])

    def test_a_table_past_the_section_with_padding_before_the_next(self):
        table = bytes(0xc)   # 0x88c bytes: the next section starts at +0x890, and the alignment of the control length alone is not 0x40
        rec = record(LITTLE, [(code(1), control(0x100, 0x880, table, 1)), (code(2), control(0x100, 0x880))])
        (_, st), = ss.snvn_records(snvn(LITTLE, rec), 0x18, 0x18 + 12 + len(rec), 'test', LITTLE)
        self.assertEqual([(len(c), k[4]) for c, k in st], [(0x88c, 1), (0x880, 2)])

    def test_a_table_on_the_last_section_has_no_padding(self):
        rec = record(LITTLE, [(code(1), control(0x100, 0x880)), (code(2), control(0x100, 0x880, bytes(0xc), 1))])
        (_, st), = ss.snvn_records(snvn(LITTLE, rec), 0x18, 0x18 + 12 + len(rec), 'test', LITTLE)
        self.assertEqual([len(c) for c, _ in st], [0x880, 0x88c])

    def test_a_field_that_does_not_name_the_section_length_is_no_table(self):
        c = bytearray(control(0x100, 0x840))
        struct.pack_into('<II', c, 0x7e8, 0x1234, 0x5678)   # SDK 4: these words mean something else
        rec = record(BIG, [(code(1), bytes(c)), (code(2), control(0x100, 0x840))])
        (_, st), = ss.snvn_records(snvn(BIG, rec), 0x18, 0x18 + 12 + len(rec), 'test', BIG)
        self.assertEqual([len(s) for s, _ in st], [0x840, 0x840])


class Files(unittest.TestCase):
    def material(self, order, size, fill):
        return form(order, b'MTRL', snvn(order, record(order, [(code(fill), control(0x100, size))])))

    def test_a_single_form_in_both_orders(self):
        for order in (BIG, LITTLE):
            with self.subTest(order=order):
                self.assertEqual(stages(ss.rfrm_shaders(self.material(order, 0x880, 7), '/x.arc')), [(ss.CTL_MAGIC, 0x880, 7)])

    def test_a_big_endian_pack_of_36_byte_entries(self):
        r = form(BIG, b'MTRL', zlib.compress(self.material(BIG, 0x840, 3)))
        self.assertEqual(stages(ss.rfrm_shaders(pack_big(r), '/x.pak')), [(ss.CTL_MAGIC, 0x840, 3)])

    def test_a_little_endian_pack_of_52_byte_entries(self):
        r = form(LITTLE, b'MTRL', zlib.compress(self.material(LITTLE, 0x880, 5)), 168)
        self.assertEqual(stages(ss.rfrm_shaders(pack_little(r), '/x.pak')), [(ss.CTL_MAGIC, 0x880, 5)])

    def test_a_pack_with_no_materials_is_quick_and_empty(self):
        adir = chunk(LITTLE, b'ADIR', struct.pack('<I', 1) + b'TXTR' + GUID + struct.pack('<IIQQQ', 1, 1, 0, 0, 0))
        self.assertEqual(ss.rfrm_shaders(form(LITTLE, b'PACK', form(LITTLE, b'TOCC', adir, 3)), '/x.pak'), [])

    def test_an_adir_of_an_unknown_entry_size_stops(self):
        adir = chunk(LITTLE, b'ADIR', struct.pack('<I', 2) + bytes(80))
        with self.assertRaises(SystemExit) as stop: ss.rfrm_shaders(form(LITTLE, b'PACK', adir), '/x.pak')
        self.assertIn('entries of a known size', str(stop.exception))

    def test_a_little_endian_startup_form_compressed_into_main(self):
        x = self.material(LITTLE, 0x880, 9)
        lzss = b''.join(b'\0' + x[i:i + 8] for i in range(0, len(x), 8))   # a clear flag byte: eight literals
        main = b'pad' + b'\x01\0\0\0' + lzss
        self.assertEqual(stages(ss.retro_main_forms(main, 'main')), [(ss.CTL_MAGIC, 0x880, 9)])


if __name__ == '__main__':
    unittest.main()
