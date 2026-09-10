import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A titled block. The eyebrow is small, spaced and quiet — it labels the content
 *  without competing with it, which a same-size bold heading always does. */
export function Section({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="space-y-1">
          <h2 className="text-[11px] font-medium tracking-[0.09em] text-muted-foreground uppercase">
            {title}
          </h2>
          {description && (
            <p className="max-w-2xl text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
