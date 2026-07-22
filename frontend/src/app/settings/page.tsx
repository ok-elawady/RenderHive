"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Eye, EyeOff, Loader2, Lock, LockKeyhole, ShieldCheck, UserCog } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  changePassword,
  fetchCurrentUserProfile,
  formatApiError,
  type CurrentUserProfile,
} from "@/services/api";

interface PasswordState {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const emptyPasswordState: PasswordState = {
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
};

export default function SettingsPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<CurrentUserProfile | null>(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState<boolean>(true);
  const [isChangingPassword, setIsChangingPassword] = useState<boolean>(false);
  const [passwords, setPasswords] = useState<PasswordState>(emptyPasswordState);
  const [visiblePasswords, setVisiblePasswords] = useState<Record<keyof PasswordState, boolean>>({
    currentPassword: false,
    newPassword: false,
    confirmPassword: false,
  });
  const [passwordError, setPasswordError] = useState<string>("");

  useEffect(() => {
    let isMounted = true;

    async function loadProfile(): Promise<void> {
      try {
        const nextProfile = await fetchCurrentUserProfile();
        if (isMounted) setProfile(nextProfile);
      } catch (error) {
        toast.error("Unable to load profile", {
          description: formatApiError(error),
        });
      } finally {
        if (isMounted) setIsLoadingProfile(false);
      }
    }

    void loadProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  const fullName =
    profile && [profile.firstName, profile.lastName].filter(Boolean).join(" ")
      ? [profile.firstName, profile.lastName].filter(Boolean).join(" ")
      : user?.displayName || profile?.username || "RenderHive User";
  const role = profile?.role || user?.role || "Authenticated";
  const initials = user?.initials || fullName.slice(0, 2).toUpperCase() || "RH";

  const handlePasswordChange = (field: keyof PasswordState, value: string): void => {
    setPasswords((currentPasswords) => ({
      ...currentPasswords,
      [field]: value,
    }));
    if (passwordError) setPasswordError("");
  };

  const togglePasswordVisibility = (field: keyof PasswordState): void => {
    setVisiblePasswords((currentVisibility) => ({
      ...currentVisibility,
      [field]: !currentVisibility[field],
    }));
  };

  // Derived validation — drives button disabled state and inline messages.
  const allFieldsFilled =
    passwords.currentPassword.trim() !== "" &&
    passwords.newPassword.trim() !== "" &&
    passwords.confirmPassword.trim() !== "";
  const newPasswordLongEnough = passwords.newPassword === "" || passwords.newPassword.length >= 8;
  const passwordsMatch =
    passwords.confirmPassword === "" || passwords.newPassword === passwords.confirmPassword;
  const canSubmit = allFieldsFilled && newPasswordLongEnough && passwordsMatch && !isChangingPassword;

  const handlePasswordSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    if (!allFieldsFilled) {
      setPasswordError("All password fields are required.");
      return;
    }
    if (!newPasswordLongEnough) {
      setPasswordError("New password must be at least 8 characters.");
      return;
    }
    if (!passwordsMatch) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await changePassword({
        currentPassword: passwords.currentPassword,
        newPassword: passwords.newPassword,
      });
      setPasswords(emptyPasswordState);
      toast.success("Password updated", {
        description: "Your new password is now active across RenderHive.",
      });
    } catch (error) {
      setPasswordError(formatApiError(error));
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <div className="h-screen overflow-y-auto bg-background p-4 text-foreground font-mono md:p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">
        <Card className="border-border bg-card/95 shadow-2xl shadow-black/10 dark:shadow-black/30">
          <CardContent className="flex flex-col gap-6 p-6 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <div className="flex size-24 items-center justify-center rounded-2xl border border-primary/40 bg-gradient-to-br from-primary/30 to-[#d01fc7]/20 text-3xl font-black text-primary shadow-[0_0_24px_rgba(90,31,166,0.22)]">
                {initials}
              </div>
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">
                  My Profile
                </p>
                <h1 className="mt-2 text-2xl font-black tracking-tight text-foreground">
                  {isLoadingProfile ? "Loading profile..." : fullName}
                </h1>
                <p className="mt-1 text-sm font-semibold text-muted-foreground">{role}</p>
              </div>
            </div>
            <Badge variant="outline" className="border-border bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground font-normal">
              Profile identity is managed by Django Admin
            </Badge>
          </CardContent>
        </Card>

        <Card className="border-border bg-card/95">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle className="flex items-center gap-3 text-base font-black">
              <UserCog className="text-primary" size={18} />
              Personal Information
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-5 p-6 md:grid-cols-2">
            <ReadOnlyField label="First Name" value={profile?.firstName || user?.firstName || ""} />
            <ReadOnlyField label="Last Name" value={profile?.lastName || user?.lastName || ""} />
            <ReadOnlyField label="Username" value={profile?.username || user?.username || ""} />
            <ReadOnlyField label="Email Address" value={profile?.email || user?.email || ""} />
            <ReadOnlyField label="Title / Role" value={role} />
            <ReadOnlyField
              label="Access Level"
              value={profile?.isSuperuser ? "Superuser" : profile?.isStaff ? "Staff" : "User"}
            />
          </CardContent>
        </Card>

        <Card className="border-border bg-card/95">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle className="flex items-center gap-3 text-base font-black">
              <ShieldCheck className="text-primary" size={18} />
              Security Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <Form
              onSubmit={(event) => void handlePasswordSubmit(event)}
              className="w-full space-y-4"
            >
              <FormField>
                <FormLabel>Current Password</FormLabel>
                <PasswordInput
                  value={passwords.currentPassword}
                  isVisible={visiblePasswords.currentPassword}
                  onToggleVisibility={() => togglePasswordVisibility("currentPassword")}
                  onChange={(value) => handlePasswordChange("currentPassword", value)}
                  hasError={Boolean(passwordError) && !passwords.currentPassword}
                  autoComplete="current-password"
                />
              </FormField>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField>
                  <FormLabel>New Password</FormLabel>
                  <PasswordInput
                    value={passwords.newPassword}
                    isVisible={visiblePasswords.newPassword}
                    onToggleVisibility={() => togglePasswordVisibility("newPassword")}
                    onChange={(value) => handlePasswordChange("newPassword", value)}
                    hasError={!newPasswordLongEnough}
                    autoComplete="new-password"
                  />
                  {!newPasswordLongEnough && (
                    <FormMessage>Must be at least 8 characters.</FormMessage>
                  )}
                </FormField>

                <FormField>
                  <FormLabel>Confirm New Password</FormLabel>
                  <PasswordInput
                    value={passwords.confirmPassword}
                    isVisible={visiblePasswords.confirmPassword}
                    onToggleVisibility={() => togglePasswordVisibility("confirmPassword")}
                    onChange={(value) => handlePasswordChange("confirmPassword", value)}
                    hasError={!passwordsMatch}
                    autoComplete="new-password"
                  />
                  {!passwordsMatch && (
                    <FormMessage>Passwords do not match.</FormMessage>
                  )}
                </FormField>
              </div>

              {passwordError ? <FormMessage>{passwordError}</FormMessage> : null}

              <Button type="submit" disabled={!canSubmit} size="lg" className="mt-2 sm:w-auto">
                {isChangingPassword ? <Loader2 className="animate-spin" /> : <LockKeyhole />}
                Update Password
              </Button>
            </Form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PasswordInput({
  value,
  isVisible,
  onToggleVisibility,
  onChange,
  hasError,
  autoComplete,
}: {
  value: string;
  isVisible: boolean;
  onToggleVisibility: () => void;
  onChange: (value: string) => void;
  hasError: boolean;
  autoComplete: "current-password" | "new-password";
}) {
  const Icon = isVisible ? EyeOff : Eye;

  return (
    <FormControl>
      <Input
        type={isVisible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={hasError}
        autoComplete={autoComplete}
        className="pr-11"
      />
      <button
        type="button"
        onClick={onToggleVisibility}
        className="absolute right-3 top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
        aria-label={isVisible ? "Hide password" : "Show password"}
      >
        <Icon size={16} />
      </button>
    </FormControl>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <FormField>
      <div className="flex items-center justify-between">
        <FormLabel>{label}</FormLabel>
        <span className="flex items-center gap-1 text-[11px] text-muted-foreground/60">
          <Lock size={11} />
          Read-only
        </span>
      </div>
      <FormControl>
        <Input
          value={value || "-"}
          readOnly
          tabIndex={-1}
          className="bg-muted/40 text-muted-foreground border-border/50 cursor-not-allowed select-none focus-visible:ring-0"
        />
      </FormControl>
    </FormField>
  );
}
