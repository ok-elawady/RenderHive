"use client";

import Image from "next/image";
import { useState, type FormEvent } from "react";
import { Eye, EyeOff, Loader2, LockKeyhole, User } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { formatApiError } from "@/services/api";

interface LoginFormValues {
  username: string;
  password: string;
}

interface LoginFormErrors {
  username?: string;
  password?: string;
  root?: string;
}

const initialValues: LoginFormValues = {
  username: "",
  password: "",
};

function validateLoginForm(values: LoginFormValues): LoginFormErrors {
  const errors: LoginFormErrors = {};

  if (!values.username.trim()) {
    errors.username = "Username is required.";
  }

  if (!values.password) {
    errors.password = "Password is required.";
  }

  return errors;
}

export default function LoginPage() {
  const { loginUser } = useAuth();
  const [values, setValues] = useState<LoginFormValues>(initialValues);
  const [errors, setErrors] = useState<LoginFormErrors>({});
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    const validationErrors = validateLoginForm(values);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      await loginUser({
        username: values.username.trim(),
        password: values.password,
      });
    } catch (error) {
      setErrors({
        username: " ",
        password: " ",
        root:
          formatApiError(error) ||
          "Invalid username or password. Please check your credentials.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-background p-6 text-foreground font-mono">
      <Card className="w-full max-w-md border-border bg-card/95 shadow-2xl shadow-black/40">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto flex flex-col items-center gap-3">
            <div className="relative size-16">
              <Image
                src="/logo.svg"
                alt="RenderHive Logo"
                fill
                sizes="64px"
                className="object-contain drop-shadow-[0_0_18px_rgba(90,31,166,0.45)] dark:hidden"
                priority
              />
              <Image
                src="/logo-dark.svg"
                alt="RenderHive Logo"
                fill
                sizes="64px"
                className="object-contain drop-shadow-[0_0_18px_rgba(90,31,166,0.45)] hidden dark:block"
                priority
              />
            </div>
          </div>
          <div>
            <CardTitle className="text-2xl font-black tracking-tight">
              <span className="text-zinc-950 dark:text-slate-100">Render</span>
              <span className="text-violet-500">Hive</span>
            </CardTitle>
            <CardDescription className="mt-2 text-sm">
              Welcome To Our Render Management{" "}
              <span className="font-black text-zinc-950 dark:text-slate-100">
                Render
              </span>
              <span className="font-black text-violet-500">Hive</span>
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <div className="relative">
                <User
                  size={16}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="username"
                  value={values.username}
                  onChange={(event) => {
                    setValues((current) => ({
                      ...current,
                      username: event.target.value,
                    }));
                    setErrors((current) => ({
                      ...current,
                      username: undefined,
                      root: undefined,
                    }));
                  }}
                  className="pl-9"
                  aria-invalid={Boolean(errors.username)}
                  autoComplete="username"
                  disabled={isSubmitting}
                />
              </div>
              {errors.username && errors.username.trim() && (
                <p className="text-sm font-medium text-destructive">{errors.username}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <LockKeyhole
                  size={16}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={values.password}
                  onChange={(event) => {
                    setValues((current) => ({
                      ...current,
                      password: event.target.value,
                    }));
                    setErrors((current) => ({
                      ...current,
                      password: undefined,
                      root: undefined,
                    }));
                  }}
                  className="px-9"
                  aria-invalid={Boolean(errors.password)}
                  autoComplete="current-password"
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && errors.password.trim() && (
                <p className="text-sm font-medium text-destructive">{errors.password}</p>
              )}
            </div>

            {errors.root && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs font-semibold text-destructive">
                {errors.root}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="animate-spin" size={16} />}
              {isSubmitting ? "Authenticating..." : "Sign In"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
