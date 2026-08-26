"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Server,
  LayoutTemplate,
  Search,
  Loader2,
  ListOrdered
} from "lucide-react";
import { Button } from "@/components/ui/button";

import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useUnifiedSearch } from "@/hooks/useUnifiedSearch";

export function GlobalSearch() {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const { results, isLoading } = useUnifiedSearch(query);
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const runCommand = React.useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  const hasResults =
    results.jobs.length > 0 ||
    results.workers.length > 0 ||
    results.pools.length > 0;

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(true)}
        aria-label="Search the render farm (Ctrl+K)"
        title="Search (Ctrl+K)"
        className="group hover:bg-accent/50"
      >
        <Search size={18} className="text-muted-foreground group-hover:text-primary transition-colors" />
      </Button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <Command shouldFilter={false} className="bg-transparent">
          <CommandInput
            placeholder="Search jobs, workers, or pools..."
            value={query}
            onValueChange={setQuery}
            className="h-12 text-base px-2"
          />
          <CommandList>
          {isLoading && (
            <div className="p-4 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching...
            </div>
          )}
          {!isLoading && !hasResults && query.trim() !== "" && (
            <CommandEmpty className="py-6 text-center text-sm">No results found for &quot;{query}&quot;.</CommandEmpty>
          )}

          {!isLoading && query.trim() === "" && (
            <div className="py-14 px-6 text-center text-sm text-muted-foreground">
              <Search className="mx-auto h-10 w-10 opacity-20 mb-4" />
              <p className="text-base font-medium text-foreground/80 mb-1">Search the Render Farm</p>
              <p>Type above to find active jobs, worker nodes, and hardware pools instantly.</p>
            </div>
          )}

          {!isLoading && results.jobs.length > 0 && (
            <CommandGroup heading="Jobs">
              {results.jobs.map((job) => (
                <CommandItem
                  key={job.id}
                  value={`job-${job.id}-${job.name}-${job.visible_name}`}
                  onSelect={() =>
                    runCommand(() => router.push(`/jobs/${job.id}`))
                  }
                >
                  <ListOrdered className="mr-2 h-4 w-4 shrink-0 text-primary" />
                  <div className="flex flex-col">
                    <span className="text-sm">{job.visible_name || job.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {job.project} {job.department && `• ${job.department}`}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          
          {!isLoading && results.jobs.length > 0 && (results.workers.length > 0 || results.pools.length > 0) && (
            <CommandSeparator className="my-2" />
          )}

          {!isLoading && results.workers.length > 0 && (
            <CommandGroup heading="Worker Nodes">
              {results.workers.map((worker) => (
                <CommandItem
                  key={worker.hostname}
                  value={`worker-${worker.hostname}-${worker.ip_address}`}
                  onSelect={() =>
                    runCommand(() => router.push(`/nodes?search=${encodeURIComponent(worker.hostname)}`))
                  }
                >
                  <Server className="mr-2 h-4 w-4 shrink-0 text-primary" />
                  <div className="flex flex-col">
                    <span className="text-sm">{worker.hostname}</span>
                    <span className="text-xs text-muted-foreground">
                      {worker.status} • {worker.ip_address}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          
          {!isLoading && results.workers.length > 0 && results.pools.length > 0 && (
            <CommandSeparator className="my-2" />
          )}

          {!isLoading && results.pools.length > 0 && (
            <CommandGroup heading="Worker Pools">
              {results.pools.map((pool) => (
                <CommandItem
                  key={pool.name}
                  value={`pool-${pool.name}-${pool.description}`}
                  onSelect={() =>
                    runCommand(() => router.push(`/pools?search=${encodeURIComponent(pool.name)}`))
                  }
                >
                  <LayoutTemplate className="mr-2 h-4 w-4 shrink-0 text-primary" />
                  <div className="flex flex-col">
                    <span className="text-sm">{pool.name}</span>
                    {pool.description && (
                      <span className="text-xs text-muted-foreground">
                        {pool.description}
                      </span>
                    )}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
