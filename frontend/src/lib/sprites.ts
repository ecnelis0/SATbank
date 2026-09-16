/** Cut the individual things out of a picture, and scatter them.
 *
 *  Tiling one photo across the page is wallpaper: you can see the seams and the
 *  repeat, and ten cats always arrive in the same clump. What actually reads as
 *  "cats everywhere" is ten *separate* cats at different sizes and angles.
 *
 *  Getting there is ordinary image processing, not a model. A cartoon, a sticker
 *  sheet or a cut-out sits on a flat background, so: guess the background from
 *  the border pixels, mark everything far enough from it as foreground, and let
 *  a flood fill find the separate blobs. Each blob is one sprite.
 *
 *  Photographs have no flat background and will segment into one enormous blob
 *  or none at all. That is expected and handled by the caller, which falls back
 *  to cropping the picture into pieces instead.
 */

export interface SpriteRegion {
  /** Bounding box in the working canvas, in pixels. */
  x: number;
  y: number;
  width: number;
  height: number;
  /** `width * height`, 1 where the blob is. Everything else is cut away, so a
   *  sprite has a transparent surround rather than a rectangle of background. */
  mask: Uint8Array;
  pixels: number;
}

interface SegmentOptions {
  maxSprites?: number;
  /** Ignore specks: a blob under this fraction of the picture is noise. */
  minFraction?: number;
  /** Ignore the whole picture arriving as one blob. */
  maxFraction?: number;
  /** How close to the border colour a pixel must be to seed the background. */
  tolerance?: number;
  /** How big a colour jump between neighbours ends the background. Small,
   *  because a gradient moves by a couple of levels per pixel and an object's
   *  edge moves by dozens. */
  localTolerance?: number;
}

function distance(
  r: number,
  g: number,
  b: number,
  to: { r: number; g: number; b: number },
): number {
  // Manhattan rather than Euclidean: same decision, no square root per pixel.
  return Math.abs(r - to.r) + Math.abs(g - to.g) + Math.abs(b - to.b);
}

/** The commonest colour around the edge, which is the background often enough. */
export function borderColour(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): { r: number; g: number; b: number } {
  const counts = new Map<number, { r: number; g: number; b: number; n: number }>();
  const add = (x: number, y: number) => {
    const i = (y * width + x) * 4;
    if (data[i + 3] < 125) return;
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
    const seen = counts.get(key);
    if (seen) {
      seen.r += r;
      seen.g += g;
      seen.b += b;
      seen.n += 1;
    } else {
      counts.set(key, { r, g, b, n: 1 });
    }
  };

  for (let x = 0; x < width; x += 1) {
    add(x, 0);
    add(x, height - 1);
  }
  for (let y = 0; y < height; y += 1) {
    add(0, y);
    add(width - 1, y);
  }

  let best = { r: 255, g: 255, b: 255, n: 0 };
  for (const entry of counts.values()) if (entry.n > best.n) best = entry;
  return { r: best.r / (best.n || 1), g: best.g / (best.n || 1), b: best.b / (best.n || 1) };
}

/** Flood-fill the picture into separate blobs, biggest first. */
export function segmentSprites(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  options: SegmentOptions = {},
): SpriteRegion[] {
  const {
    maxSprites = 14,
    minFraction = 0.0015,
    maxFraction = 0.45,
    tolerance = 60,
    localTolerance = 20,
  } = options;
  const area = width * height;
  if (area === 0) return [];

  const background = borderColour(data, width, height);

  // 1. Foreground mask, by flooding the background inward from the edge.
  //
  //    Not "far enough from the average border colour": that works on a flat
  //    background and falls apart on a gradient, where the far corner differs
  //    from the average by more than any threshold and whole slabs of sky come
  //    back as objects. Spreading from neighbour to neighbour instead asks
  //    "did the colour *jump* here", and a gradient never jumps.
  const isBackground = new Uint8Array(area);
  const queue: number[] = [];

  const seed = (index: number) => {
    if (isBackground[index]) return;
    const p = index * 4;
    if (data[p + 3] < 125) {
      isBackground[index] = 1;
      queue.push(index);
      return;
    }
    if (distance(data[p], data[p + 1], data[p + 2], background) <= tolerance) {
      isBackground[index] = 1;
      queue.push(index);
    }
  };

  for (let x = 0; x < width; x += 1) {
    seed(x);
    seed((height - 1) * width + x);
  }
  for (let y = 0; y < height; y += 1) {
    seed(y * width);
    seed(y * width + width - 1);
  }

  while (queue.length > 0) {
    const index = queue.pop()!;
    const x = index % width;
    const y = (index - x) / width;
    const p = index * 4;
    // 4-connected here on purpose: 8 lets the background squeeze diagonally
    // between two touching shapes and split one object into several.
    const neighbours = [
      x > 0 ? index - 1 : -1,
      x < width - 1 ? index + 1 : -1,
      y > 0 ? index - width : -1,
      y < height - 1 ? index + width : -1,
    ];
    for (const n of neighbours) {
      if (n < 0 || isBackground[n]) continue;
      const q = n * 4;
      if (data[q + 3] < 125) {
        isBackground[n] = 1;
        queue.push(n);
        continue;
      }
      const step = Math.abs(data[q] - data[p]) + Math.abs(data[q + 1] - data[p + 1]) +
        Math.abs(data[q + 2] - data[p + 2]);
      if (step <= localTolerance) {
        isBackground[n] = 1;
        queue.push(n);
      }
    }
  }

  const foreground = new Uint8Array(area);
  for (let i = 0; i < area; i += 1) {
    foreground[i] = isBackground[i] === 0 && data[i * 4 + 3] >= 125 ? 1 : 0;
  }

  // 2. Label connected runs. An explicit stack, not recursion: a big blob is
  //    tens of thousands of pixels deep and would blow the call stack.
  const labels = new Int32Array(area).fill(-1);
  const regions: Array<{ minX: number; minY: number; maxX: number; maxY: number; n: number }> = [];
  const stack: number[] = [];

  for (let start = 0; start < area; start += 1) {
    if (foreground[start] === 0 || labels[start] !== -1) continue;
    const id = regions.length;
    const region = {
      minX: width,
      minY: height,
      maxX: -1,
      maxY: -1,
      n: 0,
    };
    labels[start] = id;
    stack.push(start);

    while (stack.length > 0) {
      const index = stack.pop()!;
      const x = index % width;
      const y = (index - x) / width;
      region.n += 1;
      if (x < region.minX) region.minX = x;
      if (x > region.maxX) region.maxX = x;
      if (y < region.minY) region.minY = y;
      if (y > region.maxY) region.maxY = y;

      // 8-connected, so a diagonal whisker does not split a cat in two.
      for (let dy = -1; dy <= 1; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
          if (dx === 0 && dy === 0) continue;
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
          const n = ny * width + nx;
          if (foreground[n] === 1 && labels[n] === -1) {
            labels[n] = id;
            stack.push(n);
          }
        }
      }
    }
    regions.push(region);
  }

  // 3. Keep the blobs that are plausibly objects.
  const keep = regions
    .map((region, id) => ({ region, id }))
    .filter(
      ({ region }) =>
        region.n >= area * minFraction && region.n <= area * maxFraction && region.maxX >= 0,
    )
    .sort((a, b) => b.region.n - a.region.n)
    .slice(0, maxSprites);

  // 4. Cut each one out, carrying its mask so the surround is transparent.
  return keep.map(({ region, id }) => {
    const w = region.maxX - region.minX + 1;
    const h = region.maxY - region.minY + 1;
    const mask = new Uint8Array(w * h);
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const source = (region.minY + y) * width + (region.minX + x);
        if (labels[source] === id) mask[y * w + x] = 1;
      }
    }
    return { x: region.minX, y: region.minY, width: w, height: h, mask, pixels: region.n };
  });
}

// --- scattering ---------------------------------------------------------------

/** Small fast seeded RNG, so a layout is the same on every render and reload.
 *  Without it the sprites reshuffle on each keystroke-triggered re-render. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface Placement {
  sprite: number;
  /** Percentages of the viewport, so the layout reflows with the window. */
  left: number;
  top: number;
  /** Multiplier on the base size. */
  scale: number;
  rotate: number;
  opacity: number;
}

/** Lay `count` sprites over the page, evenly but not in rows.
 *
 *  A jittered grid rather than pure random placement: `Math.random()` twice per
 *  sprite clumps three in one corner and leaves the middle bare, which reads as
 *  a bug. One sprite per cell, offset randomly inside its own cell, covers the
 *  page evenly and still looks strewn.
 */
export function scatterLayout(
  spriteCount: number,
  { columns = 6, rows = 4, seed = 1 }: { columns?: number; rows?: number; seed?: number } = {},
): Placement[] {
  if (spriteCount <= 0) return [];
  const random = mulberry32(seed);
  const placements: Placement[] = [];

  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const cellWidth = 100 / columns;
      const cellHeight = 100 / rows;
      placements.push({
        // Cycle the sprites so all ten cats appear before any repeats.
        sprite: placements.length % spriteCount,
        left: column * cellWidth + random() * cellWidth * 0.82,
        top: row * cellHeight + random() * cellHeight * 0.82,
        // A few large, most small: uniform scaling looks like clip art.
        // Squared, so most are small and only a couple are big: uniform
        // scaling reads as clip art rather than as a scattering.
        scale: 0.5 + random() ** 2 * 1.15,
        rotate: (random() - 0.5) * 54,
        opacity: 0.55 + random() * 0.45,
      });
    }
  }

  // Shuffle which sprite lands in which cell, so the cycle is not readable as a
  // repeating diagonal across the page.
  for (let i = placements.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    const a = placements[i].sprite;
    placements[i].sprite = placements[j].sprite;
    placements[j].sprite = a;
  }

  return placements;
}
