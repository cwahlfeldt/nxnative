// Render scale above the game's own resolution (DM_RENDER_SCALE above 1, nvn_mtl.m): the host makes the game's render targets larger, and the game keeps seeing their own size. Which targets, and how a region
// of the game's pixels lands on the host's. The translator already scales what a shader sees: gl_FragCoord is divided by render_scale[0], and texel fetches and size queries go through render_scale[1 + i]
// (i = the texture's position among the shader's textures), which the host fills per draw. Single-sampled 2D targets of about 16:9 only: a game's lookup tables, shadow maps, bloom chains of other shapes and
// light lists are addressed by size or index and stay as they are (the rule of PrimeRecomp's renderer; Metroid Prime Remastered's 1600x900 scene, 800x456 and 400x225 chains scale, its 1024x512 bloom and 646x32 light list do not).
#ifndef NVN_RSCALE_H
#define NVN_RSCALE_H
#include <math.h>
#include <stdint.h>

#define RS_MAX 3.0f   // 9 times the pixels; DM_RENDER_SCALE above it is refused

// A texture (NVN target, samples, flags, size, whether it is packaged game data) renders at the scale. flag_* are the NVN texture flags it depends on
static inline int rs_scalable(uint32_t target, uint32_t samples, uint32_t flags, uint32_t w, uint32_t h, int packaged, uint32_t flag_compressible, uint32_t flag_refuse) {
    if (target != 1 || samples > 1 || packaged || !(flags & flag_compressible) || (flags & flag_refuse) || w < 32 || h < 16) return 0;
    float a = (float)w / (float)h; return a > 1.74f && a < 1.81f;
}
static inline uint32_t rs_up(uint32_t n, float s) { return (uint32_t)ceil((double)n * s); }   // a target's size: rounded up, so a size query divided by the scale and truncated gives the game's size back
static inline long rs_lo(long v, float s) { return s == 1 ? v : (long)floor((double)v * s); }   // a region's low edge and high edge: outward
static inline long rs_hi(long v, float s) { return s == 1 ? v : (long)ceil((double)v * s); }
#endif
