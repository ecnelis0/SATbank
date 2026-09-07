import Link from "next/link";

import { Button } from "@/components/ui/button";

export function Empty({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: { href: string; label: string };
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
    </div>
  );
}
