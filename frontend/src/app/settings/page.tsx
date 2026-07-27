"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Eye, EyeOff, Loader2, Lock, LockKeyhole, ShieldCheck, UserCog } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { changePassword, fetchCurrentUserProfile, formatApiError, type CurrentUserProfile } from "@/services/api";
import { PageHeader } from "@/components/layout/PageHeader";

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
  const passwordsMatch = passwords.confirmPassword === "" || passwords.newPassword === passwords.confirmPassword;
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
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader title="Account Settings" description="Manage your profile identity, security, and preferences." />

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          <Card className="border-border bg-card/95">
            <CardHeader className="border-b border-border pb-4">
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-base font-black">
                  <UserCog className="text-primary" size={18} />
                  Personal Information
                </div>
                <Badge
                  variant="outline"
                  className="border-border bg-muted/30 px-3 py-1 font-normal text-muted-foreground"
                >
                  Managed by Admin
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-6 p-6">
              <div className="flex items-center gap-5">
                <div className="flex aspect-square size-16 items-center justify-center rounded-xl bg-gradient-to-br from-[#d01fc7] to-primary text-xl font-bold text-white shrink-0 shadow-inner">
                  {initials}
                </div>
                <div>
                  <h2 className="text-xl font-black tracking-tight text-foreground">
                    {isLoadingProfile ? "Loading profile..." : fullName}
                  </h2>
                  <p className="mt-1 text-sm font-semibold text-muted-foreground">{role}</p>
                </div>
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <ReadOnlyField label="First Name" value={profile?.firstName || user?.firstName || ""} />
                <ReadOnlyField label="Last Name" value={profile?.lastName || user?.lastName || ""} />
                <ReadOnlyField label="Username" value={profile?.username || user?.username || ""} />
                <ReadOnlyField label="Email Address" value={profile?.email || user?.email || ""} />
                <ReadOnlyField label="Title / Role" value={role} />
                <ReadOnlyField
                  label="Access Level"
                  value={profile?.isSuperuser ? "Superuser" : profile?.isStaff ? "Staff" : "User"}
                />
              </div>
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
              <form onSubmit={(event) => void handlePasswordSubmit(event)} className="w-full space-y-4">
                <div className="space-y-2">
                  <Label>Current Password</Label>
                  <PasswordInput
                    value={passwords.currentPassword}
                    isVisible={visiblePasswords.currentPassword}
                    onToggleVisibility={() => togglePasswordVisibility("currentPassword")}
                    onChange={(value) => handlePasswordChange("currentPassword", value)}
                    hasError={Boolean(passwordError) && !passwords.currentPassword}
                    autoComplete="current-password"
                  />
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>New Password</Label>
                    <PasswordInput
                      value={passwords.newPassword}
                      isVisible={visiblePasswords.newPassword}
                      onToggleVisibility={() => togglePasswordVisibility("newPassword")}
                      onChange={(value) => handlePasswordChange("newPassword", value)}
                      hasError={!newPasswordLongEnough}
                      autoComplete="new-password"
                    />
                    {!newPasswordLongEnough && (
                      <p className="text-[0.8rem] font-medium text-destructive">Must be at least 8 characters.</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Confirm New Password</Label>
                    <PasswordInput
                      value={passwords.confirmPassword}
                      isVisible={visiblePasswords.confirmPassword}
                      onToggleVisibility={() => togglePasswordVisibility("confirmPassword")}
                      onChange={(value) => handlePasswordChange("confirmPassword", value)}
                      hasError={!passwordsMatch}
                      autoComplete="new-password"
                    />
                    {!passwordsMatch && (
                      <p className="text-[0.8rem] font-medium text-destructive">Passwords do not match.</p>
                    )}
                  </div>
                </div>

                {passwordError ? <p className="text-[0.8rem] font-medium text-destructive">{passwordError}</p> : null}

                <Button type="submit" disabled={!canSubmit} size="lg" className="mt-2 sm:w-auto">
                  {isChangingPassword ? <Loader2 className="animate-spin" /> : <LockKeyhole />}
                  Update Password
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
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
    <div className="relative">
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
    </div>
  );
}

function getDisplayValue(value: string | null | undefined): string {
  if (value == null) return "N/A";

  const normalizedValue = value.trim();
  return normalizedValue === "" || normalizedValue === "-" ? "N/A" : normalizedValue;
}

function ReadOnlyField({ label, value }: { label: string; value: string | null | undefined }) {
  const displayValue = getDisplayValue(value);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <span className="flex items-center gap-1 text-[11px] text-muted-foreground/60">
          <Lock size={11} />
          Read-only
        </span>
      </div>
      <Input
        value={value || "-"}
        readOnly
        tabIndex={-1}
        className="bg-muted/40 text-muted-foreground border-border/50 cursor-not-allowed select-none focus-visible:ring-0"
      />
    </div>
  );
}
