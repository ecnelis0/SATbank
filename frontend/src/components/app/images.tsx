"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Gallery } from "@/components/app/gallery";
import { api, keys } from "@/lib/api";
import type { Mistake } from "@/lib/types";

export { imageSrc } from "@/components/app/gallery";

export function MistakeImages({
  mistake,
  editable = false,
}: {
  mistake: Mistake;
  editable?: boolean;
}) {
  const queryClient = useQueryClient();

  const settle = (updated: Mistake) => {
    queryClient.setQueryData(keys.mistake(mistake.id), updated);
    queryClient.invalidateQueries({ queryKey: ["mistakes"] });
  };

  const upload = useMutation({
    mutationFn: (files: File[]) =>
      // Sequential rather than parallel: each response carries the whole question,
      // and concurrent writes would race to decide the final image order.
      files.reduce<Promise<Mistake>>(
        (previous, file) => previous.then(() => api.uploadImage(mistake.id, file)),
        Promise.resolve(mistake),
      ),
    onSuccess: (updated) => {
      settle(updated);
      toast.success("Picture added.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (imageId: string) => api.deleteImage(mistake.id, imageId),
    onSuccess: settle,
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Gallery
      images={mistake.images}
      context="of the question"
      editable={editable}
      uploading={upload.isPending}
      onUpload={(files) => upload.mutate(files)}
      onDelete={(imageId) => remove.mutate(imageId)}
      emptyText={
        editable
          ? "No pictures yet. Drop a screenshot of the question, or a photo of your working."
          : "No pictures."
      }
    />
  );
}
