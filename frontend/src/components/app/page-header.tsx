import type { ReactNode } from "react";

/** Every page opens the same way: a display-serif title and any actions pushed
 *  to the right. Consistency here is most of what makes a set of screens feel
 *  like one product. */
export function PageHeader({
  title,
  actions,
}: {
  title: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-[family-name:var(--font-display)] text-[2.1rem] leading-[1.08] font-semibold tracking-[-0.022em]">
          {title}
        </h1>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}
