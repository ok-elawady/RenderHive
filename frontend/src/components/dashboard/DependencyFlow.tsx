import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Dependency } from "@/services/api";

function shortenUuid(uuid: string | null | undefined): string {
  if (!uuid) return "";
  return uuid.split("-")[0];
}

interface DependencyFlowProps {
  dep: Dependency;
  currentJobId: string;
  isInbound: boolean;
}

export function DependencyFlow({ dep, currentJobId, isInbound }: DependencyFlowProps) {
  const isInternal = dep.parent_job === dep.dep_job;

  const formatEntity = (
    jobId: string,
    jobName: string | undefined,
    layerId: string | null | undefined,
    layerName: string | null | undefined,
    taskId: string | null | undefined,
    taskName: string | null | undefined,
    isCurrentJob: boolean
  ) => {
    const jName = jobName || shortenUuid(jobId);
    if (taskId) {
      const tName = taskName || shortenUuid(taskId);
      return isCurrentJob ? tName : `${jName} / ${tName}`;
    }
    if (layerId) {
      const lName = layerName || shortenUuid(layerId);
      return isCurrentJob ? lName : `${jName} / ${lName}`;
    }
    return isCurrentJob ? "Entire Job" : jName;
  };

  const blockingEntity = formatEntity(
    dep.parent_job,
    dep.parent_job_name,
    dep.parent_layer,
    dep.parent_layer_name,
    dep.parent_task,
    dep.parent_task_name,
    dep.parent_job === currentJobId
  );
  
  const blockedEntity = formatEntity(
    dep.dep_job,
    dep.dep_job_name,
    dep.dep_layer,
    dep.dep_layer_name,
    dep.dep_task,
    dep.dep_task_name,
    dep.dep_job === currentJobId
  );

  return (
    <div className="flex items-center gap-2 text-xs">
      {isInternal && (
        <Badge variant="secondary" className="h-4 px-1.5 py-0 text-[9px] uppercase">
          Internal
        </Badge>
      )}
      <span className={isInbound ? "text-muted-foreground" : "font-semibold text-foreground"}>
        {blockingEntity}
      </span>
      <ArrowRight className="size-3 shrink-0 text-muted-foreground" />
      <span className={isInbound ? "font-semibold text-foreground" : "text-muted-foreground"}>
        {blockedEntity}
      </span>
    </div>
  );
}
