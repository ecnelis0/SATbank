"use client";

import { toast } from "sonner";

import { ImageDropzone } from "@/components/app/image-dropzone";
import { usePageTheme } from "@/components/app/page-theme";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Drop a picture, and the whole app takes its colours and its wallpaper.
 *
 *  No API call: the palette comes out of the pixels in the browser, so this is
 *  instant, works with no key configured, and cannot fail on a network. */
export function ThemeStudio() {
  const { theme, intensity, setIntensity, mode, setMode, play, setPlay, applyFile, reset, busy } =
    usePageTheme();

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-lg">Dress the page</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Drop a picture. The bank takes its colours, cuts the separate things out of
          it, and strews them across the page at different sizes and angles. Drop ten
          cats and you get ten cats, not ten copies of the same square.
        </p>
      </div>

      <ImageDropzone
        disabled={busy}
        onFiles={async (files) => {
          try {
            await applyFile(files[0]);
          } catch (error) {
            toast.error(error instanceof Error ? error.message : "That picture would not read.");
          }
        }}
        label={busy ? "Reading the colours…" : "Drop a picture to theme the app"}
        inputLabel="Choose a picture to theme the app"
      />

      {theme ? (
        <>
          <div>
            <p className="text-sm font-medium">{theme.name}</p>
            <div className="mt-2 flex gap-1.5" aria-label="Colours taken from the picture">
              {theme.swatches.map((colour) => (
                <span
                  key={colour}
                  title={colour}
                  className="size-7 rounded-md border"
                  style={{ backgroundColor: colour }}
                />
              ))}
            </div>
          </div>

          <div>
            <Label htmlFor="decor-intensity">How loud</Label>
            <input
              id="decor-intensity"
              type="range"
              min={0}
              max={0.85}
              step={0.01}
              value={intensity}
              onChange={(event) => setIntensity(Number(event.target.value))}
              className="mt-2 w-full accent-primary"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              All the way down hides the cut-outs and keeps just the colours.
            </p>
          </div>

          <fieldset>
            <legend className="text-sm font-medium">How they move</legend>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {(
                [
                  ["still", "Stay put"],
                  ["drift", "Drift"],
                  ["bounce", "Bounce around"],
                  ["gravity", "Drop them"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={mode === value}
                  onClick={() => setMode(value)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-sm transition-colors",
                    mode === value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "hover:bg-muted",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="rounded-lg border p-3">
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                checked={play}
                onChange={(event) => setPlay(event.target.checked)}
                className="mt-0.5 size-4 accent-primary"
              />
              <span>
                <span className="font-medium">Let me grab them</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  Drag them anywhere, and fling them to throw. Off by default, because
                  while it is on the cut-outs take the click instead of the page
                  underneath.
                </span>
              </span>
            </label>
          </div>

          <Button type="button" variant="secondary" onClick={reset} className="w-full">
            Back to the original look
          </Button>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">
          Nothing applied — this is the bank&rsquo;s own palette. Whatever you drop is
          kept until you reset it, and survives a refresh.
        </p>
      )}
    </div>
  );
}
