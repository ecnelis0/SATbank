"use client";

import { useState } from "react";

import { Ask } from "@/components/app/ask";
import { Categories } from "@/components/app/categories";
import { SidePanel } from "@/components/app/side-panel";
import { cn } from "@/lib/utils";

type Tab = "ask" | "categories";

export function Assistant() {
  const [tab, setTab] = useState<Tab>("ask");

  return (
    <SidePanel>
      <div
        role="tablist"
        aria-label="Side panel"
        className="mb-4 flex gap-1 rounded-lg bg-muted p-1"
      >
        {(
          [
            ["ask", "Ask"],
            ["categories", "Categories"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-sm transition-colors",
              tab === value
                ? "bg-background shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "ask" ? <Ask /> : <Categories />}
    </SidePanel>
  );
}
