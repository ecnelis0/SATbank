"use client";

import { useDropzone } from "react-dropzone";

import { cn } from "@/lib/utils";

export const IMAGE_TYPES = {
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/gif": [".gif"],
  "image/webp": [".webp"],
  "image/heic": [".heic"],
};

/** Drop files here, or click to browse.
 *
 *  react-dropzone rather than hand-rolled: the drag-leave flicker as the pointer
 *  crosses a child element, the keyboard path, and the type filtering are all
 *  edge cases someone has already got right. */
export function ImageDropzone({
  onFiles,
  disabled = false,
  label = "Drag pictures here, or click to choose",
  inputLabel = "Add a picture",
  className,
}: {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  label?: string;
  /** The hidden file input's accessible name - the handle for keyboard users and
   *  for anything driving the page. react-dropzone hides the input itself. */
  inputLabel?: string;
  className?: string;
}) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: IMAGE_TYPES,
    disabled,
    onDrop: (accepted) => {
      if (accepted.length > 0) onFiles(accepted);
    },
  });

  return (
    <div
      {...getRootProps()}
      aria-label={label}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-6 text-center transition-colors",
        isDragActive ? "border-primary bg-primary/5" : "hover:bg-muted/50",
        disabled && "pointer-events-none opacity-50",
        className,
      )}
    >
      <input {...getInputProps({ "aria-label": inputLabel })} />
      <p className="text-sm text-muted-foreground">
        {isDragActive ? "Drop them here" : label}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        PNG, JPEG, GIF, WebP or HEIC · up to 10MB each
      </p>
    </div>
  );
}
