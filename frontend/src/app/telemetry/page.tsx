"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import {
  fetchClusterTelemetryHistory,
  type ClusterTelemetryHistory,
} from "@/services/api";
import { TelemetryTimeseriesChart } from "@/components/telemetry/TelemetryTimeseriesChart";
import { FarmActivityTable } from "@/components/telemetry/FarmActivityTable";
import { PageSkeleton } from "@/components/ui/SkeletonLoaders";

type TimeRange = "1h" | "24h" | "7d";

export default function TelemetryPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("1h");
  const [isManualRefreshing, setIsManualRefreshing] = useState<boolean>(false);
  const { mutate: globalMutate } = useSWRConfig();

  // Telemetry History SWR hook with keepPreviousData to prevent UI flickering
  const {
    data: telemetryData,
    isValidating: isTelemetryValidating,
    isLoading: isTelemetryLoading,
    mutate: mutateTelemetry,
  } = useSWR<ClusterTelemetryHistory>(
    ["/api/telemetry/cluster/history/", timeRange],
    () => fetchClusterTelemetryHistory(timeRange),
    {
      refreshInterval: 10000,
      keepPreviousData: true,
      revalidateOnFocus: true,
      dedupingInterval: 3000,
    }
  );

  const handleRefresh = async () => {
    setIsManualRefreshing(true);
    try {
      await Promise.all([
        mutateTelemetry(),
        globalMutate("/api/telemetry/events/?limit=100"),
      ]);
    } finally {
      setIsManualRefreshing(false);
    }
  };

  const isRefreshing = isTelemetryValidating || isManualRefreshing;

  if (isTelemetryLoading && !telemetryData) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground overflow-hidden">
      {/* 1. Standard Page Header matching other pages */}
      <PageHeader
        title="Telemetry & Logs"
        description="Cluster hardware utilization metrics and operational audit log history."
      >
        <Button
          variant="outline"
          onClick={() => void handleRefresh()}
          disabled={isRefreshing}
          className="gap-2"
        >
          <RefreshCw className={isRefreshing ? "animate-spin" : ""} size={14} />
          Refresh
        </Button>
      </PageHeader>

      {/* 2. Main Streamlined Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Hardware Timeseries Stream */}
        <TelemetryTimeseriesChart
          telemetryData={telemetryData}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          isLoading={isTelemetryLoading}
        />

        {/* Full-Width Operational Farm Activity Table matching Jobs Page */}
        <FarmActivityTable />
      </div>
    </div>
  );
}
