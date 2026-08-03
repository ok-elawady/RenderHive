"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Layers, Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

import { createPoolSchema, type CreatePoolFormValues } from "./schema";

interface CreatePoolFormProps {
  onSubmit: (data: CreatePoolFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function CreatePoolForm({ onSubmit, onCancel, isSubmitting }: CreatePoolFormProps) {
  const form = useForm<CreatePoolFormValues>({
    resolver: zodResolver(createPoolSchema as any),
    mode: "onChange",
    defaultValues: {
      name: "",
      description: "",
    },
  });

  return (
    <Form {...form}>
      <form 
        onSubmit={form.handleSubmit(onSubmit)} 
        noValidate 
        data-errors={Object.keys(form.formState.errors).length}
        className="flex flex-col h-full"
      >
        <div className="flex-1 space-y-6">
          {/* Identity Section */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
                <Layers size={16} />
              </div>
              <h3 className="text-sm font-semibold text-foreground">Pool Information</h3>
            </div>
            <div className="grid gap-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Pool Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. render-farm" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description (Optional)</FormLabel>
                    <FormControl>
                      <Textarea 
                        placeholder="Purpose of this pool..." 
                        className="resize-none min-h-[100px]"
                        {...field} 
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 border-t border-border mt-8">
          <Button
            type="button"
            variant="outline"
            disabled={isSubmitting}
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <Loader2 className="animate-spin" size={16} />
            ) : (
              <Plus size={16} />
            )}
            {isSubmitting ? "Creating..." : "Create Pool"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
