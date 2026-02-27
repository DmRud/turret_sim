#version 130

// Thermal imaging post-process shader.
// Reads the scope texture, converts to luminance, maps through
// a thermal palette: black → blue → magenta → red → yellow → white.

uniform sampler2D p3d_Texture0;
in vec2 texcoord;
out vec4 fragColor;

void main() {
    vec4 color = texture(p3d_Texture0, texcoord);

    // Luminance (perceptual weights)
    float lum = dot(color.rgb, vec3(0.299, 0.587, 0.114));

    // Invert: sky/background (bright) becomes cold (dark),
    // objects (darker) become hot (bright).
    float heat = 1.0 - lum;

    // Boost contrast
    heat = clamp(heat * 1.4 - 0.1, 0.0, 1.0);

    // Thermal palette: 5-stop gradient
    //   0.00 → dark navy    (cold sky)
    //   0.25 → deep blue
    //   0.50 → magenta/purple
    //   0.75 → red-orange
    //   1.00 → bright yellow-white (hot target)
    vec3 thermal;
    if (heat < 0.25) {
        float t = heat / 0.25;
        thermal = mix(vec3(0.02, 0.02, 0.08), vec3(0.05, 0.1, 0.45), t);
    } else if (heat < 0.5) {
        float t = (heat - 0.25) / 0.25;
        thermal = mix(vec3(0.05, 0.1, 0.45), vec3(0.55, 0.1, 0.55), t);
    } else if (heat < 0.75) {
        float t = (heat - 0.5) / 0.25;
        thermal = mix(vec3(0.55, 0.1, 0.55), vec3(0.9, 0.3, 0.05), t);
    } else {
        float t = (heat - 0.75) / 0.25;
        thermal = mix(vec3(0.9, 0.3, 0.05), vec3(1.0, 1.0, 0.85), t);
    }

    fragColor = vec4(thermal, 1.0);
}
