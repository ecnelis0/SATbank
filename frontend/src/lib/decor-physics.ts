/** The physics behind the scattered cut-outs: drifting, bouncing, falling, and
 *  being thrown.
 *
 *  Kept as a pure step function over plain objects so the behaviour can be
 *  tested without a browser, a canvas or a frame loop. The React side owns the
 *  `requestAnimationFrame` loop and writes the results straight to the DOM; it
 *  never re-renders per frame, because twenty-four components re-rendering at
 *  60fps is how a decoration starts costing you scroll performance.
 */

export type DecorMode = "still" | "drift" | "bounce" | "gravity";

export interface Body {
  /** Centre position in CSS pixels. */
  x: number;
  y: number;
  /** Velocity in pixels per second. */
  vx: number;
  vy: number;
  rot: number;
  /** Spin in degrees per second. */
  vrot: number;
  /** Rendered width and height in pixels; used as the collision box. */
  size: number;
  /** Held by the pointer: physics leaves it alone until it is let go. */
  held?: boolean;
  /** Where it started, so "still" and "drift" have something to return to. */
  homeX: number;
  homeY: number;
  /** Phase offset, so drifting sprites do not bob in unison. */
  phase: number;
}

export interface World {
  width: number;
  height: number;
  mode: DecorMode;
  /** Seconds since the world started; drives the drift wobble. */
  time: number;
}

const GRAVITY = 1500; // px/s²
const AIR = 0.6; // per second, proportion of speed kept in gravity mode
const BOUNCE = 0.55;
const FLOOR_FRICTION = 0.82;
/** Below this, a body on the floor is asleep rather than jittering forever. */
const REST_SPEED = 26;

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/** Advance one body by `dt` seconds. Returns a new body; does not mutate. */
export function stepBody(body: Body, world: World, dt: number): Body {
  if (body.held) return body;

  const radius = body.size / 2;
  const minX = radius;
  const maxX = Math.max(radius, world.width - radius);
  const minY = radius;
  const maxY = Math.max(radius, world.height - radius);

  let { x, y, vx, vy, rot, vrot } = body;

  if (world.mode === "still" || world.mode === "drift") {
    // A thrown sprite still flies in these modes; it just eases back home
    // afterwards rather than falling or bouncing forever.
    const speed = Math.hypot(vx, vy);
    if (speed > 4) {
      x += vx * dt;
      y += vy * dt;
      rot += vrot * dt;
      const decay = 0.12 ** dt;
      vx *= decay;
      vy *= decay;
      vrot *= decay;
    } else {
      const wobble =
        world.mode === "drift" ? Math.sin(world.time * 0.7 + body.phase) * 9 : 0;
      // Ease home rather than snapping, so letting go looks like settling.
      const pull = 1 - 0.02 ** dt;
      x += (body.homeX - x) * pull;
      y += (body.homeY + wobble - y) * pull;
      vx = 0;
      vy = 0;
      rot += (body.rot - rot) * pull;
      vrot = 0;
    }
    return { ...body, x: clamp(x, minX, maxX), y: clamp(y, minY, maxY), vx, vy, rot, vrot };
  }

  if (world.mode === "gravity") vy += GRAVITY * dt;

  x += vx * dt;
  y += vy * dt;
  rot += vrot * dt;

  if (world.mode === "gravity") {
    const drag = AIR ** dt;
    vx *= drag;
    vrot *= drag;
  }

  // Walls. Reflect and damp, and put the body back inside rather than letting
  // it sit one pixel out and re-trigger the bounce every frame.
  if (x < minX) {
    x = minX;
    vx = Math.abs(vx) * (world.mode === "gravity" ? BOUNCE : 1);
    vrot = -vrot;
  } else if (x > maxX) {
    x = maxX;
    vx = -Math.abs(vx) * (world.mode === "gravity" ? BOUNCE : 1);
    vrot = -vrot;
  }

  if (y < minY) {
    y = minY;
    vy = Math.abs(vy) * (world.mode === "gravity" ? BOUNCE : 1);
  } else if (y > maxY) {
    y = maxY;
    if (world.mode === "gravity") {
      vy = -Math.abs(vy) * BOUNCE;
      vx *= FLOOR_FRICTION;
      vrot *= FLOOR_FRICTION;
      // Stop the endless micro-bouncing that otherwise leaves every sprite
      // buzzing against the floor forever.
      if (Math.abs(vy) < REST_SPEED) {
        vy = 0;
        if (Math.abs(vx) < REST_SPEED) {
          vx = 0;
          vrot = 0;
        }
      }
    } else {
      vy = -Math.abs(vy);
    }
  }

  return { ...body, x, y, vx, vy, rot, vrot };
}

export function step(bodies: Body[], world: World, dt: number): Body[] {
  // Clamped: a backgrounded tab hands back a dt of several seconds, and one
  // giant step teleports every sprite through a wall.
  const safe = Math.min(dt, 1 / 30);
  return bodies.map((body) => stepBody(body, world, safe));
}

/** Velocity from the last few pointer samples, in pixels per second.
 *
 *  Averaged over a short window rather than taken from the final two events:
 *  a pointer that stops dead for a moment before release would otherwise throw
 *  with whatever jitter the last event happened to carry. */
export function throwVelocity(
  samples: Array<{ x: number; y: number; t: number }>,
  window = 90,
): { vx: number; vy: number } {
  if (samples.length < 2) return { vx: 0, vy: 0 };
  const last = samples[samples.length - 1];

  // The oldest sample still *inside* the window. Walking past it — or stopping
  // on the first one outside — both end up measuring the whole gesture, which
  // turns a slow drag followed by a flick into a limp toss.
  let first = samples[samples.length - 2];
  for (let i = samples.length - 2; i >= 0; i -= 1) {
    if (last.t - samples[i].t > window) break;
    first = samples[i];
  }

  const dt = (last.t - first.t) / 1000;
  if (dt <= 0) return { vx: 0, vy: 0 };
  // Capped so a flick across a trackpad cannot fling a sprite at 40,000px/s.
  const cap = 4000;
  return {
    vx: clamp((last.x - first.x) / dt, -cap, cap),
    vy: clamp((last.y - first.y) / dt, -cap, cap),
  };
}
