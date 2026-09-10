import { PageHeader } from "@/components/app/page-header";
import { ReviewSession } from "@/components/app/review-session";

export default function ReviewPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-7">
      <PageHeader
        title="Review"
        lede="Answer it in your head, then check. Getting it wrong sends it back to the start of the ladder."
      />
      <ReviewSession />
    </div>
  );
}
