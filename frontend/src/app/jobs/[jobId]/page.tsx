import { JobDetailView } from "./JobDetailView";

export function generateStaticParams() {
  return [{ jobId: "index" }];
}

export default function JobDetailPage() {
  return <JobDetailView />;
}
