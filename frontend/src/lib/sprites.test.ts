import { describe, expect, it } from "vitest";

import {
  borderColour,
  mulberry32,
  scatterLayout,
  segmentSprites,
} from "@/lib/sprites";

/** A blank canvas of `bg`, with rectangles painted on it. */
function picture(
  width: number,
  height: number,
  bg: [number, number, number],
  blobs: Array<{ x: number; y: number; w: number; h: number; colour: [number, number, number] }>,
) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i += 1) {
    data[i * 4] = bg[0];
    data[i * 4 + 1] = bg[1];
    data[i * 4 + 2] = bg[2];
    data[i * 4 + 3] = 255;
  }
  for (const blob of blobs) {
    for (let y = blob.y; y < blob.y + blob.h; y += 1) {
      for (let x = blob.x; x < blob.x + blob.w; x += 1) {
        const i = (y * width + x) * 4;
        data[i] = blob.colour[0];
        data[i + 1] = blob.colour[1];
        data[i + 2] = blob.colour[2];
        data[i + 3] = 255;
      }
    }
  }
  return data;
}

describe("finding the background", () => {
  it("takes the colour around the edge, not the thing in the middle", () => {
    const data = picture(40, 40, [250, 248, 240], [
      { x: 10, y: 10, w: 20, h: 20, colour: [10, 10, 10] },
    ]);
    const bg = borderColour(data, 40, 40);
    expect(bg.r).toBeGreaterThan(200);
    expect(bg.g).toBeGreaterThan(200);
  });
});

describe("cutting things out", () => {
  it("finds each separate shape, and not the background", () => {
    const data = picture(60, 60, [255, 255, 255], [
      { x: 4, y: 4, w: 12, h: 12, colour: [220, 40, 40] },
      { x: 40, y: 6, w: 14, h: 10, colour: [40, 80, 220] },
      { x: 20, y: 38, w: 16, h: 16, colour: [30, 180, 90] },
    ]);
    const sprites = segmentSprites(data, 60, 60);

    expect(sprites).toHaveLength(3);
    // Biggest first: the 16×16 square.
    expect(sprites[0].width).toBe(16);
    expect(sprites[0].height).toBe(16);
    // Bounding boxes sit exactly on the shapes.
    const boxes = sprites.map((s) => `${s.x},${s.y},${s.width},${s.height}`).sort();
    expect(boxes).toEqual(["20,38,16,16", "4,4,12,12", "40,6,14,10"].sort());
  });

  it("keeps two touching shapes together and two apart separate", () => {
    const touching = picture(60, 60, [255, 255, 255], [
      { x: 10, y: 10, w: 10, h: 10, colour: [200, 0, 0] },
      { x: 20, y: 10, w: 10, h: 10, colour: [0, 0, 200] },
    ]);
    expect(segmentSprites(touching, 60, 60)).toHaveLength(1);

    const apart = picture(60, 60, [255, 255, 255], [
      { x: 10, y: 10, w: 10, h: 10, colour: [200, 0, 0] },
      { x: 34, y: 10, w: 10, h: 10, colour: [0, 0, 200] },
    ]);
    expect(segmentSprites(apart, 60, 60)).toHaveLength(2);
  });

  it("masks the surround so a sprite is the shape, not its bounding box", () => {
    // An L, so the bounding box has a corner that is not part of the shape.
    const data = picture(40, 40, [255, 255, 255], [
      { x: 8, y: 8, w: 6, h: 18, colour: [30, 30, 30] },
      { x: 8, y: 20, w: 18, h: 6, colour: [30, 30, 30] },
    ]);
    const [sprite] = segmentSprites(data, 40, 40);
    expect(sprite.width).toBe(18);
    expect(sprite.height).toBe(18);
    // Top-left is on the upright of the L; top-right is empty.
    expect(sprite.mask[0]).toBe(1);
    expect(sprite.mask[sprite.width - 1]).toBe(0);
    expect(sprite.pixels).toBeLessThan(sprite.width * sprite.height);
  });

  it("does not mistake a gradient background for objects", () => {
    // The bug this replaced: the border colour averages to the middle of the
    // gradient, so both ends of it sat further away than the threshold and came
    // back as big salmon-coloured blobs scattered over the page.
    const width = 80;
    const height = 80;
    const data = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const i = (y * width + x) * 4;
        const t = (x + y) / (width + height);
        data[i] = 232 - t * 110;
        data[i + 1] = 133 - t * 80;
        data[i + 2] = 58 - t * 42;
        data[i + 3] = 255;
      }
    }
    // Two obvious shapes sitting on the gradient.
    for (const blob of [
      { x: 10, y: 12, w: 14, h: 14 },
      { x: 50, y: 48, w: 16, h: 12 },
    ]) {
      for (let y = blob.y; y < blob.y + blob.h; y += 1) {
        for (let x = blob.x; x < blob.x + blob.w; x += 1) {
          const i = (y * width + x) * 4;
          data[i] = 250;
          data[i + 1] = 220;
          data[i + 2] = 60;
        }
      }
    }

    const sprites = segmentSprites(data, width, height);
    expect(sprites).toHaveLength(2);
    expect(sprites.map((s) => `${s.width}x${s.height}`).sort()).toEqual(["14x14", "16x12"]);
  });

  it("throws away specks", () => {
    const data = picture(60, 60, [255, 255, 255], [
      { x: 5, y: 5, w: 20, h: 20, colour: [10, 10, 10] },
      { x: 50, y: 50, w: 1, h: 1, colour: [10, 10, 10] },
    ]);
    expect(segmentSprites(data, 60, 60)).toHaveLength(1);
  });

  it("returns nothing for a picture with no flat background, so the caller can slice instead", () => {
    // A gradient: every pixel differs from its neighbour, and the whole frame is
    // one connected blob well over the size ceiling.
    const width = 60;
    const height = 60;
    const data = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < width * height; i += 1) {
      data[i * 4] = (i % width) * 4;
      data[i * 4 + 1] = 60;
      data[i * 4 + 2] = 200 - (i % width) * 3;
      data[i * 4 + 3] = 255;
    }
    expect(segmentSprites(data, width, height).length).toBeLessThan(3);
  });

  it("caps how many it returns", () => {
    const blobs = [];
    for (let row = 0; row < 6; row += 1) {
      for (let column = 0; column < 6; column += 1) {
        blobs.push({ x: column * 10 + 2, y: row * 10 + 2, w: 6, h: 6, colour: [0, 0, 0] as [number, number, number] });
      }
    }
    const data = picture(60, 60, [255, 255, 255], blobs);
    expect(segmentSprites(data, 60, 60, { maxSprites: 8 })).toHaveLength(8);
  });

  it("does not fall over on an empty picture", () => {
    expect(segmentSprites(new Uint8ClampedArray([]), 0, 0)).toEqual([]);
  });
});

describe("scattering", () => {
  it("is the same every time for the same seed, and different for another", () => {
    expect(scatterLayout(5, { seed: 42 })).toEqual(scatterLayout(5, { seed: 42 }));
    expect(scatterLayout(5, { seed: 42 })).not.toEqual(scatterLayout(5, { seed: 43 }));
  });

  it("stays on the page", () => {
    for (const placement of scatterLayout(6, { seed: 7 })) {
      expect(placement.left).toBeGreaterThanOrEqual(0);
      expect(placement.left).toBeLessThan(100);
      expect(placement.top).toBeGreaterThanOrEqual(0);
      expect(placement.top).toBeLessThan(100);
      expect(placement.opacity).toBeGreaterThan(0);
      expect(placement.opacity).toBeLessThanOrEqual(1);
    }
  });

  it("covers the page instead of clumping in one corner", () => {
    // The reason for a jittered grid rather than two calls to random(): every
    // quadrant has to get something.
    const placements = scatterLayout(8, { seed: 3, columns: 6, rows: 4 });
    const quadrant = (p: { left: number; top: number }) =>
      `${p.left < 50 ? "L" : "R"}${p.top < 50 ? "T" : "B"}`;
    const seen = new Set(placements.map(quadrant));
    expect(seen.size).toBe(4);
  });

  it("uses every sprite before repeating any", () => {
    const placements = scatterLayout(10, { seed: 11, columns: 5, rows: 2 });
    expect(new Set(placements.map((p) => p.sprite)).size).toBe(10);
  });

  it("varies size and angle, so it does not read as a grid", () => {
    const placements = scatterLayout(6, { seed: 5 });
    expect(new Set(placements.map((p) => p.scale.toFixed(3))).size).toBeGreaterThan(5);
    expect(placements.some((p) => p.rotate < -4)).toBe(true);
    expect(placements.some((p) => p.rotate > 4)).toBe(true);
  });

  it("returns nothing when there are no sprites", () => {
    expect(scatterLayout(0)).toEqual([]);
  });

  it("has a usable random generator", () => {
    const random = mulberry32(1);
    const values = Array.from({ length: 500 }, random);
    expect(Math.min(...values)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...values)).toBeLessThan(1);
    // Roughly uniform, not stuck in one part of the range.
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    expect(mean).toBeGreaterThan(0.4);
    expect(mean).toBeLessThan(0.6);
  });
});
