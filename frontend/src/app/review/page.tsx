import { PageHeader } from "@/components/app/page-header";
import { ReviewSession } from "@/components/app/review-session";

export default function ReviewPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-7">
      <PageHeader
        title="Review"
      />
      <ReviewSession />
    </div>
  );
}
