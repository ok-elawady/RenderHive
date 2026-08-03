"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface TabsContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const context = React.useContext(TabsContext);

  if (!context) {
    throw new Error("Tabs components must be used inside <Tabs>.");
  }

  return context;
}

function Tabs({
  value,
  defaultValue,
  onValueChange,
  className,
  ...props
}: React.ComponentProps<"div"> & {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
}) {
  const [internalValue, setInternalValue] = React.useState(defaultValue ?? "");
  const currentValue = value ?? internalValue;

  const contextValue = React.useMemo<TabsContextValue>(
    () => ({
      value: currentValue,
      onValueChange: (nextValue) => {
        setInternalValue(nextValue);
        onValueChange?.(nextValue);
      },
    }),
    [currentValue, onValueChange],
  );

  return (
    <TabsContext.Provider value={contextValue}>
      <div data-slot="tabs" className={cn("space-y-4", className)} {...props} />
    </TabsContext.Provider>
  );
}

function TabsList({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="tabs-list"
      className={cn(
        "inline-flex items-center text-muted-foreground",
        "h-10 w-full justify-start rounded-none border-b border-border bg-transparent p-0",
        className,
      )}
      {...props}
    />
  );
}

function TabsTrigger({ value, className, ...props }: React.ComponentProps<"button"> & { value: string }) {
  const { value: currentValue, onValueChange } = useTabsContext();
  const isActive = currentValue === value;

  return (
    <button
      type="button"
      data-slot="tabs-trigger"
      data-state={isActive ? "active" : "inactive"}
      className={cn(
        "inline-flex items-center justify-center text-sm font-medium transition-all cursor-pointer",
        "h-10 rounded-none border-b-2 border-transparent px-4 data-[state=active]:border-primary data-[state=active]:text-foreground hover:text-foreground text-muted-foreground",
        className,
      )}
      onClick={() => onValueChange(value)}
      {...props}
    />
  );
}

function TabsContent({ value, className, ...props }: React.ComponentProps<"div"> & { value: string }) {
  const { value: currentValue } = useTabsContext();

  if (currentValue !== value) return null;

  return <div data-slot="tabs-content" className={cn("outline-none", className)} {...props} />;
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
