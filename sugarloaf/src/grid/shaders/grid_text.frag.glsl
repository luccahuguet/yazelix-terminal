#version 450

// Text fragment shader. One combined-image-sampler bound at
// `set=1, binding=0` — the page-list atlas (`grid/vulkan.rs`) binds
// one page's image+sampler here per draw call. The host packs cells
// by (kind, page) into separate buckets, so each draw uniformly
// samples one page, and a fragment-stage push constant carries the
// kind (`is_color`) so the shader picks the right sampling mode.
//
// Grayscale masks use `texelFetch` at integer pixel coordinates so
// terminal text remains crisp. Color atlas entries use filtered image
// sampling so emoji bitmaps do not become jagged when constrained to
// grid cells.

layout(set = 1, binding = 0) uniform sampler2D atlas;

layout(push_constant) uniform PushConstants {
    // 0 = grayscale (alpha mask × in_color), 1 = color (RGBA premul).
    uint is_color;
} pc;

layout(location = 0) flat in vec4 in_color;
layout(location = 1)      in vec2 in_tex_coord;

layout(location = 0) out vec4 out_color;

void main() {
    ivec2 uv = ivec2(in_tex_coord);
    if (pc.is_color == 0u) {
        vec4 s = texelFetch(atlas, uv, 0);
        // Grayscale: sample alpha mask, multiply by per-glyph color.
        // Color is already premultiplied (in_color.rgb *= in_color.a
        // in the vertex shader), so the result is also premultiplied.
        out_color = in_color * s.r;
    } else {
        // Color atlas: sample premultiplied RGBA with the descriptor's
        // linear sampler.
        vec2 dims = vec2(textureSize(atlas, 0));
        vec2 color_uv = in_tex_coord / dims;
        out_color = texture(atlas, color_uv);
    }
}
