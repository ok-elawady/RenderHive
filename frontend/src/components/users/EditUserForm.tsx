"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, BadgeCheck, UserRound, ChevronDown, RefreshCw } from "lucide-react";
import { useEffect } from "react";

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

import { USER_ACCESS_LEVELS, USER_TITLE_ROLES, type User } from "@/services/api";

import { updateUserSchema, type UpdateUserFormValues } from "./schema";

interface EditUserFormProps {
  user: User;
  onSubmit: (data: UpdateUserFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function EditUserForm({ user, onSubmit, onCancel, isSubmitting }: EditUserFormProps) {
  const form = useForm<UpdateUserFormValues>({
    resolver: zodResolver(updateUserSchema as any),
    mode: "onChange",
    defaultValues: {
      fullName: [user.first_name, user.last_name].filter(Boolean).join(" ") || "",
      email: user.email || "",
      titleRole: USER_TITLE_ROLES.includes(user.title_role as any) 
        ? (user.title_role as any) 
        : "Render User",
      accessLevel: user.access_level || "Client",
    },
  });

  const { errors } = form.formState;

  // Reset form when the selected user changes
  useEffect(() => {
    form.reset({
      fullName: [user.first_name, user.last_name].filter(Boolean).join(" ") || "",
      email: user.email || "",
      titleRole: USER_TITLE_ROLES.includes(user.title_role as any) 
        ? (user.title_role as any) 
        : "Render User",
      accessLevel: user.access_level || "Client",
    });
  }, [user, form]);

  return (
    <Form {...form}>
      <form 
        onSubmit={form.handleSubmit(onSubmit)} 
        className="space-y-6" 
        noValidate
        data-errors={Object.keys(form.formState.errors).length}
      >
        {/* Identity Section */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
              <UserRound size={16} />
            </div>
            <h3 className="text-sm font-semibold text-foreground">Identity Information</h3>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="fullName"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Full Name / Display Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. John Doe or Pipeline Bot" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Email Address</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>

        <div className="h-px w-full bg-border/50" />

        {/* Role & Access Section */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
              <BadgeCheck size={16} />
            </div>
            <h3 className="text-sm font-semibold text-foreground">Role & Permissions</h3>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="titleRole"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title / Role</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <select
                        {...field}
                        className="flex h-9 w-full appearance-none rounded-lg border border-transparent bg-input/50 pl-3 pr-8 py-1 text-base md:text-sm transition-colors outline-none hover:bg-input/80 hover:border-border/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
                      >
                        {USER_TITLE_ROLES.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="accessLevel"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Access Level</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <select
                        {...field}
                        className="flex h-9 w-full appearance-none rounded-lg border border-transparent bg-input/50 pl-3 pr-8 py-1 text-base md:text-sm transition-colors outline-none hover:bg-input/80 hover:border-border/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
                      >
                        {USER_ACCESS_LEVELS.map((level) => (
                          <option key={level} value={level}>
                            {level}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 border-t border-border mt-8">
          <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={!form.formState.isDirty || isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Changes"
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}
