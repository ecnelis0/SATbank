"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { ImageDropzone } from "@/components/app/image-dropzone";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ScannedQuestion } from "@/lib/types";

/** Drop a Question Bank screenshot and have the form filled in from it.
 *
 *  Sits at the top of the form because it is the fast path: most questions are
 *  missed on a screen, and retyping a passage is the reason a miss never gets
 *  logged at all. The picture is handed back to the parent as well as read, so
 *  it ends up attached to the question rather than thrown away after the scan.
 */
export function ScanQuestion({
  onScanned,
  onKeepPicture,
  disabled = false,
}: {
  onScanned: (scanned: ScannedQuestion, file: File) => void;
  /** Attach the picture without a reading of it. */
  onKeepPicture?: (file: File) => void;
  disabled?: boolean;
}) {
  // Dropping a picture must do something useful with no AI at all. Whatever the
  // reader manages, the picture itself is kept and attached to the question, so
  // running out of usage costs you the typing it would have saved and nothing
  // else.
  const keep = (file: File, message: string) => {
    onKeepPicture?.(file);
    toast.info(onKeepPicture ? `${message} The picture is attached — type it in.` : message);
  };

  const scan = useMutation({
    mutationFn: async (file: File) => ({ scanned: await api.scanQuestion(file), file }),
    onSuccess: ({ scanned, file }) => {
      // An empty question means the reader saw nothing usable - the offline stub,
      // or a picture with no question in it. Filling the form with blanks would
      // look like a successful read, so say what happened instead.
      if (!scanned.question_text.trim()) {
        keep(file, scanned.note ?? "Nothing readable in that picture.");
        return;
      }
      onScanned(scanned, file);
      toast.success(
        scanned.answer_source === "worked"
          ? "Filled in. The page gave no answer, so that one is worked out — check it."
          : "Filled in. Check it, then say what you put.",
      );
    },
    onError: (error: Error, file: File) => keep(file, error.message),
  });

  if (scan.isPending) {
    return (
      <div
        role="status"
        className="flex items-center justify-center gap-3 rounded-lg border border-dashed bg-card/60 px-4 py-6 text-sm text-muted-foreground"
      >
        <span className="size-3 animate-pulse rounded-full bg-primary" />
        Reading the question…
      </div>
    );
  }

  if (scan.isSuccess && scan.data.scanned.question_text.trim()) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3">
        <p className="text-sm">
          Filled in from <span className="font-medium">{scan.data.file.name}</span>.
        </p>
        <Button type="button" variant="ghost" size="sm" onClick={() => scan.reset()}>
          Use a different picture
        </Button>
      </div>
    );
  }

  return (
    <ImageDropzone
      disabled={disabled}
      onFiles={(files) => scan.mutate(files[0])}
      // Neither label may contain "The question", "Add a picture" or the
      // pictures dropzone's own wording: `getByLabel` matches on substring, so
      // an overlap turns every existing query for those fields into a
      // strict-mode violation rather than a failure anyone can read.
      label="Drop a screenshot and the AI fills this in"
      inputLabel="Scan a screenshot"
    />
  );
}
