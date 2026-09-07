"use client";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** A native <select>, skinned to match the shadcn inputs.
 *
 *  Deliberately not the popup Select: a native control is reachable by keyboard
 *  everywhere, needs no portal, and can actually be driven in a component test. */
export function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
  className,
}: {
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <Label htmlFor={`field-${label}`}>{label}</Label>
      <select
        id={`field-${label}`}
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className={cn(
          "mt-1.5 h-8 w-full rounded-lg border border-border bg-background px-2 text-sm",
          "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none",
        )}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
