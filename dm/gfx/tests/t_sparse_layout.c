// Storage sizes of sparse (flag 0x20) 2D textures with the automatic block height, against the sizes of the pre-swizzled level data the games ship: Yoshi's Crafted World's
// streamed DXT and BGRA8 textures (one level each) and Monster Hunter Rise's 1024×1024 ASTC 6×6 (48 GOBs wide, level 1 at 0x90000). A non-sparse texture keeps the automatic block height
#include <stdio.h>
#include "../nvn/nvn_tex.h"

static int g_n, g_fail;

static void check_size(uint32_t w, uint32_t h, int format, int flags, uint64_t want) {
    nvn_texdesc d = { .target = 1, .format = format, .flags = flags, .width = w, .height = h, .depth = 1, .levels = 1 };
    nvn_texlayout L; nvn_tex_layout(&d, &L);
    g_n++; if (L.size != want) g_fail++;
    printf("%4ux%-4u format %#x flags %#x: size %#llx (want %#llx) %s\n", w, h, format, flags, (unsigned long long)L.size, (unsigned long long)want, L.size == want ? "✓" : "✗");
}

// A sparse 3D texture's block height and depth (log2 of the GOB count) and its size; the shape only moves its content, so the size is the same as with the automatic ones
static void check_3d(uint32_t w, uint32_t h, uint32_t z, int format, int flags, unsigned want_h, unsigned want_d, uint64_t want_size) {
    nvn_texdesc d = { .target = 2, .format = format, .flags = flags, .width = w, .height = h, .depth = z, .levels = 1 };
    nvn_texlayout L; nvn_tex_layout(&d, &L);
    int ok = L.tileH == want_h && L.tileD == want_d && L.size == want_size;
    g_n++; if (!ok) g_fail++;
    printf("%ux%ux%u format %#x flags %#x: block height / depth log2 %u/%u, size %#llx (want %u/%u, %#llx) %s\n", w, h, z, format, flags, L.tileH, L.tileD, (unsigned long long)L.size, want_h, want_d, (unsigned long long)want_size, ok ? "✓" : "✗");
}

int main(void) {
    static const struct { uint32_t w, h; int format; uint64_t size; } yoshi[] = {
        {384, 384, 0x48, 0x40000}, {384, 384, 0x45, 0x20000}, {960, 384, 0x48, 0x80000}, {480, 480, 0x48, 0x40000}, {900, 420, 0x48, 0x80000},
        {1920, 912, 0x48, 0x200000}, {1920, 864, 0x48, 0x200000}, {1440, 480, 0x48, 0xc0000}, {840, 448, 0x48, 0x80000}, {840, 840, 0x48, 0x100000},
        {1350, 270, 0x9c, 0x210000}, {240, 270, 0x9c, 0x60000}, {720, 270, 0x9c, 0x120000}, {1080, 174, 0x9c, 0x120000}, {2010, 390, 0x9c, 0x400000},
    };
    for (unsigned i = 0; i < sizeof yoshi / sizeof *yoshi; i++) check_size(yoshi[i].w, yoshi[i].h, yoshi[i].format, 0x20, yoshi[i].size);
    check_size(384, 384, 0x48, 0, 0x30000);
    nvn_texdesc mh = { .target = 1, .format = 0x7d, .flags = 0x20, .width = 1024, .height = 1024, .depth = 1, .levels = 11 };
    uint64_t l1 = nvn_tex_level_offset(&mh, 1); uint32_t g0 = nvn_tex_level_gobs(&mh, 0);
    g_n++; if (l1 != 0x90000 || g0 != 48) g_fail++;
    printf("1024x1024 ASTC 6x6 sparse: level 0 %u GOBs wide, level 1 at %#llx (want 48, 0x90000) %s\n", g0, (unsigned long long)l1, l1 == 0x90000 && g0 == 48 ? "✓" : "✗");
    // Metroid Prime Remastered's lighting volumes: 16- and 8-byte blocks, 16x16x16 and 32x16x16 blocks to a 64 KB tile
    check_3d(512, 256, 368, 0x50, 0x20, 1, 4, 0x2e00000); check_3d(512, 256, 368, 0x42, 0x20, 1, 4, 0x1700000);
    check_3d(256, 128, 32, 0x50, 0x20, 1, 4, 0x100000); check_3d(256, 128, 32, 0x42, 0x20, 1, 4, 0x80000);
    check_3d(64, 64, 64, 0x1, 0x20, 2, 5, 0x40000);   // 1 byte per block: a tile of 64x32x32
    check_3d(64, 64, 32, 0x25, 0x20, 2, 4, 0x80000);   // 4 bytes per block: a tile of 32x32x16
    // Not sparse, or smaller than one tile (all mip tail): the automatic ones (its fog volume, its 33x33x33 colour grading tables)
    check_3d(100, 57, 64, 0x29, 0, 0, 4, 0x340000); check_3d(33, 33, 33, 0x25, 0, 0, 4, 0x5a000);
    check_3d(8, 8, 8, 0x25, 0x20, 0, 3, 0x10000);
    printf("== %d checks, %d failed ==\n", g_n, g_fail);
    return g_fail != 0;
}
