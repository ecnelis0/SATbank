"use client";

import { useState } from "react";
import Lightbox from "yet-another-react-lightbox";
import Zoom from "yet-another-react-lightbox/plugins/zoom";

import { ImageDropzone } from "@/components/app/image-dropzone";
import { API_URL } from "@/lib/api";
import type { MistakeImage } from "@/lib/types";

import "yet-another-react-lightbox/styles.css";

/** The API serves `/uploads/...`; the browser needs the API's own origin. */
export function imageSrc(image: MistakeImage): string {
  return image.url.startsWith("http") ? image.url : `${API_URL}${image.url}`;
}

/** Pictures, zoomable, optionally editable. Used by questions and by concepts -
 *  the two differ only in which endpoint the parent's handlers call. */
export function Gallery({
  images,
  title = "Pictures",
  noun = "Picture",
  context = "",
  addLabel = "Add a picture",
  editable = false,
  uploading = false,
  onUpload,
  onDelete,
  emptyText,
}: {
  images: MistakeImage[];
  title?: string;
  /** "Picture" or "Diagram" - the accessible name every control is built from. */
  noun?: string;
  /** "of the question" / "of the concept", so a screen reader knows which. */
  context?: string;
  addLabel?: string;
  editable?: boolean;
  uploading?: boolean;
  onUpload?: (files: File[]) => void;
  onDelete?: (imageId: string) => void;
  emptyText?: string;
}) {
  // Controls are named without the context - "Open picture 1 full size" reads
  // better than "Open picture 1 of the question full size", and the section heading
  // already says which. The context goes on the alt text, where it is the only
  // thing telling a screen reader what it is looking at.
  const control = (index: number) => `${noun} ${index + 1}`;
  const alt = (index: number) =>
    `${noun} ${index + 1}${context ? ` ${context}` : ""}`;
  // null means closed. 0 is a valid index, so a falsy check would hide the first
  // picture the moment you clicked it.
  const [zoomedAt, setZoomedAt] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium">{title}</h2>

      {editable && onUpload && (
        <ImageDropzone
          onFiles={onUpload}
          disabled={uploading}
          label={uploading ? "Uploading…" : "Drag pictures here, or click to choose"}
          inputLabel={addLabel}
        />
      )}

      {images.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {emptyText ?? (editable ? "Nothing here yet." : "No pictures.")}
        </p>
      ) : (
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {images.map((image, index) => (
            <li key={image.id} className="group relative">
              <button
                type="button"
                onClick={() => setZoomedAt(index)}
                aria-label={image.caption ?? `Open ${control(index).toLowerCase()} full size`}
                className="block w-full overflow-hidden rounded-lg border transition-colors hover:border-foreground/30"
              >
                {/* A plain <img>: these are user uploads served by the API on another
                    origin, which next/image would need configuring for and would gain
                    nothing from. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageSrc(image)}
                  alt={image.caption ?? alt(index)}
                  className="aspect-4/3 w-full object-cover"
                  loading="lazy"
                />
              </button>
              {editable && onDelete && (
                <button
                  type="button"
                  aria-label={`Delete ${control(index).toLowerCase()}`}
                  onClick={() => onDelete(image.id)}
                  className="absolute top-1.5 right-1.5 rounded-full bg-background/90 px-1.5 py-0.5 text-xs shadow transition-opacity focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
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
          alt: image.caption ?? alt(index),
        }))}
        plugins={[Zoom]}
        zoom={{ maxZoomPixelRatio: 5, scrollToZoom: true }}
        carousel={{ finite: true }}
        controller={{ closeOnBackdropClick: true }}
      />
    </div>
  );
}
