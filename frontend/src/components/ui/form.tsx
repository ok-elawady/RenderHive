import * as React from "react";

import { cn } from "@/lib/utils";

function Form({ className, ...props }: React.ComponentProps<"form">) {
  return <form className={cn("space-y-5", className)} {...props} />;
}

function FormField({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("space-y-2", className)} {...props} />;
}

function FormItem({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("space-y-2", className)} {...props} />;
}

function FormLabel({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn("text-sm font-bold text-muted-foreground", className)}
      {...props}
    />
  );
}

function FormControl({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("relative", className)} {...props} />;
}

function FormMessage({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn("text-xs font-semibold text-destructive", className)}
      {...props}
    />
  );
}

export { Form, FormControl, FormField, FormItem, FormLabel, FormMessage };
