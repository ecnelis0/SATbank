"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { TagPicker } from "@/components/app/tag-picker";
import { api, keys } from "@/lib/api";
import type { Mistake } from "@/lib/types";

/** Your labels on a question you have already logged.
 *
 *  The same picker as the log form, so a label added later is the same act as a
 *  label added at the time - and reuses the ones you already have rather than
 *  making you retype them into a comma-separated box. */
export function MistakeLabels({
  mistake,
  editable = false,
}: {
  mistake: Mistake;
  editable?: boolean;
}) {
  const queryClient = useQueryClient();

  const save = useMutation({
    mutationFn: (tags: string[]) => api.updateMistake(mistake.id, { tags }),
    onSuccess: (updated) => {
      queryClient.setQueryData(keys.mistake(mistake.id), updated);
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      // A new label has to show up in the picker's suggestions straight away.
      queryClient.invalidateQueries({ queryKey: keys.tags() });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const tags = mistake.tags ?? [];

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium">Your labels</h2>

      {editable ? (
        <TagPicker
          selected={tags}
          onChange={(next) => save.mutate(next)}
          disabled={save.isPending}
        />
      ) : tags.length === 0 ? (
        <p className="text-sm text-muted-foreground">No labels.</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <li
              key={tag}
              className="rounded-full border bg-muted/50 px-2.5 py-0.5 text-xs"
            >
              {tag}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
