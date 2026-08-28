import { LayerDetailView } from "./LayerDetailView";

export function generateStaticParams() {
  return [{ jobId: "index", layerId: "index" }];
}

export default function LayerInspectorPage() {
  return <LayerDetailView />;
}
