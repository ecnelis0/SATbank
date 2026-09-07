"use client";

import { useEffect, useState } from "react";

import { ImageDropzone } from "@/components/app/image-dropzone";

/** A picture chosen before the question exists, held with its preview URL. */
export interface PendingImage {
  id: string;
  file: File;
  preview: string;
}

export function usePendingImages() {
  const [images, setImages] = useState<PendingImage[]>([]);

  // Object URLs are a document-lifetime leak until revoked; do it on unmount too,
  // not only when a picture is removed by hand.
  useEffect(() => {
    return () => {
      for (const image of images) URL.revokeObjectURL(image.preview);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const add = (files: File[]) =>
    setImages((current) => [
      ...current,
      ...files.map((file) => ({
        id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        preview: URL.createObjectURL(file),
      })),
    ]);

  const remove = (id: string) =>
    setImages((current) => {
      const going = current.find((image) => image.id === id);
      if (going) URL.revokeObjectURL(going.preview);
      return current.filter((image) => image.id !== id);
    });

  const clear = () =>
    setImages((current) => {
      for (const image of current) URL.revokeObjectURL(image.preview);
      return [];
    });

  return { images, add, remove, clear };
}

export function PendingImages({
  images,
  onAdd,
  onRemove,
  disabled = false,
}: {
  images: PendingImage[];
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-3">
      <ImageDropzone
        onFiles={onAdd}
        disabled={disabled}
        label="Drag a screenshot here, or click to choose"
      />

      {images.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {images.map((image, index) => (
            <li key={image.id} className="group relative">
              {/* Object URL of a file the user just chose; next/image has nothing
                  to optimise here and cannot resolve a blob: URL anyway. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={image.preview}
                alt={`Picture ${index + 1} to upload`}
                className="aspect-4/3 w-full rounded-lg border object-cover"
              />
              <button
                type="button"
                aria-label={`Remove picture ${index + 1}`}
                disabled={disabled}
                onClick={() => onRemove(image.id)}
                className="absolute top-1 right-1 rounded-full bg-background/90 px-1.5 py-0.5 text-xs shadow transition-opacity focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
