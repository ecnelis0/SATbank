"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { SidePanelToggle } from "@/components/app/side-panel";
import { api, keys } from "@/lib/api";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/log", label: "Log a miss" },
  { href: "/bank", label: "The bank" },
  { href: "/review", label: "Review" },
];

export function Nav() {
  const pathname = usePathname();
  const { data: stats } = useQuery({
    queryKey: keys.stats(),
    queryFn: api.stats,
    refetchInterval: 60_000,
  });
  const due = stats?.due_now ?? 0;

  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-5xl items-center gap-1 px-4">
        <Link href="/" className="mr-4 font-semibold tracking-tight">
          Mistake<span className="text-muted-foreground">Bank</span>
        </Link>

        {LINKS.map((link) => {
          const active =
            link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {link.label}
              {link.href === "/review" && due > 0 && (
                <span
                  className="ml-1.5 rounded-full bg-primary px-1.5 py-0.5 text-[11px] font-medium text-primary-foreground"
                  aria-label={`${due} due now`}
                >
                  {due}
                </span>
              )}
            </Link>
          );
        })}

        <div className="ml-auto">
          <SidePanelToggle />
        </div>
      </nav>
    </header>
  );
}
