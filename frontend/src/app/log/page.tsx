import { MistakeForm } from "@/components/app/mistake-form";
import { PageHeader } from "@/components/app/page-header";

export default function LogPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader
        title="Log a miss"
      />
      <MistakeForm />
    </div>
  );
}
