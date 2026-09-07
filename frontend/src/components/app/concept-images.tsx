"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Gallery } from "@/components/app/gallery";
import { api, keys } from "@/lib/api";
import type { ConceptDetail } from "@/lib/types";

export function ConceptImages({
  concept,
  editable = false,
}: {
  concept: ConceptDetail;
  editable?: boolean;
}) {
  const queryClient = useQueryClient();

  const settle = (updated: ConceptDetail) => {
    queryClient.setQueryData(keys.concept(concept.id), updated);
    queryClient.invalidateQueries({ queryKey: keys.concepts() });
  };

  const upload = useMutation({
    mutationFn: (files: File[]) =>
      files.reduce<Promise<ConceptDetail>>(
        (previous, file) => previous.then(() => api.uploadConceptImage(concept.id, file)),
        Promise.resolve(concept),
      ),
    onSuccess: (updated) => {
      settle(updated);
      toast.success("Diagram added.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (imageId: string) => api.deleteConceptImage(concept.id, imageId),
    onSuccess: settle,
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Gallery
      images={concept.images}
      title="Diagrams"
      noun="Diagram"
      context="of the concept"
      addLabel="Add a diagram"
      editable={editable}
      uploading={upload.isPending}
      onUpload={(files) => upload.mutate(files)}
      onDelete={(imageId) => remove.mutate(imageId)}
      emptyText={
        editable
          ? "No diagrams yet. Drop a figure, a worked example, or a photo of the rule."
          : "No diagrams."
      }
    />
  );
}
