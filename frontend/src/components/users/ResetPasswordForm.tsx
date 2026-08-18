"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, KeyRound, Eye, EyeOff, WandSparkles } from "lucide-react";
import { useForm } from "react-hook-form";
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
import type { User } from "@/services/api";

import { resetPasswordSchema, type ResetPasswordFormValues } from "./schema";

interface ResetPasswordFormProps {
  user: User;
  onSubmit: (data: ResetPasswordFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function ResetPasswordForm({
  user,
  onSubmit,
  onCancel,
  isSubmitting,
}: ResetPasswordFormProps) {
  const [showPassword, setShowPassword] = useState(false);

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema as never) as unknown as import("react-hook-form").Resolver<ResetPasswordFormValues>,
    mode: "onChange",
    defaultValues: {
      password: "",
    },
  });

  const handleGeneratePassword = () => {
    const pwd = generateSecurePassword();
    form.setValue("password", pwd, { shouldValidate: true });
    setShowPassword(true);
  };

  const handleSubmit = async (data: ResetPasswordFormValues) => {
    await onSubmit(data);
    form.reset();
  };

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleSubmit)}
        className="space-y-6"
        noValidate
        data-errors={Object.keys(form.formState.errors).length}
      >
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-destructive/15 text-destructive">
              <KeyRound size={16} />
            </div>
            <h3 className="text-sm font-semibold text-foreground">Reset Password</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            Set a new secure password for <span className="font-semibold text-foreground">{user.username}</span>.
          </p>

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between">
                  <FormLabel>New Password</FormLabel>
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
                      placeholder="Enter new secure password"
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
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button type="submit" variant="destructive" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Resetting...
              </>
            ) : (
              "Reset Password"
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}
