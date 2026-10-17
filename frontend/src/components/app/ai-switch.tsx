"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, keys } from "@/lib/api";
import type { ProviderId } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The two the student actually chooses between. The API-key Claude and "off"
 *  stay reachable from `./ai.sh`; offering four options in the nav for a choice
 *  that is really between two would make the common case harder to read. */
const SHOWN: ProviderId[] = ["agent", "openai"];

/** Which AI writes the debriefs, scans and answers. Takes effect on the next
 *  request; nothing restarts. */
export function AiSwitch() {
  const queryClient = useQueryClient();
  const { data: choice, isError } = useQuery({ queryKey: keys.ai(), queryFn: api.ai });

  const flip = useMutation({
    mutationFn: (provider: ProviderId) => api.switchAi(provider),
    onSuccess: (next) => {
      queryClient.setQueryData(keys.ai(), next);
      toast.success(`${next.label} is answering now.`);
      if (!next.ready) toast.warning(`${next.label} has no API key in .env yet.`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  // No switch rather than a wrong one: an unreachable API is said elsewhere.
  if (isError || !choice) return null;

  const options = choice.options.filter((option) => SHOWN.includes(option.id));

  return (
    <div
      role="radiogroup"
      aria-label="Which AI to use"
      className="flex items-center gap-0.5 rounded-lg border border-foreground/12 p-0.5"
    >
      {options.map((option) => {
        const on = option.id === choice.provider;
        return (
          <Button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={on}
            size="xs"
            variant={on ? "secondary" : "ghost"}
            title={option.description}
            disabled={flip.isPending}
            onClick={() => !on && flip.mutate(option.id)}
            className={cn(!on && "text-muted-foreground")}
          >
            {option.label}
            {on && !option.ready && (
              <span className="text-destructive" aria-label="not ready">
                !
              </span>
            )}
          </Button>
        );
      })}
    </div>
  );
}
