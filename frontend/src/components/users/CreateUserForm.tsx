"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { BadgeCheck, UserRound, Lock, Eye, EyeOff, WandSparkles, ChevronDown, Plus, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { generateSecurePassword } from "@/lib/utils";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

import { USER_ACCESS_LEVELS, USER_TITLE_ROLES } from "@/services/api";

import { createUserSchema, type CreateUserFormValues } from "./schema";

interface CreateUserFormProps {
  onSubmit: (data: CreateUserFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function CreateUserForm({ onSubmit, onCancel, isSubmitting }: CreateUserFormProps) {
  const [showPassword, setShowPassword] = useState(false);

  const form = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserSchema as never) as unknown as import("react-hook-form").Resolver<CreateUserFormValues>,
    mode: "onChange",
    defaultValues: {
      fullName: "",
      username: "",
      email: "",
      titleRole: "Animator",
      accessLevel: "Client",
      password: "",
    },
  });

  const handleGeneratePassword = () => {
    const pwd = generateSecurePassword();
    form.setValue("password", pwd, { shouldValidate: true });
    setShowPassword(true);
  };

  return (
    <Form {...form}>
      <form 
        onSubmit={form.handleSubmit(onSubmit)} 
        noValidate 
        data-errors={Object.keys(form.formState.errors).length}
      >
        {/* Identity Section */}
        <div className="mb-6">
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
              name="username"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Username</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
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

        <div className="h-px w-full bg-border/50 mb-6" />

        {/* Role & Access Section */}
        <div className="mb-6">
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

        <div className="h-px w-full bg-border/50 mb-6" />

        {/* Security Section */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
              <Lock size={16} />
            </div>
            <h3 className="text-sm font-semibold text-foreground">Security Details</h3>
          </div>
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between">
                  <FormLabel>Password</FormLabel>
                  <button
                    type="button"
                    className="text-xs text-primary hover:underline flex items-center gap-1 cursor-pointer"
                    onClick={handleGeneratePassword}
                  >
                    <WandSparkles size={12} />
                    Generate
                  </button>
                </div>
                <FormControl>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      className="pr-11"
                      {...field}
                    />
                    <button
                      type="button"
                      className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                      onClick={() => setShowPassword((current) => !current)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
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
            {isSubmitting ? "Creating..." : "Create User"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
