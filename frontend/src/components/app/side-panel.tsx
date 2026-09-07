"use client";

import { createContext, useContext, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SidePanelContext = createContext<{
  open: boolean;
  setOpen: (open: boolean) => void;
} | null>(null);

export function SidePanelProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <SidePanelContext value={{ open, setOpen }}>{children}</SidePanelContext>
  );
}

export function useSidePanel() {
  const context = useContext(SidePanelContext);
  if (!context) throw new Error("useSidePanel must be used inside SidePanelProvider");
  return context;
}

export function SidePanelToggle() {
  const { open, setOpen } = useSidePanel();

  return (
    <Button
      size="sm"
      variant={open ? "secondary" : "ghost"}
      aria-expanded={open}
      aria-controls="side-panel"
      onClick={() => setOpen(!open)}
    >
      {open ? "Close" : "Ask the bank"}
    </Button>
  );
}

/** Makes room for the rail on a wide screen instead of covering the page with it. */
export function MainArea({ children }: { children: React.ReactNode }) {
  const { open } = useSidePanel();

  return (
    <main
      className={cn(
        "mx-auto max-w-5xl px-4 py-8 transition-[margin] duration-200",
        open && "lg:mr-[26rem]",
      )}
    >
      {children}
    </main>
  );
}

/** The rail itself.
 *
 *  Fixed-position and always mounted when open, with no clip-path and no transform
 *  on a clipped child - the two ways a panel in this codebase has previously been
 *  laid out, opaque, and still invisible. */
export function SidePanel({ children }: { children: React.ReactNode }) {
  const { open, setOpen } = useSidePanel();

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-background/60 backdrop-blur-[1px] lg:hidden"
        onClick={() => setOpen(false)}
        aria-hidden
      />
      <aside
        id="side-panel"
        aria-label="Ask the bank"
        className={cn(
          "fixed top-14 right-0 bottom-0 z-50 w-full max-w-md border-l bg-background",
          "overflow-y-auto p-5 shadow-lg sm:w-[26rem]",
        )}
      >
        {children}
      </aside>
    </>
  );
}
