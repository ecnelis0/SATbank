import { describe, expect, it } from "vitest";

import {
  buildTheme,
  contrast,
  extractPalette,
  hslToRgb,
  luminance,
  readableOn,
  rgbToHsl,
  THEMED_VARS,
  toHex,
  type Rgb,
} from "@/lib/theme-from-image";

/** Build pixel data from a list of [r,g,b,a] repeated `times`. */
function pixels(...runs: Array<{ colour: [number, number, number, number]; times: number }>) {
  const out: number[] = [];
  for (const run of runs) {
    for (let i = 0; i < run.times; i += 1) out.push(...run.colour);
  }
  return new Uint8ClampedArray(out);
}

function fromHex(hex: string): Rgb {
  return {
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16),
  };
}

describe("colour maths", () => {
  it("matches the WCAG reference points", () => {
    const black = { r: 0, g: 0, b: 0 };
    const white = { r: 255, g: 255, b: 255 };
    expect(contrast(black, white)).toBeCloseTo(21, 1);
    expect(contrast(white, white)).toBeCloseTo(1, 5);
    expect(luminance(white)).toBeCloseTo(1, 5);
    expect(luminance(black)).toBeCloseTo(0, 5);
  });

  it("round-trips through HSL", () => {
    for (const colour of [
      { r: 200, g: 40, b: 90 },
      { r: 12, g: 180, b: 240 },
      { r: 128, g: 128, b: 128 },
    ]) {
      const { h, s, l } = rgbToHsl(colour);
      const back = hslToRgb(h, s, l);
      expect(back.r).toBeCloseTo(colour.r, 0);
      expect(back.g).toBeCloseTo(colour.g, 0);
      expect(back.b).toBeCloseTo(colour.b, 0);
    }
  });

  it("puts dark text on light and light text on dark", () => {
    expect(luminance(readableOn({ r: 250, g: 250, b: 250 }))).toBeLessThan(0.1);
    expect(luminance(readableOn({ r: 10, g: 10, b: 15 }))).toBeGreaterThan(0.5);
  });

  it("never returns a foreground under 4.5:1, at any background lightness", () => {
    // The crossover near 19% luminance is where the softened black and white
    // both fail; this walks straight through it.
    for (let v = 0; v <= 255; v += 1) {
      const background = { r: v, g: v, b: v };
      expect(contrast(readableOn(background), background)).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe("reading a picture", () => {
  it("finds the commonest colour", () => {
    const data = pixels(
      { colour: [200, 30, 30, 255], times: 50 },
      { colour: [30, 30, 200, 255], times: 10 },
    );
    const palette = extractPalette(data);
    expect(palette.dominant.r).toBeGreaterThan(150);
    expect(palette.dominant.b).toBeLessThan(100);
  });

  it("ignores transparent pixels rather than reading them as black", () => {
    const data = pixels(
      { colour: [0, 0, 0, 0], times: 500 },
      { colour: [240, 200, 40, 255], times: 20 },
    );
    const palette = extractPalette(data);
    expect(palette.dominant.r).toBeGreaterThan(200);
    expect(palette.dark).toBe(false);
  });

  it("takes the accent from colour, not from frequency", () => {
    // A photo is mostly dull. The button must not come out beige.
    const data = pixels(
      { colour: [150, 145, 140, 255], times: 400 },
      { colour: [230, 20, 120, 255], times: 30 },
    );
    const palette = extractPalette(data);
    expect(rgbToHsl(palette.dominant).s).toBeLessThan(0.2);
    expect(rgbToHsl(palette.vibrant).s).toBeGreaterThan(0.6);
  });

  it("calls a mostly dark picture dark", () => {
    expect(extractPalette(pixels({ colour: [20, 18, 30, 255], times: 100 })).dark).toBe(true);
    expect(extractPalette(pixels({ colour: [240, 238, 230, 255], times: 100 })).dark).toBe(false);
  });

  it("survives an empty picture instead of dividing by zero", () => {
    const palette = extractPalette(new Uint8ClampedArray([]));
    expect(palette.swatches).toEqual([]);
    expect(() => buildTheme(palette)).not.toThrow();
  });
});

describe("building a theme", () => {
  // Every pair the app actually renders text in.
  const PAIRS: Array<[string, string]> = [
    ["--foreground", "--background"],
    ["--card-foreground", "--card"],
    ["--popover-foreground", "--popover"],
    ["--primary-foreground", "--primary"],
    ["--secondary-foreground", "--secondary"],
    ["--muted-foreground", "--muted"],
    ["--accent-foreground", "--accent"],
    ["--sidebar-foreground", "--sidebar"],
    ["--sidebar-accent-foreground", "--sidebar-accent"],
    ["--sidebar-primary-foreground", "--sidebar-primary"],
  ];

  const CASES: Array<[string, Rgb]> = [
    ["pure black", { r: 0, g: 0, b: 0 }],
    ["pure white", { r: 255, g: 255, b: 255 }],
    ["mid grey", { r: 128, g: 128, b: 128 }],
    ["saturated red", { r: 255, g: 0, b: 0 }],
    ["pale yellow", { r: 250, g: 245, b: 170 }],
    ["deep navy", { r: 10, g: 15, b: 60 }],
    ["ginger cat", { r: 208, g: 126, b: 54 }],
    ["neon green", { r: 40, g: 255, b: 90 }],
  ];

  it.each(CASES)("keeps every text pair readable for %s", (_name, colour) => {
    const palette = extractPalette(
      pixels({ colour: [colour.r, colour.g, colour.b, 255], times: 200 }),
    );
    const theme = buildTheme(palette);

    for (const [fg, bg] of PAIRS) {
      const ratio = contrast(fromHex(theme[fg]), fromHex(theme[bg]));
      expect(
        ratio,
        `${fg} on ${bg} was ${ratio.toFixed(2)}:1 (${theme[fg]} on ${theme[bg]})`,
      ).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("tints the page with the picture's hue rather than painting it", () => {
    const palette = extractPalette(pixels({ colour: [255, 0, 0, 255], times: 200 }));
    const background = rgbToHsl(fromHex(buildTheme(palette)["--background"]));

    // Two things at once, and the feature is only right when both hold: the
    // page is recognisably *this* picture's colour…
    expect(background.h).toBeLessThan(20);
    expect(background.s).toBeGreaterThan(0.2);
    // …and it is still paper rather than paint, so a passage is readable on it.
    expect(background.l).toBeGreaterThan(0.9);
  });

  it("keeps the hue of the picture across very different pictures", () => {
    const hues: Record<string, [number, number, number]> = {
      red: [230, 30, 30],
      green: [30, 200, 60],
      blue: [40, 70, 220],
    };
    const got = Object.fromEntries(
      Object.entries(hues).map(([name, colour]) => [
        name,
        rgbToHsl(
          fromHex(
            buildTheme(extractPalette(pixels({ colour: [...colour, 255], times: 200 })))[
              "--background"
            ],
          ),
        ).h,
      ]),
    );
    expect(Math.abs(got.red - rgbToHsl({ r: 230, g: 30, b: 30 }).h)).toBeLessThan(20);
    expect(Math.abs(got.green - rgbToHsl({ r: 30, g: 200, b: 60 }).h)).toBeLessThan(20);
    expect(Math.abs(got.blue - rgbToHsl({ r: 40, g: 70, b: 220 }).h)).toBeLessThan(20);
  });

  it("goes dark when the picture is dark", () => {
    const dark = buildTheme(extractPalette(pixels({ colour: [18, 16, 24, 255], times: 200 })));
    expect(rgbToHsl(fromHex(dark["--background"])).l).toBeLessThan(0.3);
    expect(luminance(fromHex(dark["--foreground"]))).toBeGreaterThan(0.5);
  });

  it("lists exactly the variables it sets, so a reset removes all of them", () => {
    const theme = buildTheme(extractPalette(pixels({ colour: [100, 150, 200, 255], times: 10 })));
    expect(new Set(THEMED_VARS)).toEqual(new Set(Object.keys(theme)));
    expect(THEMED_VARS).toContain("--background");
    expect(THEMED_VARS).toContain("--sidebar-ring");
  });

  it("writes every value as something CSS will accept", () => {
    const theme = buildTheme(extractPalette(pixels({ colour: [90, 200, 180, 255], times: 10 })));
    for (const [name, value] of Object.entries(theme)) {
      expect(value, name).toMatch(/^#[0-9a-f]{6}([0-9a-f]{2})?$/);
    }
  });

  it("formats hex with two digits a channel", () => {
    expect(toHex({ r: 0, g: 0, b: 0 })).toBe("#000000");
    expect(toHex({ r: 255, g: 255, b: 255 })).toBe("#ffffff");
    // Out of range values are clamped rather than producing "#10a-3ff".
    expect(toHex({ r: 300, g: -20, b: 128 })).toBe("#ff0080");
  });
});
