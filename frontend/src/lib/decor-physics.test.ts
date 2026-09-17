import { describe, expect, it } from "vitest";

import { step, stepBody, throwVelocity, type Body, type World } from "@/lib/decor-physics";

function body(over: Partial<Body> = {}): Body {
  return {
    x: 500,
    y: 300,
    vx: 0,
    vy: 0,
    rot: 0,
    vrot: 0,
    size: 80,
    homeX: 500,
    homeY: 300,
    phase: 0,
    ...over,
  };
}

const world = (over: Partial<World> = {}): World => ({
  width: 1000,
  height: 600,
  mode: "bounce",
  time: 0,
  ...over,
});

/** Run the world forward for `seconds` at 60fps. */
function run(bodies: Body[], w: World, seconds: number): Body[] {
  let current = bodies;
  for (let i = 0; i < Math.round(seconds * 60); i += 1) current = step(current, w, 1 / 60);
  return current;
}

describe("gravity", () => {
  it("pulls things down and they land", () => {
    const [landed] = run([body({ y: 100 })], world({ mode: "gravity" }), 4);
    expect(landed.y).toBeCloseTo(600 - 40, 0);
  });

  it("comes to rest instead of buzzing on the floor forever", () => {
    const [resting] = run([body({ y: 100, vx: 200 })], world({ mode: "gravity" }), 12);
    expect(Math.abs(resting.vy)).toBe(0);
    expect(Math.abs(resting.vx)).toBe(0);
  });

  it("bounces lower each time rather than gaining energy", () => {
    let current = [body({ y: 100 })];
    const w = world({ mode: "gravity" });
    const peaks: number[] = [];
    let previousY = current[0].y;
    let rising = false;
    for (let i = 0; i < 60 * 8; i += 1) {
      current = step(current, w, 1 / 60);
      const nowRising = current[0].y < previousY;
      if (nowRising && !rising) rising = true;
      if (!nowRising && rising) {
        peaks.push(current[0].y);
        rising = false;
      }
      previousY = current[0].y;
    }
    expect(peaks.length).toBeGreaterThan(1);
    // Higher on screen is a *smaller* y, so each successive peak must be lower
    // down, i.e. a larger number.
    for (let i = 1; i < peaks.length; i += 1) {
      expect(peaks[i]).toBeGreaterThan(peaks[i - 1]);
    }
  });
});

describe("walls", () => {
  it("keeps everything on screen however hard it is thrown", () => {
    const thrown = [
      body({ vx: 4000, vy: 4000 }),
      body({ vx: -4000, vy: -4000 }),
      body({ x: 10, y: 10, vx: -9000, vy: -9000 }),
    ];
    for (const mode of ["bounce", "gravity", "drift", "still"] as const) {
      for (const result of run(thrown, world({ mode }), 6)) {
        expect(result.x).toBeGreaterThanOrEqual(result.size / 2 - 0.001);
        expect(result.x).toBeLessThanOrEqual(1000 - result.size / 2 + 0.001);
        expect(result.y).toBeGreaterThanOrEqual(result.size / 2 - 0.001);
        expect(result.y).toBeLessThanOrEqual(600 - result.size / 2 + 0.001);
      }
    }
  });

  it("reverses direction at a wall in bounce mode", () => {
    const [result] = run([body({ x: 900, vx: 600 })], world({ mode: "bounce" }), 1);
    expect(result.vx).toBeLessThan(0);
  });

  it("keeps its speed in bounce mode rather than dying out", () => {
    const [result] = run([body({ vx: 300, vy: 200 })], world({ mode: "bounce" }), 5);
    expect(Math.hypot(result.vx, result.vy)).toBeCloseTo(Math.hypot(300, 200), 0);
  });
});

describe("still and drift", () => {
  it("stays where it was put", () => {
    const [result] = run([body()], world({ mode: "still" }), 3);
    expect(result.x).toBeCloseTo(500, 0);
    expect(result.y).toBeCloseTo(300, 0);
  });

  it("returns home after being thrown", () => {
    const [result] = run([body({ vx: 900, vy: -400 })], world({ mode: "still" }), 8);
    expect(result.x).toBeCloseTo(500, 0);
    expect(result.y).toBeCloseTo(300, 0);
  });

  it("bobs around home in drift, without wandering off", () => {
    const seen: number[] = [];
    let current = [body()];
    for (let i = 0; i < 60 * 6; i += 1) {
      current = step(current, world({ mode: "drift", time: i / 60 }), 1 / 60);
      seen.push(current[0].y);
    }
    expect(Math.max(...seen) - Math.min(...seen)).toBeGreaterThan(2);
    for (const y of seen) expect(Math.abs(y - 300)).toBeLessThan(40);
  });
});

describe("being held", () => {
  it("is left exactly alone while the pointer has it", () => {
    const held = body({ held: true, x: 123, y: 456, vy: 999 });
    const after = stepBody(held, world({ mode: "gravity" }), 1 / 60);
    expect(after).toEqual(held);
  });
});

describe("a big timestep", () => {
  it("cannot teleport a sprite through a wall", () => {
    // What a backgrounded tab hands back on the first frame after it wakes.
    const [result] = step([body({ vx: 3000 })], world({ mode: "bounce" }), 5);
    expect(result.x).toBeLessThanOrEqual(1000 - result.size / 2 + 0.001);
  });
});

describe("throw velocity", () => {
  it("is the speed of the last part of the drag", () => {
    const { vx, vy } = throwVelocity([
      { x: 0, y: 0, t: 0 },
      { x: 50, y: 25, t: 50 },
      { x: 100, y: 50, t: 100 },
    ]);
    expect(vx).toBeCloseTo(1000, 0);
    expect(vy).toBeCloseTo(500, 0);
  });

  it("is zero for a tap that never moved", () => {
    expect(throwVelocity([{ x: 5, y: 5, t: 0 }])).toEqual({ vx: 0, vy: 0 });
    expect(throwVelocity([])).toEqual({ vx: 0, vy: 0 });
  });

  it("ignores where the drag started, so a slow drag then a flick still flicks", () => {
    const samples = [{ x: 0, y: 0, t: 0 }];
    for (let t = 1000; t <= 1080; t += 20) {
      samples.push({ x: (t - 1000) * 2, y: 0, t });
    }
    // Averaging over the whole gesture would give ~150px/s; the last 90ms is
    // what the hand actually did.
    expect(throwVelocity(samples).vx).toBeGreaterThan(1500);
  });

  it("caps a trackpad flick instead of launching into orbit", () => {
    const { vx } = throwVelocity([
      { x: 0, y: 0, t: 0 },
      { x: 4000, y: 0, t: 2 },
    ]);
    expect(vx).toBeLessThanOrEqual(4000);
  });

  it("does not divide by zero when two samples share a timestamp", () => {
    const { vx, vy } = throwVelocity([
      { x: 0, y: 0, t: 12 },
      { x: 90, y: 90, t: 12 },
    ]);
    expect(Number.isFinite(vx)).toBe(true);
    expect(Number.isFinite(vy)).toBe(true);
  });
});
