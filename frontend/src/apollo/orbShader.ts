/* ==================================================================== */
/* Apollo orb — fragment shader                                          */
/*                                                                       */
/* All distances are in half-box units: uv ∈ [-1,1] across the shorter    */
/* canvas edge, so the halo can fade out before the quad is clipped.      */
/* The orb is an SDF sphere with a domain-warped plasma interior, a       */
/* fresnel rim and three transient layers: amber failover shockwave,      */
/* crimson error pulse and a directional dispatch flare.                  */
/* ==================================================================== */

export const VERTEX_SHADER = /* glsl */ `
attribute vec2 a_pos;
void main() {
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

export const FRAGMENT_SHADER = /* glsl */ `
precision highp float;

uniform vec2  u_res;
uniform float u_time;
uniform float u_energy;       // 0 idle .. 1 full turbulence
uniform float u_hover;        // 0 .. 1
uniform float u_shock;        // failover shockwave, 1 -> 0
uniform float u_error;        // error ring, 1 -> 0
uniform float u_flare;        // dispatch flare, 1 -> 0
uniform float u_flareAngle;   // radians, 0 = +x
uniform vec3  u_colA;         // deep body colour
uniform vec3  u_colB;         // rim / glow colour

#define PI 3.14159265

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 rot = mat2(0.80, 0.60, -0.60, 0.80);
  for (int i = 0; i < 4; i++) {
    v += a * vnoise(p);
    p = rot * p * 2.03;
    a *= 0.5;
  }
  return v;
}

void main() {
  // half-box normalised coordinates
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_res) / (0.5 * min(u_res.x, u_res.y));
  float t = u_time;
  float R = 0.52;
  float d = length(uv);

  // --- membrane: harmonic breathing + energy-driven turbulence --------
  float breathe = 0.014 * sin(t * 0.85) + 0.007 * sin(t * 1.41 + 1.7);
  vec2 q = uv * 2.2;
  float turb  = fbm(q + vec2(t * 0.16, -t * 0.11));
  float turb2 = fbm(q * 1.9 + vec2(-t * 0.24, t * 0.19));
  float wobble = ((turb - 0.5) * 0.55 + (turb2 - 0.5) * 0.45) * (0.020 + 0.120 * u_energy);
  float membrane = R + breathe + wobble;
  float inside = 1.0 - smoothstep(membrane - 0.008, membrane + 0.008, d);

  // --- sphere normal --------------------------------------------------
  float nd = clamp(d / max(membrane, 1e-3), 0.0, 1.0);
  float z = sqrt(max(0.0, 1.0 - nd * nd));
  vec3 n = vec3(uv / max(membrane, 1e-3), z);

  // --- plasma: polar swirl, two warped octave layers -------------------
  float ang = atan(uv.y, uv.x);
  float spin = t * (0.18 + 0.55 * u_energy);
  vec2 sw = vec2(cos(ang + spin), sin(ang + spin)) * (0.30 + 0.85 * nd);
  float w1 = fbm(sw * 2.6 + fbm(sw * 1.4 + t * 0.17) * 1.7);
  float w2 = fbm(sw * 5.4 - t * 0.21 + w1 * 0.9);
  float veins = smoothstep(0.34, 0.68, w1) * 0.80 + smoothstep(0.55, 0.92, w2) * 0.45;
  veins = clamp(veins, 0.0, 1.25);

  // Dark plasma body: the veins are the light source, the body stays black.
  vec3 plasma = mix(u_colA * 0.80, mix(u_colA, u_colB, 0.62), clamp(veins, 0.0, 1.0));
  plasma += u_colB * pow(1.0 - nd, 3.0) * 0.20;   // gentle inner bloom
  plasma += mix(u_colB, vec3(1.0), 0.5) * pow(1.0 - nd, 9.0) * 0.16; // small hot centre

  // --- lighting -------------------------------------------------------
  vec3 lightDir = normalize(vec3(-0.50, 0.62, 0.90));
  float diff = clamp(dot(n, lightDir), 0.0, 1.0);
  float fres = pow(1.0 - z, 2.0);
  float spec = pow(clamp(dot(reflect(-lightDir, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 48.0);

  vec3 col = plasma * (0.45 + 0.80 * diff);
  col *= mix(0.30, 1.0, pow(z, 0.70));            // volume falloff to the limb
  col += u_colB * fres * 0.80;                    // fresnel
  col += vec3(1.0) * spec * 0.30;                 // specular

  // thin hot silhouette
  float rim = exp(-pow((d - membrane) / 0.008, 2.0));
  col += mix(u_colB, vec3(1.0), 0.40) * rim * (0.85 + u_hover * 0.55);

  // --- halo (fades well inside the quad) ------------------------------
  float halo = exp(-pow((d - membrane) / 0.070, 2.0)) * 0.55;
  halo += exp(-pow((d - membrane) / 0.24, 2.0)) * 0.16;
  col += u_colB * halo * (0.55 + 0.55 * u_hover);

  // --- failover shockwave (amber) ------------------------------------
  if (u_shock > 0.001) {
    float swr = mix(membrane, 0.98, 1.0 - u_shock);
    float ring = exp(-pow((d - swr) / (0.010 + 0.05 * u_shock), 2.0));
    col += vec3(0.961, 0.620, 0.043) * ring * u_shock * 1.9;
  }

  // --- error pulse (crimson, damped) ---------------------------------
  if (u_error > 0.001) {
    float wob = sin(d * 42.0 - t * 26.0) * 0.5 + 0.5;
    float ring = exp(-pow((d - membrane * (1.02 + 0.05 * sin(t * 18.0))) / 0.018, 2.0));
    col += vec3(0.937, 0.267, 0.267) * ring * wob * u_error;
    col += vec3(0.937, 0.267, 0.267) * (1.0 - inside) * u_error * 0.10;
  }

  // --- dispatch flare (directional beam) -----------------------------
  if (u_flare > 0.001) {
    float diffA = abs(mod(atan(uv.y, uv.x) - u_flareAngle + PI, 2.0 * PI) - PI);
    float beam = pow(max(0.0, 1.0 - diffA / 0.60), 5.0);
    float reach = smoothstep(membrane * 0.9, 0.95, d) * (1.0 - smoothstep(0.95, 1.30, d));
    col += mix(u_colB, vec3(0.85, 1.0, 1.0), 0.4) * beam * (0.45 + reach) * u_flare * 1.2;
  }

  // --- finish ---------------------------------------------------------
  float alpha = clamp(inside * 0.98 + halo * 0.55 + rim * 0.55, 0.0, 1.0);
  col = pow(max(col, 0.0), vec3(0.92));
  gl_FragColor = vec4(col, alpha);
}
`;
