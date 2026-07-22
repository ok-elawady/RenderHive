"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      richColors={false}
      style={{
        "--normal-bg": "var(--card)",
        "--normal-text": "var(--card-foreground)",
        "--normal-border": "var(--border)",
      } as React.CSSProperties}
      icons={{
        success: (
          <CircleCheckIcon className="size-4 text-emerald-400 shrink-0" />
        ),
        info: (
          <InfoIcon className="size-4 text-primary shrink-0" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4 text-amber-400 shrink-0" />
        ),
        error: (
          <OctagonXIcon className="size-4 text-rose-400 shrink-0" />
        ),
        loading: (
          <Loader2Icon className="size-4 text-primary animate-spin shrink-0" />
        ),
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:!bg-card group-[.toaster]:!text-card-foreground group-[.toaster]:!border-border group-[.toaster]:shadow-2xl group-[.toaster]:shadow-black/30 group-[.toaster]:rounded-xl group-[.toaster]:font-mono group-[.toaster]:p-4 group-[.toaster]:gap-3",
          title: "group-[.toast]:font-bold group-[.toast]:text-sm group-[.toast]:!text-card-foreground tracking-tight font-mono",
          description: "group-[.toast]:!text-muted-foreground group-[.toast]:text-xs group-[.toast]:mt-0.5 font-mono",
          actionButton:
            "group-[.toast]:!bg-primary group-[.toast]:!text-primary-foreground group-[.toast]:font-bold group-[.toast]:text-xs group-[.toast]:rounded-lg group-[.toast]:px-3 group-[.toast]:py-1.5 transition-all hover:opacity-90 shadow-sm shadow-primary/30",
          cancelButton:
            "group-[.toast]:!bg-muted group-[.toast]:!text-muted-foreground group-[.toast]:font-semibold group-[.toast]:text-xs group-[.toast]:rounded-lg group-[.toast]:px-3 group-[.toast]:py-1.5 transition-colors hover:bg-muted/80",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
