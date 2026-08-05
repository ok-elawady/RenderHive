import * as React from "react"

import { cn } from "@/lib/utils"

function Card({
  className,
  size = "default",
  variant = "default",
  ...props
}: React.ComponentProps<"div"> & { size?: "default" | "sm", variant?: "default" | "flush" }) {
  return (
    <div
      data-slot="card"
      data-size={size}
      data-variant={variant}
      className={cn(
        "group/card flex flex-col overflow-hidden rounded-xl bg-card text-sm text-card-foreground border border-border *:[img:first-child]:rounded-t-xl *:[img:last-child]:rounded-b-xl",
        variant === "default" && "gap-(--card-spacing) py-(--card-spacing) [--card-spacing:--spacing(4)] has-[>img:first-child]:pt-0 data-[size=sm]:[--card-spacing:--spacing(3)]",
        variant === "flush" && "p-0 gap-0",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({ 
  className, 
  variant = "default",
  ...props 
}: React.ComponentProps<"div"> & { variant?: "default" | "flush" | "tabs" }) {
  return (
    <div
      data-slot="card-header"
      data-variant={variant}
      className={cn(
        "group/card-header @container/card-header rounded-t-xl",
        variant === "default" && "grid auto-rows-min items-start gap-1.5 has-data-[slot=card-action]:grid-cols-[1fr_auto] has-data-[slot=card-description]:grid-rows-[auto_auto] [.border-b]:pb-(--card-spacing) px-(--card-spacing)",
        variant === "flush" && "flex flex-row items-center justify-between px-4 py-3 border-b border-border/50",
        variant === "tabs" && "flex flex-row items-center justify-between px-4 py-2 border-b border-border/50",
        className
      )}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      className={cn("text-base font-medium", className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        "group-data-[variant=default]/card-header:col-start-2 group-data-[variant=default]/card-header:row-span-2 group-data-[variant=default]/card-header:row-start-1 group-data-[variant=default]/card-header:self-start group-data-[variant=default]/card-header:justify-self-end",
        className
      )}
      {...props}
    />
  )
}

function CardContent({ 
  className, 
  variant = "default",
  ...props 
}: React.ComponentProps<"div"> & { variant?: "default" | "flush" }) {
  return (
    <div
      data-slot="card-content"
      data-variant={variant}
      className={cn(
        variant === "default" && "px-(--card-spacing)",
        variant === "flush" && "p-0",
        className
      )}
      {...props}
    />
  )
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn(
        "flex items-center rounded-b-xl px-(--card-spacing) [.border-t]:pt-(--card-spacing)",
        className
      )}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
}
