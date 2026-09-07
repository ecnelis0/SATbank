"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";
import Lightbox from "yet-another-react-lightbox";
import Zoom from "yet-another-react-lightbox/plugins/zoom";

import { Button } from "@/components/ui/button";
import { API_URL, api, keys } from "@/lib/api";
import type { Mistake, MistakeImage } from "@/lib/types";

import "yet-another-react-lightbox/styles.css";

/** The API serves `/uploads/...`; the browser needs the API's own origin. */
export function imageSrc(image: MistakeImage): string {
  return image.url.startsWith("http") ? image.url : `${API_URL}${image.url}`;
}

export function MistakeImages({
  mistake,
  editable = false,
}: {
  mistake: Mistake;
  editable?: boolean;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  // null means closed. 0 is a valid index, so a plain falsy check would hide the
  // first image the moment you clicked it.
  const [zoomedAt, setZoomedAt] = useState<number | null>(null);

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
    onSettled: () => {
      // Let the same file be picked again after a failure.
      if (input.current) input.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: (imageId: string) => api.deleteImage(mistake.id, imageId),
    onSuccess: (updated) => {
      settle(updated);
      setZoomedAt(null);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const images = mistake.images;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-medium">Pictures</h2>
        {editable && (
          <>
            <input
              ref={input}
              type="file"
              accept="image/png,image/jpeg,image/gif,image/webp,image/heic"
              multiple
              className="sr-only"
              aria-label="Add a picture"
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (files.length > 0) upload.mutate(files);
              }}
            />
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              disabled={upload.isPending}
              onClick={() => input.current?.click()}
            >
              {upload.isPending ? "Uploading…" : "Add a picture"}
            </Button>
          </>
        )}
      </div>

      {images.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {editable
            ? "No pictures yet. Add a screenshot of the question, or a photo of your working."
            : "No pictures."}
        </p>
      ) : (
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {images.map((image, index) => (
            <li key={image.id} className="group relative">
              <button
                type="button"
                onClick={() => setZoomedAt(index)}
                aria-label={image.caption ?? `Open picture ${index + 1} full size`}
                className="block w-full overflow-hidden rounded-lg border transition-colors hover:border-foreground/30"
              >
                {/* Deliberately a plain <img>: these are user uploads served by the
                    API on another origin, which next/image would need configuring
                    for and would gain nothing from. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageSrc(image)}
                  alt={image.caption ?? `Picture ${index + 1} of the question`}
                  className="aspect-4/3 w-full object-cover"
                  loading="lazy"
                />
              </button>
              {editable && (
                <button
                  type="button"
                  aria-label={`Delete picture ${index + 1}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(image.id)}
                  className="absolute top-1.5 right-1.5 rounded-full bg-background/90 px-1.5 py-0.5 text-xs opacity-0 shadow transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <Lightbox
        open={zoomedAt !== null}
        index={zoomedAt ?? 0}
        close={() => setZoomedAt(null)}
        // Numbered rather than all sharing one name: the lightbox preloads the
        // neighbouring slides, so identical alt text makes them indistinguishable
        // to a screen reader and to a test.
        slides={images.map((image, index) => ({
          src: imageSrc(image),
          width: image.width ?? undefined,
          height: image.height ?? undefined,
          alt: image.caption ?? `Picture ${index + 1} of the question`,
        }))}
        plugins={[Zoom]}
        zoom={{ maxZoomPixelRatio: 5, scrollToZoom: true }}
        carousel={{ finite: true }}
        controller={{ closeOnBackdropClick: true }}
      />
    </div>
  );
}
