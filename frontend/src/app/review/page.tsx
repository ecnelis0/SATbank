import { ReviewSession } from "@/components/app/review-session";

export default function ReviewPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Review</h1>
      <ReviewSession />
    </div>
  );
}
