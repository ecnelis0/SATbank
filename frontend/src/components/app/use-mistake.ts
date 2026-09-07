"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, keys } from "@/lib/api";
import type { Mistake, MistakeEdit } from "@/lib/types";

/** Every write to a mistake lands here, so the caches it affects stay in step. */
function useMistakeWrite(id: string) {
  const queryClient = useQueryClient();

  return (updated: Mistake) => {
    queryClient.setQueryData(keys.mistake(id), updated);
    queryClient.invalidateQueries({ queryKey: ["mistakes"] });
    queryClient.invalidateQueries({ queryKey: ["reviews"] });
    queryClient.invalidateQueries({ queryKey: keys.stats() });
  };
}

export function useUpdateMistake(id: string, onDone?: () => void) {
  const settle = useMistakeWrite(id);

  return useMutation({
    mutationFn: (edit: MistakeEdit) => api.updateMistake(id, edit),
    onSuccess: (updated) => {
      settle(updated);
      toast.success("Saved.");
      onDone?.();
    },
    onError: (error: Error) => toast.error(error.message),
  });
}

export function useAnalyzeMistake(id: string) {
  const settle = useMistakeWrite(id);

  return useMutation({
    mutationFn: (force: boolean = false) => api.analyze(id, force),
    onSuccess: (updated) => {
      settle(updated);
      if (updated.analysis_status === "ready") toast.success("Debriefed.");
      else toast.error("The analysis did not come back.");
    },
    onError: (error: Error) => toast.error(error.message),
  });
}
