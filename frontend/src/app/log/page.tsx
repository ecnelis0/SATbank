import { MistakeForm } from "@/components/app/mistake-form";

export default function LogPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">Log a miss</h1>
      <p className="mt-1 mb-8 text-sm text-muted-foreground">
        The analysis runs as soon as you save. The first review lands an hour from now.
      </p>
      <MistakeForm />
    </div>
  );
}
