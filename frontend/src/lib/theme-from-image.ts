/** Build a whole page theme out of a dropped picture.
 *
 *  Deliberately not an AI call. Pulling the colours out of an image is pixel
 *  arithmetic with an exact answer, so a model would only add a round trip, a
 *  cost and a failure mode to a thing that is instant and cannot fail.
 *
 *  The one rule everything below serves: **the app has to stay readable.** A
 *  dominant colour used raw as a page background is a wall of saturated paint
 *  with unreadable text on it, so the image only ever supplies a *hue*; this
 *  file decides the lightness and the saturation, then checks the result
 *  against WCAG and overrides itself when it fails.
 */

export interface Rgb {
  r: number;
  g: number;
  b: number;
}

export interface Swatch extends Rgb {
  count: number;
}

export interface Palette {
  /** Most common colour in the picture. Decides the hue of the whole page. */
  dominant: Rgb;
  /** Most colourful frequent colour. Becomes buttons, links and highlights. */
  vibrant: Rgb;
  /** The top few, for the swatch strip in the panel. */
  swatches: Swatch[];
  /** True when the picture is mostly dark, so the theme goes dark with it. */
  dark: boolean;
}

// --- conversions --------------------------------------------------------------

export function toHex({ r, g, b }: Rgb): string {
  const part = (n: number) =>
    Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
  return `#${part(r)}${part(g)}${part(b)}`;
}

export function rgbToHsl({ r, g, b }: Rgb): { h: number; s: number; l: number } {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };

  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h: number;
  if (max === rn) h = ((gn - bn) / d + (gn < bn ? 6 : 0)) / 6;
  else if (max === gn) h = ((bn - rn) / d + 2) / 6;
  else h = ((rn - gn) / d + 4) / 6;
  return { h: h * 360, s, l };
}

export function hslToRgb(h: number, s: number, l: number): Rgb {
  const hn = (((h % 360) + 360) % 360) / 360;
  if (s === 0) {
    const v = l * 255;
    return { r: v, g: v, b: v };
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const channel = (t: number) => {
    let tn = t;
    if (tn < 0) tn += 1;
    if (tn > 1) tn -= 1;
    if (tn < 1 / 6) return p + (q - p) * 6 * tn;
    if (tn < 1 / 2) return q;
    if (tn < 2 / 3) return p + (q - p) * (2 / 3 - tn) * 6;
    return p;
  };
  return {
    r: channel(hn + 1 / 3) * 255,
    g: channel(hn) * 255,
    b: channel(hn - 1 / 3) * 255,
  };
}

// --- contrast -----------------------------------------------------------------

/** WCAG relative luminance. */
export function luminance({ r, g, b }: Rgb): number {
  const channel = (v: number) => {
    const n = v / 255;
    return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio, 1 (identical) to 21 (black on white). */
export function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

const NEAR_BLACK: Rgb = { r: 17, g: 17, b: 20 };
const NEAR_WHITE: Rgb = { r: 252, g: 252, b: 252 };

/** Whichever of near-black / near-white reads better on this background.
 *
 *  This is the function that keeps the app usable whatever gets dropped on it:
 *  every foreground token in the theme goes through it rather than being taken
 *  from the picture.
 *
 *  The softened black and white are nicer to read, but against a background of
 *  around 19% luminance the better of them only reaches 4.27:1 — under AA. Pure
 *  black and pure white bottom out at 4.58:1 instead, so that pair is the
 *  fallback whenever the soft one would fail. */
export function readableOn(background: Rgb): Rgb {
  const soft =
    contrast(NEAR_BLACK, background) >= contrast(NEAR_WHITE, background)
      ? NEAR_BLACK
      : NEAR_WHITE;
  if (contrast(soft, background) >= 4.5) return soft;

  const black = { r: 0, g: 0, b: 0 };
  const white = { r: 255, g: 255, b: 255 };
  return contrast(black, background) >= contrast(white, background) ? black : white;
}

/** Push a colour's lightness until it clears `target` against `against`.
 *
 *  Used for the accent: a pale yellow vibrant colour is invisible as a button on
 *  a white page, and darkening it until it passes is better than discarding the
 *  picture's colour altogether. */
export function ensureContrast(colour: Rgb, against: Rgb, target = 4.5): Rgb {
  if (contrast(colour, against) >= target) return colour;
  const { h, s } = rgbToHsl(colour);
  const goDarker = luminance(against) > 0.2;
  let best = colour;
  let bestRatio = contrast(colour, against);
  // Walk lightness in small steps and keep the first that clears the bar. The
  // loop is bounded, so a hue that can never pass returns its closest attempt
  // rather than spinning.
  for (let i = 1; i <= 20; i += 1) {
    const l = goDarker ? 0.5 - i * 0.025 : 0.5 + i * 0.025;
    const candidate = hslToRgb(h, s, Math.max(0.03, Math.min(0.97, l)));
    const ratio = contrast(candidate, against);
    if (ratio > bestRatio) {
      best = candidate;
      bestRatio = ratio;
    }
    if (ratio >= target) return candidate;
  }
  return best;
}

// --- reading the picture ------------------------------------------------------

/** Count colours in downsampled pixel data, quantised into 4-bit buckets.
 *
 *  Exported and pure so the mapping can be tested on a handful of made-up
 *  pixels rather than through a canvas. */
export function extractPalette(pixels: Uint8ClampedArray): Palette {
  const buckets = new Map<number, { r: number; g: number; b: number; count: number }>();

  for (let i = 0; i < pixels.length; i += 4) {
    const alpha = pixels[i + 3];
    if (alpha < 125) continue; // transparent corners are not part of the picture
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];
    const key = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4);
    const bucket = buckets.get(key);
    if (bucket) {
      bucket.r += r;
      bucket.g += g;
      bucket.b += b;
      bucket.count += 1;
    } else {
      buckets.set(key, { r, g, b, count: 1 });
    }
  }

  if (buckets.size === 0) {
    const grey = { r: 128, g: 128, b: 128 };
    return { dominant: grey, vibrant: grey, swatches: [], dark: false };
  }

  const swatches: Swatch[] = [...buckets.values()]
    .map((bucket) => ({
      r: bucket.r / bucket.count,
      g: bucket.g / bucket.count,
      b: bucket.b / bucket.count,
      count: bucket.count,
    }))
    .sort((a, b) => b.count - a.count);

  const dominant = swatches[0];

  // The accent wants colour, not frequency: a photo is mostly muted browns and
  // greys, and picking the commonest again would give a beige button on a beige
  // page. Score the frequent ones by saturation, with a nudge for mid lightness
  // so a near-black or near-white pixel does not win on saturation noise.
  const considered = swatches.slice(0, 24);
  const mostSeen = considered[0]?.count || 1;
  let vibrant = dominant;
  let bestScore = -1;
  for (const swatch of considered) {
    const { s, l } = rgbToHsl(swatch);
    const midness = 1 - Math.abs(l - 0.5) * 2;
    // Frequency counts too, or a dozen bright pixels in one corner outvote the
    // colour the picture actually looks like.
    const share = swatch.count / mostSeen;
    const score = s * 0.55 + midness * 0.15 + share * 0.3;
    if (score > bestScore) {
      bestScore = score;
      vibrant = swatch;
    }
  }

  // Weighted average lightness decides light or dark, so a mostly-black photo
  // gives a dark page instead of black text on black.
  const total = swatches.reduce((sum, s) => sum + s.count, 0);
  const meanL =
    swatches.reduce((sum, s) => sum + rgbToHsl(s).l * s.count, 0) / (total || 1);

  return { dominant, vibrant, swatches: swatches.slice(0, 6), dark: meanL < 0.42 };
}

// --- building the theme -------------------------------------------------------

/** The CSS custom properties this theme overrides, as name → colour. */
export type ThemeVars = Record<string, string>;

/** Turn a palette into the app's design tokens.
 *
 *  The picture gives two things and no more: the hue of the page and the accent
 *  colour. Every lightness, every saturation and every foreground is decided
 *  here, which is why a photo of a black cat and a photo of a sunset both come
 *  out as something you can still read a passage in.
 */
export function buildTheme(palette: Palette): ThemeVars {
  const { h, s } = rgbToHsl(palette.dominant);
  const dark = palette.dark;

  // Enough of the picture's hue that the page is visibly *that* picture's
  // colour, but held at a lightness you can still read a passage on. A ginger
  // cat should give warm paper, not white, and not orange paint.
  const tint = Math.min(s, 0.7);
  const background = dark
    ? hslToRgb(h, tint * 0.55, 0.15)
    : hslToRgb(h, tint * 0.85, 0.945);
  const card = dark ? hslToRgb(h, tint * 0.5, 0.2) : hslToRgb(h, tint * 0.55, 0.985);
  const muted = dark ? hslToRgb(h, tint * 0.5, 0.26) : hslToRgb(h, tint * 0.9, 0.9);
  const border = dark ? hslToRgb(h, tint * 0.45, 0.32) : hslToRgb(h, tint * 0.8, 0.84);

  // Take the accent's hue and saturation, but set its lightness outright: a
  // pale yellow walked down until it passes contrast arrives as mud, whereas
  // the same hue placed at a chosen lightness stays a colour.
  const vibrantHsl = rgbToHsl(palette.vibrant);
  const primary = ensureContrast(
    hslToRgb(vibrantHsl.h, Math.max(vibrantHsl.s, 0.35), dark ? 0.62 : 0.44),
    background,
    4.5,
  );
  const primaryHsl = rgbToHsl(primary);
  const accent = dark
    ? hslToRgb(primaryHsl.h, Math.max(primaryHsl.s * 0.5, 0.15), 0.28)
    : hslToRgb(primaryHsl.h, Math.max(primaryHsl.s * 0.6, 0.15), 0.93);

  const foreground = readableOn(background);
  const mutedForeground = ensureContrast(
    hslToRgb(h, tint * 0.3, dark ? 0.68 : 0.42),
    muted,
    4.5,
  );

  return {
    "--background": toHex(background),
    "--foreground": toHex(foreground),
    "--card": toHex(card),
    "--card-foreground": toHex(readableOn(card)),
    "--popover": toHex(card),
    "--popover-foreground": toHex(readableOn(card)),
    "--primary": toHex(primary),
    "--primary-foreground": toHex(readableOn(primary)),
    "--secondary": toHex(muted),
    "--secondary-foreground": toHex(readableOn(muted)),
    "--muted": toHex(muted),
    "--muted-foreground": toHex(mutedForeground),
    "--accent": toHex(accent),
    "--accent-foreground": toHex(readableOn(accent)),
    "--border": toHex(border),
    "--input": toHex(border),
    "--ring": `${toHex(primary)}73`,
    "--sidebar": toHex(dark ? hslToRgb(h, tint * 0.45, 0.17) : muted),
    "--sidebar-foreground": toHex(readableOn(dark ? hslToRgb(h, tint * 0.45, 0.17) : muted)),
    "--sidebar-primary": toHex(primary),
    "--sidebar-primary-foreground": toHex(readableOn(primary)),
    "--sidebar-accent": toHex(accent),
    "--sidebar-accent-foreground": toHex(readableOn(accent)),
    "--sidebar-border": toHex(border),
    "--sidebar-ring": toHex(primary),
  };
}

/** Every token the theme sets, so resetting can remove exactly these and leave
 *  anything set elsewhere alone. */
export const THEMED_VARS = Object.keys(
  buildTheme({
    dominant: { r: 128, g: 128, b: 128 },
    vibrant: { r: 128, g: 128, b: 128 },
    swatches: [],
    dark: false,
  }),
);
