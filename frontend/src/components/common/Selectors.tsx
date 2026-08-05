"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { buttonVariants, Button } from "@/components/ui/button";
import { Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { getJobs, getJobLayers, getLayerTasks, type BackendJob, type LayerList, type TaskList } from "@/services/api";

function useClickOutside(ref: React.RefObject<HTMLElement | null>, handler: () => void, enabled: boolean) {
  React.useEffect(() => {
    if (!enabled) return;
    const listener = (event: MouseEvent | TouchEvent) => {
      if (!ref.current || ref.current.contains(event.target as Node)) return;
      handler();
    };
    document.addEventListener("mousedown", listener);
    document.addEventListener("touchstart", listener);
    return () => {
      document.removeEventListener("mousedown", listener);
      document.removeEventListener("touchstart", listener);
    };
  }, [ref, handler, enabled]);
}

const SelectorTrigger = React.forwardRef<HTMLButtonElement, React.ComponentProps<"button">>(({ className, children, ...props }, ref) => {
  return (
    <button
      ref={ref}
      type="button"
      className={cn(
        "flex h-9 w-full items-center justify-between whitespace-nowrap rounded-lg border border-transparent bg-input/50 px-3 py-2 text-sm text-foreground shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 hover:bg-input/80 hover:border-border/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 [&>span]:line-clamp-1",
        className
      )}
      {...props}
    >
      {children}
      <ChevronsUpDown className="h-4 w-4 opacity-50 shrink-0" />
    </button>
  );
});
SelectorTrigger.displayName = "SelectorTrigger";

export function JobSelector({
  value,
  onChange,
  disabled,
  placeholder = "Select job...",
}: {
  value?: string;
  onChange: (val: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [jobs, setJobs] = React.useState<BackendJob[]>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    setLoading(true);
    getJobs()
      .then((res) => {
        if (mounted) {
          setJobs(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <>
      <SelectorTrigger
        disabled={disabled || loading}
        onClick={() => setOpen(true)}
        className="font-mono text-xs"
      >
        {value
          ? jobs.find((job) => job.id === value)?.visible_name || value
          : loading
            ? "Loading jobs..."
            : placeholder}
      </SelectorTrigger>
      <CommandDialog open={open} onOpenChange={setOpen} title="Select Job" description="Search and select a job from the queue">
        <Command className="text-slate-100">
          <CommandInput placeholder="Search jobs by name..." className="text-slate-100" />
          <CommandList>
            <CommandEmpty>No job found.</CommandEmpty>
            <CommandGroup>
              {jobs.map((job) => (
                <CommandItem
                  key={job.id}
                  value={job.visible_name + " " + job.id}
                  onSelect={() => {
                    onChange(job.id === value ? "" : job.id);
                    setOpen(false);
                  }}
                >
                  <Check className={cn("mr-2 h-4 w-4 shrink-0", value === job.id ? "opacity-100" : "opacity-0")} />
                  <div className="flex flex-col overflow-hidden">
                    <span className="truncate font-bold">{job.visible_name}</span>
                    <span className="text-[10px] text-muted-foreground truncate">{job.id}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}

export function LayerSelector({
  jobId,
  value,
  onChange,
  disabled,
  placeholder = "Select layer...",
}: {
  jobId?: string;
  value?: string;
  onChange: (val: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [layers, setLayers] = React.useState<LayerList[]>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!jobId) {
      setLayers([]);
      return;
    }
    let mounted = true;
    setLoading(true);
    getJobLayers(jobId)
      .then((res) => {
        if (mounted) {
          setLayers(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [jobId]);

  return (
    <>
      <SelectorTrigger
        disabled={disabled || loading || !jobId}
        onClick={() => setOpen(true)}
        className="font-mono text-xs"
      >
        {value
          ? layers.find((l) => l.id === value)?.name || value
          : !jobId
            ? "Select a job first"
            : loading
              ? "Loading layers..."
              : placeholder}
      </SelectorTrigger>
      <CommandDialog open={open} onOpenChange={setOpen} title="Select Layer" description="Search and select a layer from the job">
        <Command className="text-slate-100">
          <CommandInput placeholder="Search layers by name..." className="text-slate-100" />
          <CommandList>
            <CommandEmpty>No layer found.</CommandEmpty>
            <CommandGroup>
              {layers.map((layer) => (
                <CommandItem
                  key={layer.id}
                  value={layer.name + " " + layer.id}
                  onSelect={() => {
                    onChange(layer.id === value ? "" : layer.id);
                    setOpen(false);
                  }}
                >
                  <Check className={cn("mr-2 h-4 w-4 shrink-0", value === layer.id ? "opacity-100" : "opacity-0")} />
                  <div className="flex flex-col overflow-hidden">
                    <span className="truncate font-bold">{layer.name}</span>
                    <span className="text-[10px] text-muted-foreground truncate">{layer.id}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}

export function TaskSelector({
  jobId,
  layerId,
  value,
  onChange,
  disabled,
  placeholder = "Select task...",
}: {
  jobId?: string;
  layerId?: string;
  value?: string;
  onChange: (val: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [tasks, setTasks] = React.useState<TaskList[]>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!jobId || !layerId) {
      setTasks([]);
      return;
    }
    let mounted = true;
    setLoading(true);
    getLayerTasks(jobId, layerId)
      .then((res) => {
        if (mounted) {
          setTasks(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [jobId, layerId]);

  return (
    <>
      <SelectorTrigger
        disabled={disabled || loading || !layerId}
        onClick={() => setOpen(true)}
        className="font-mono text-xs"
      >
        {value
          ? tasks.find((t) => t.id === value)?.name || value
          : !layerId
            ? "Select a layer first"
            : loading
              ? "Loading tasks..."
              : placeholder}
      </SelectorTrigger>
      <CommandDialog open={open} onOpenChange={setOpen} title="Select Task" description="Search and select a task from the layer">
        <Command className="text-slate-100">
          <CommandInput placeholder="Search tasks by name..." className="text-slate-100" />
          <CommandList>
            <CommandEmpty>No task found.</CommandEmpty>
            <CommandGroup>
              {tasks.map((task) => (
                <CommandItem
                  key={task.id}
                  value={task.name + " " + task.id}
                  onSelect={() => {
                    onChange(task.id === value ? "" : task.id);
                    setOpen(false);
                  }}
                >
                  <Check className={cn("mr-2 h-4 w-4 shrink-0", value === task.id ? "opacity-100" : "opacity-0")} />
                  <div className="flex flex-col overflow-hidden">
                    <span className="truncate font-bold">{task.name}</span>
                    <span className="text-[10px] text-muted-foreground truncate">{task.id}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
