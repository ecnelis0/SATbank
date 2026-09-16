"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";

import { scatterLayout, segmentSprites, type SpriteRegion } from "@/lib/sprites";
import {
  buildTheme,
  extractPalette,
  toHex,
  THEMED_VARS,
  type Palette,
  type ThemeVars,
} from "@/lib/theme-from-image";

const STORAGE_KEY = "mistake-bank:page-theme";

/** Pixels the palette is read from. 64² is 4096 samples — plenty to find the
 *  colours in a photo, and small enough that the read is imperceptible. */
const SAMPLE_EDGE = 64;

/** Working size for cutting things out. Big enough that a cat keeps its ears,
 *  small enough that a flood fill over every pixel is imperceptible. */
const WORK_EDGE = 420;

/** Longest edge of any one sprite that gets stored. A dozen full-size cut-outs
 *  as PNG data URLs would blow the 5MB localStorage budget on their own. */
const SPRITE_EDGE = 150;

const DEFAULT_INTENSITY = 0.4;

export interface PageTheme {
  name: string;
  vars: ThemeVars;
  /** The things cut out of the picture, each with a transparent surround. */
  sprites: string[];
  /** Fixes the scatter, so it does not reshuffle on every render. */
  seed: number;
  swatches: string[];
}

interface Stored {
  theme: PageTheme | null;
  intensity: number;
}

const EMPTY: Stored = { theme: null, intensity: DEFAULT_INTENSITY };

// --- the stored theme, as an external store -----------------------------------
//
// localStorage rather than React state, read through `useSyncExternalStore`.
// The obvious version - `useState` plus a `useEffect` that reads storage on
// mount - sets state inside an effect, which cascades a second render and which
// the React Compiler rejects outright.

let cachedRaw: string | null = null;
let cachedValue: Stored = EMPTY;
const listeners = new Set<() => void>();

function readStore(): Stored {
  if (typeof window === "undefined") return EMPTY;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  // Memoised on the raw string: `useSyncExternalStore` re-renders forever if
  // the snapshot is a fresh object every call.
  if (raw === cachedRaw) return cachedValue;
  cachedRaw = raw;
  if (!raw) {
    cachedValue = EMPTY;
    return cachedValue;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<Stored>;
    cachedValue = {
      theme: parsed.theme ?? null,
      intensity: typeof parsed.intensity === "number" ? parsed.intensity : DEFAULT_INTENSITY,
    };
  } catch {
    // A corrupt entry must not take the app down with it.
    window.localStorage.removeItem(STORAGE_KEY);
    cachedRaw = null;
    cachedValue = EMPTY;
  }
  return cachedValue;
}

function writeStore(next: Stored) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Quota: the theme still applies for this session, it just will not persist.
  }
  cachedRaw = null;
  for (const listener of listeners) listener();
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  // Another tab theming the app themes this one too.
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

// --- reading a picture --------------------------------------------------------

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("That file could not be read as a picture."));
    };
    image.src = url;
  });
}

/** Draw the image into a canvas whose longest edge is `edge`. */
function draw(image: HTMLImageElement, edge: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  const ratio = image.width / image.height || 1;
  canvas.width = ratio >= 1 ? edge : Math.max(1, Math.round(edge * ratio));
  canvas.height = ratio >= 1 ? Math.max(1, Math.round(edge / ratio)) : edge;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("This browser would not give us a canvas to read.");
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas;
}

/** Crop one blob out of the working canvas, with everything that is not the blob
 *  turned transparent, scaled down, as a PNG data URL. */
function cutOut(source: ImageData, region: SpriteRegion): string {
  const cut = document.createElement("canvas");
  cut.width = region.width;
  cut.height = region.height;
  const context = cut.getContext("2d");
  if (!context) throw new Error("This browser would not give us a canvas to draw on.");

  const out = context.createImageData(region.width, region.height);
  for (let y = 0; y < region.height; y += 1) {
    for (let x = 0; x < region.width; x += 1) {
      const to = (y * region.width + x) * 4;
      const from = ((region.y + y) * source.width + (region.x + x)) * 4;
      out.data[to] = source.data[from];
      out.data[to + 1] = source.data[from + 1];
      out.data[to + 2] = source.data[from + 2];
      // The mask is the whole point: without it every sprite is a rectangle of
      // background with a cat in the middle, and the scatter looks like tiles.
      out.data[to + 3] = region.mask[y * region.width + x] ? source.data[from + 3] : 0;
    }
  }
  context.putImageData(out, 0, 0);

  const longest = Math.max(region.width, region.height);
  if (longest <= SPRITE_EDGE) return cut.toDataURL("image/png");

  const scaled = document.createElement("canvas");
  const ratio = SPRITE_EDGE / longest;
  scaled.width = Math.max(1, Math.round(region.width * ratio));
  scaled.height = Math.max(1, Math.round(region.height * ratio));
  const scaledContext = scaled.getContext("2d");
  if (!scaledContext) return cut.toDataURL("image/png");
  scaledContext.imageSmoothingQuality = "high";
  scaledContext.drawImage(cut, 0, 0, scaled.width, scaled.height);
  return scaled.toDataURL("image/png");
}

/** Slice the picture into pieces. The fallback for a photograph, which has no
 *  flat background to cut against and segments into one blob or none. */
function sliceUp(canvas: HTMLCanvasElement, across = 3, down = 3): string[] {
  const pieces: string[] = [];
  const w = Math.floor(canvas.width / across);
  const h = Math.floor(canvas.height / down);
  if (w < 8 || h < 8) return [canvas.toDataURL("image/jpeg", 0.75)];

  for (let row = 0; row < down; row += 1) {
    for (let column = 0; column < across; column += 1) {
      const piece = document.createElement("canvas");
      piece.width = Math.min(w, SPRITE_EDGE);
      piece.height = Math.min(h, SPRITE_EDGE);
      const context = piece.getContext("2d");
      if (!context) continue;
      context.drawImage(
        canvas,
        column * w,
        row * h,
        w,
        h,
        0,
        0,
        piece.width,
        piece.height,
      );
      pieces.push(piece.toDataURL("image/jpeg", 0.75));
    }
  }
  return pieces;
}

/** Inline custom properties on the root element beat the stylesheet's `:root`,
 *  so nothing in globals.css has to change and resetting is a clean removal. */
function applyVars(vars: ThemeVars) {
  const root = document.documentElement;
  for (const [name, value] of Object.entries(vars)) root.style.setProperty(name, value);
}

function clearVars() {
  const root = document.documentElement;
  // Only the ones this feature sets; anything else on the element is not ours.
  for (const name of THEMED_VARS) root.style.removeProperty(name);
}

// --- the provider -------------------------------------------------------------

interface PageThemeApi {
  theme: PageTheme | null;
  intensity: number;
  setIntensity: (value: number) => void;
  applyFile: (file: File) => Promise<void>;
  reset: () => void;
  busy: boolean;
}

const Context = createContext<PageThemeApi | null>(null);

export function usePageTheme(): PageThemeApi {
  const api = useContext(Context);
  if (!api) throw new Error("usePageTheme must be used inside PageThemeProvider");
  return api;
}

export function PageThemeProvider({ children }: { children: React.ReactNode }) {
  const stored = useSyncExternalStore(subscribe, readStore, () => EMPTY);
  const { theme, intensity } = stored;
  const [busy, setBusy] = useState(false);

  // Pushing the tokens at the DOM is exactly what an effect is for: syncing an
  // external system with React state, rather than deriving more state.
  useEffect(() => {
    if (theme) applyVars(theme.vars);
    else clearVars();
  }, [theme]);

  const applyFile = useCallback(
    async (file: File) => {
      setBusy(true);
      try {
        const image = await loadImage(file);

        const sample = draw(image, SAMPLE_EDGE);
        const sampleContext = sample.getContext("2d", { willReadFrequently: true });
        if (!sampleContext) throw new Error("This browser would not give us a canvas to read.");
        const palette: Palette = extractPalette(
          sampleContext.getImageData(0, 0, sample.width, sample.height).data,
        );

        // Cut the separate things out of the picture. Three is the bar for
        // "this segmented into objects" rather than "this is a photograph and
        // the whole frame came back as one blob".
        const work = draw(image, WORK_EDGE);
        const workContext = work.getContext("2d", { willReadFrequently: true });
        if (!workContext) throw new Error("This browser would not give us a canvas to read.");
        const source = workContext.getImageData(0, 0, work.width, work.height);
        const regions = segmentSprites(source.data, work.width, work.height);
        const sprites =
          regions.length >= 3 ? regions.map((region) => cutOut(source, region)) : sliceUp(work);

        writeStore({
          theme: {
            name: file.name.replace(/\.[^.]+$/, "").slice(0, 40) || "Your picture",
            vars: buildTheme(palette),
            sprites,
            seed: Math.floor(Math.random() * 2 ** 31),
            swatches: palette.swatches.map(toHex),
          },
          intensity,
        });
      } finally {
        setBusy(false);
      }
    },
    [intensity],
  );

  const reset = useCallback(() => writeStore({ theme: null, intensity }), [intensity]);

  const setIntensity = useCallback(
    (value: number) => writeStore({ theme, intensity: value }),
    [theme],
  );

  const api = useMemo(
    () => ({ theme, intensity, setIntensity, applyFile, reset, busy }),
    [theme, intensity, setIntensity, applyFile, reset, busy],
  );

  return <Context.Provider value={api}>{children}</Context.Provider>;
}

/** The things cut out of the picture, strewn across the page.
 *
 *  `fixed`, `aria-hidden` and `pointer-events-none`: it is decoration, so it
 *  must not scroll, must not be read aloud, and must never eat a click. The
 *  content above it carries `z-10`. */
export function PageDecor() {
  const { theme, intensity } = usePageTheme();

  // Same seed, same layout — including across a reload, which is what stops the
  // cats jumping to new places every time a page re-renders.
  const placements = useMemo(
    () => (theme ? scatterLayout(theme.sprites.length, { seed: theme.seed }) : []),
    [theme],
  );

  if (!theme || theme.sprites.length === 0) return null;

  return (
    <div
      aria-hidden
      data-testid="page-decor"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
      style={{ opacity: intensity }}
    >
      {placements.map((placement, index) => (
        // next/image has nothing to optimise here: these are base64 data URLs
        // generated in the browser and already scaled to 150px.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={index}
          src={theme.sprites[placement.sprite]}
          alt=""
          data-testid="decor-sprite"
          className="decor-float absolute"
          style={{
            left: `${placement.left}%`,
            top: `${placement.top}%`,
            width: `calc(clamp(2.5rem, 7vw, 6.5rem) * ${placement.scale})`,
            opacity: placement.opacity,
            // The independent `rotate` property, not `transform`: the drift
            // animation owns `translate`, and the two would overwrite each
            // other if both went through `transform`.
            rotate: `${placement.rotate}deg`,
            // Staggered so they drift independently rather than pulsing as one.
            animationDelay: `${(index % 7) * -1.9}s`,
            animationDuration: `${11 + (index % 5) * 2.5}s`,
          }}
        />
      ))}
    </div>
  );
}
