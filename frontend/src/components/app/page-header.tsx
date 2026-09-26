import type { ReactNode } from "react";

/** Every page opens the way the scroll does: a cinnabar seal, the title in the
 *  display serif beside it, and a brushed ink rule under the pair. Consistency
 *  here is most of what makes a set of screens feel like one product — and the
 *  seal is what makes them feel like one painting.
 *
 *  The seal carries the page's initial. It is decoration, so it is hidden from
 *  the accessibility tree: the h1 already says where you are, and a screen
 *  reader announcing a bare letter first would only be noise. */
export function PageHeader({
  title,
  actions,
}: {
  title: string;
  actions?: ReactNode;
}) {
  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span aria-hidden data-slot="seal">
            {title.trim().charAt(0).toUpperCase()}
          </span>
          <h1 className="font-[family-name:var(--font-display)] text-[2.1rem] leading-[1.08] font-semibold tracking-[-0.022em]">
            {title}
          </h1>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
      <hr data-slot="ink-rule" aria-hidden />
    </header>
  );
}
