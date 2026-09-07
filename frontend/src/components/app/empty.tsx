import Link from "next/link";

import { Button } from "@/components/ui/button";

export function Empty({
  title,
  body,
  action,
  onAction,
}: {
  title: string;
  body: string;
  action?: { href: string; label: string };
  /** An empty state that acts on the page it is on, rather than linking away. */
  onAction?: { label: string; onClick: () => void };
}) {
  return (
    <div className="rounded-xl border border-dashed px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{body}</p>
      {action && (
        <Button render={<Link href={action.href} />} nativeButton={false} className="mt-5">
          {action.label}
        </Button>
      )}
      {onAction && (
        <Button className="mt-5" onClick={onAction.onClick}>
          {onAction.label}
        </Button>
      )}
    </div>
  );
}
