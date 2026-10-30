// Which render targets take the render scale above the game's own resolution, and how sizes and regions round (nvn_rscale.h).
#include <stdio.h>
#include "../nvn/nvn_rscale.h"

enum { COMPRESSIBLE = 8, REFUSE = 2 | 0x10 | 0x20 | 0x40 };   // NVN_TEXTURE_FLAGS: video decode, linear, sparse, linear render target
static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); fails++; } } while (0)
static int scalable(uint32_t target, uint32_t samples, uint32_t flags, uint32_t w, uint32_t h, int packaged) { return rs_scalable(target, samples, flags, w, h, packaged, COMPRESSIBLE, REFUSE); }

int main(void) {
    // Metroid Prime Remastered's frame: the scene and its depth, the half-size and bloom chains of about 16:9
    uint32_t yes[][2] = {{1600, 900}, {800, 456}, {400, 225}, {200, 112}, {100, 56}, {50, 28}, {1280, 720}, {1920, 1080}};
    for (unsigned i = 0; i < sizeof yes / sizeof yes[0]; i++) CHECK(scalable(1, 0, COMPRESSIBLE, yes[i][0], yes[i][1], 0));
    // ... and what stays: another shape (its bloom, its light list, a shadow map), too small to be a view of the picture
    uint32_t no[][2] = {{1024, 512}, {646, 32}, {2888, 2888}, {25, 14}, {16, 9}};
    for (unsigned i = 0; i < sizeof no / sizeof no[0]; i++) CHECK(!scalable(1, 0, COMPRESSIBLE, no[i][0], no[i][1], 0));
    CHECK(scalable(1, 0, COMPRESSIBLE | 1 | 4, 1600, 900, 0));   // a window texture, and a target also used as an image
    CHECK(!scalable(1, 0, 0, 1600, 900, 0));                     // not compressible: game data of that size (its 1600x900 UI textures)
    CHECK(!scalable(1, 0, COMPRESSIBLE, 1600, 900, 1));          // packaged data: its bytes are laid out for the game's size
    CHECK(!scalable(1, 4, COMPRESSIBLE, 1600, 900, 0));          // multisampled
    CHECK(!scalable(2, 0, COMPRESSIBLE, 1600, 900, 0));          // a 3D texture (the fog volume's target), an array, a cube
    CHECK(!scalable(4, 0, COMPRESSIBLE, 1600, 900, 0));
    for (uint32_t f = 2; f <= 0x40; f <<= 1) if (f & REFUSE) CHECK(!scalable(1, 0, COMPRESSIBLE | f, 1600, 900, 0));

    // A target's size rounds up, so that a size query (size / scale, truncated by the translator's TextureSizeUnscale) gives the game's size back
    float scales[] = {1.25f, 1.5f, 1.75f, 2, 2.25f, 2.5f, 3};
    for (unsigned s = 0; s < sizeof scales / sizeof scales[0]; s++)
        for (uint32_t n = 1; n <= 4096; n++) { uint32_t up = rs_up(n, scales[s]); CHECK(up >= n * scales[s]); CHECK((uint32_t)((float)up / scales[s]) == n); }
    CHECK(rs_up(1600, 2) == 3200); CHECK(rs_up(225, 1.5f) == 338);

    // A region grows outward and stays inside the larger target; at scale 1 nothing changes
    CHECK(rs_lo(10, 1.5f) == 15); CHECK(rs_lo(11, 1.5f) == 16); CHECK(rs_hi(11, 1.5f) == 17);
    CHECK(rs_hi(225, 1.5f) == (long)rs_up(225, 1.5f));
    for (long v = -3; v < 20000; v += 7) { CHECK(rs_lo(v, 1) == v); CHECK(rs_hi(v, 1) == v); }
    if (fails) { printf("t_rscale: %d failed\n", fails); return 1; }
    printf("t_rscale: ok\n");
    return 0;
}
