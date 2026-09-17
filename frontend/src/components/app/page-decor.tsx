"use client";

import { useEffect, useMemo, useRef } from "react";

import { usePageTheme } from "@/components/app/page-theme";
import { step, throwVelocity, type Body, type World } from "@/lib/decor-physics";
import { scatterLayout } from "@/lib/sprites";

/** Base size of a sprite before its own scale multiplier. */
const BASE = 76;

/** The cut-outs, strewn across the page — and draggable when play is on.
 *
 *  `aria-hidden` and, unless play is on, `pointer-events-none`: it is
 *  decoration, so it must not be read aloud and must never eat a click meant
 *  for the app. Turning play on is the one case where it *should* take the
 *  pointer, and that is a deliberate choice made in the Theme panel.
 */
export function PageDecor() {
  const { theme, intensity, mode, play } = usePageTheme();

  const layout = useMemo(
    () => (theme ? scatterLayout(theme.sprites.length, { seed: theme.seed }) : []),
    [theme],
  );

  const nodes = useRef<Array<HTMLImageElement | null>>([]);
  const bodies = useRef<Body[]>([]);
  const container = useRef<HTMLDivElement | null>(null);
  // Read by the frame loop, which is started once and would otherwise close over
  // whichever mode was current on the render that created it. Written in an
  // effect, not during render: a ref assignment mid-render is a torn read for
  // anything that reads it concurrently.
  const live = useRef({ mode, play });
  useEffect(() => {
    live.current = { mode, play };
  }, [mode, play]);

  // Seed the bodies from the layout whenever the picture or the window changes.
  useEffect(() => {
    if (layout.length === 0) return;
    const { innerWidth: w, innerHeight: h } = window;
    bodies.current = layout.map((placement, index) => {
      const size = BASE * placement.scale;
      const x = (placement.left / 100) * w + size / 2;
      const y = (placement.top / 100) * h + size / 2;
      return {
        x,
        y,
        vx: 0,
        vy: 0,
        rot: placement.rotate,
        vrot: 0,
        size,
        homeX: x,
        homeY: y,
        phase: index * 1.7,
      };
    });
  }, [layout]);

  useEffect(() => {
    if (layout.length === 0) return;

    let frame = 0;
    let previous = performance.now();
    let time = 0;

    const tick = (now: number) => {
      const dt = (now - previous) / 1000;
      previous = now;
      time += dt;

      const world: World = {
        width: window.innerWidth,
        height: window.innerHeight,
        mode: live.current.mode,
        time,
      };
      bodies.current = step(bodies.current, world, dt);

      for (let i = 0; i < bodies.current.length; i += 1) {
        const node = nodes.current[i];
        const body = bodies.current[i];
        if (!node || !body) continue;
        // Written straight to the DOM: re-rendering two dozen components every
        // frame is how a decoration starts costing real scroll performance.
        node.style.translate = `${body.x - body.size / 2}px ${body.y - body.size / 2}px`;
        node.style.rotate = `${body.rot}deg`;
      }
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [layout.length]);

  // Re-home everything when the window resizes, or a sprite ends up off screen.
  useEffect(() => {
    const onResize = () => {
      const { innerWidth: w, innerHeight: h } = window;
      bodies.current = bodies.current.map((body, index) => {
        const placement = layout[index];
        if (!placement) return body;
        const homeX = (placement.left / 100) * w + body.size / 2;
        const homeY = (placement.top / 100) * h + body.size / 2;
        return {
          ...body,
          homeX,
          homeY,
          x: Math.min(body.x, w - body.size / 2),
          y: Math.min(body.y, h - body.size / 2),
        };
      });
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [layout]);

  if (!theme || theme.sprites.length === 0) return null;

  const grab = (index: number) => (event: React.PointerEvent<HTMLImageElement>) => {
    if (!live.current.play) return;
    const body = bodies.current[index];
    if (!body) return;

    event.preventDefault();
    const node = event.currentTarget;
    node.setPointerCapture(event.pointerId);

    const samples: Array<{ x: number; y: number; t: number }> = [
      { x: event.clientX, y: event.clientY, t: performance.now() },
    ];
    // Grab it where it was actually clicked, so it does not jump to centre.
    const offsetX = body.x - event.clientX;
    const offsetY = body.y - event.clientY;
    bodies.current[index] = { ...body, held: true, vx: 0, vy: 0 };

    const move = (moveEvent: PointerEvent) => {
      const current = bodies.current[index];
      if (!current) return;
      bodies.current[index] = {
        ...current,
        x: moveEvent.clientX + offsetX,
        y: moveEvent.clientY + offsetY,
      };
      samples.push({ x: moveEvent.clientX, y: moveEvent.clientY, t: performance.now() });
      if (samples.length > 12) samples.shift();
    };

    const release = () => {
      node.removeEventListener("pointermove", move);
      node.removeEventListener("pointerup", release);
      node.removeEventListener("pointercancel", release);
      const current = bodies.current[index];
      if (!current) return;
      const { vx, vy } = throwVelocity(samples);
      bodies.current[index] = {
        ...current,
        held: false,
        vx,
        vy,
        // Spin proportional to how hard it was thrown sideways.
        vrot: Math.max(-720, Math.min(720, vx * 0.4)),
      };
    };

    node.addEventListener("pointermove", move);
    node.addEventListener("pointerup", release);
    node.addEventListener("pointercancel", release);
  };

  return (
    <div
      ref={container}
      aria-hidden
      data-testid="page-decor"
      data-play={play ? "on" : "off"}
      // Behind the app normally, in front of it while play is on. It has to be
      // in front to be grabbable at all: the content wrapper is a full-page
      // `z-10` div, so at `z-0` every pointerdown aimed at a cat landed on that
      // div instead and nothing was ever draggable. The layer itself keeps
      // `pointer-events: none` either way, so only the cut-outs take a click.
      className={play ? "fixed inset-0 z-50 overflow-hidden" : "fixed inset-0 z-0 overflow-hidden"}
      style={{ opacity: intensity, pointerEvents: "none" }}
    >
      {layout.map((placement, index) => (
        // next/image has nothing to optimise here: these are base64 data URLs
        // generated in the browser and already scaled to 150px.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={index}
          ref={(node) => {
            nodes.current[index] = node;
          }}
          src={theme.sprites[placement.sprite]}
          alt=""
          draggable={false}
          data-testid="decor-sprite"
          onPointerDown={grab(index)}
          className="absolute top-0 left-0 select-none"
          style={{
            width: `${BASE * placement.scale}px`,
            opacity: placement.opacity,
            // Only the sprites take the pointer, and only in play mode; the
            // layer itself stays transparent to clicks either way.
            pointerEvents: play ? "auto" : "none",
            cursor: play ? "grab" : undefined,
            touchAction: play ? "none" : undefined,
          }}
        />
      ))}
    </div>
  );
}
