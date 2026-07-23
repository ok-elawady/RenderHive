"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { AlertCircle, Play, FileText } from "lucide-react";
import {
  buildJobRequest,
  createJob,
  formatApiError,
  getDefaultRenderCommand,
} from "@/services/api";
import type { JobFormValues } from "@/types/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface NewJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (jobName: string) => Promise<void> | void;
}

export default function NewJobModal({
  isOpen,
  onClose,
  onSuccess,
}: NewJobModalProps) {
  const defaultEngine = "Houdini (Mantra/Karma)";
  const defaultStartFrame = "1";
  const defaultEndFrame = "100";

  const [formData, setFormData] = useState<JobFormValues>({
    jobName: "",
    user: "",
    engine: defaultEngine,
    priority: 50,
    startFrame: defaultStartFrame,
    endFrame: defaultEndFrame,
    logDirectory: "/tmp/render_logs",
    renderCommand: getDefaultRenderCommand(
      defaultEngine,
      defaultStartFrame,
      defaultEndFrame,
    ),
  });

  const [hasError, setHasError] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    const flexiblePattern = /^[a-zA-Z0-9_]+_v[0-9]+$/;

    if (!formData.jobName.trim() || !flexiblePattern.test(formData.jobName)) {
      setHasError(true);
      return;
    }

    if (!formData.user.trim()) {
      setSubmitError("Artist Name is required.");
      return;
    }

    if (!formData.logDirectory.trim() || !formData.renderCommand.trim()) {
      setSubmitError("Log Directory and Render Command are required.");
      return;
    }

    setHasError(false);
    setSubmitError("");
    setIsSubmitting(true);

    try {
      await createJob(buildJobRequest(formData));
      await onSuccess(formData.jobName);
      onClose();
    } catch (error) {
      setSubmitError(formatApiError(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJobNameChange = (
    event: ChangeEvent<HTMLInputElement>,
  ): void => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      jobName: event.target.value,
    }));
    if (hasError) setHasError(false);
    if (submitError) setSubmitError("");
  };

  const handleUserChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      user: event.target.value,
    }));
    if (submitError) setSubmitError("");
  };

  const handleEngineChange = (value: string | null): void => {
    if (!value) return;
    setFormData((currentFormData) => ({
      ...currentFormData,
      engine: value,
      renderCommand: getDefaultRenderCommand(
        value,
        currentFormData.startFrame,
        currentFormData.endFrame,
      ),
    }));
  };

  const handleStartFrameChange = (
    event: ChangeEvent<HTMLInputElement>,
  ): void => {
    const nextStartFrame = event.target.value;

    setFormData((currentFormData) => {
      const currentDefaultCommand = getDefaultRenderCommand(
        currentFormData.engine,
        currentFormData.startFrame,
        currentFormData.endFrame,
      );
      const nextFormData = {
        ...currentFormData,
        startFrame: nextStartFrame,
      };

      return currentFormData.renderCommand === currentDefaultCommand
        ? {
            ...nextFormData,
            renderCommand: getDefaultRenderCommand(
              nextFormData.engine,
              nextFormData.startFrame,
              nextFormData.endFrame,
            ),
          }
        : nextFormData;
    });
  };

  const handleEndFrameChange = (
    event: ChangeEvent<HTMLInputElement>,
  ): void => {
    const nextEndFrame = event.target.value;

    setFormData((currentFormData) => {
      const currentDefaultCommand = getDefaultRenderCommand(
        currentFormData.engine,
        currentFormData.startFrame,
        currentFormData.endFrame,
      );
      const nextFormData = {
        ...currentFormData,
        endFrame: nextEndFrame,
      };

      return currentFormData.renderCommand === currentDefaultCommand
        ? {
            ...nextFormData,
            renderCommand: getDefaultRenderCommand(
              nextFormData.engine,
              nextFormData.startFrame,
              nextFormData.endFrame,
            ),
          }
        : nextFormData;
    });
  };

  const handlePriorityChange = (
    event: ChangeEvent<HTMLInputElement>,
  ): void => {
    const value = Number.parseInt(event.target.value, 10);
    setFormData((currentFormData) => ({
      ...currentFormData,
      priority: Number.isNaN(value) ? 50 : value,
    }));
  };

  const handleLogDirectoryChange = (
    event: ChangeEvent<HTMLInputElement>,
  ): void => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      logDirectory: event.target.value,
    }));
    if (submitError) setSubmitError("");
  };

  const handleRenderCommandChange = (
    event: ChangeEvent<HTMLTextAreaElement>,
  ): void => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      renderCommand: event.target.value,
    }));
    if (submitError) setSubmitError("");
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl p-0 gap-0 overflow-hidden border-border bg-surface">
        <DialogHeader className="border-b border-border px-8 py-5 bg-background/80">
          <DialogTitle className="text-lg font-bold text-foreground">
            Submit New Pipeline Job
          </DialogTitle>
        </DialogHeader>

        <form
          onSubmit={handleSubmit}
          className="p-8 space-y-6 font-mono text-sm max-h-[calc(92vh-78px)] overflow-y-auto"
        >
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <Label className="text-muted-foreground font-bold text-sm">
                Job ID / Scene Name
              </Label>
              {hasError && (
                <span className="text-destructive flex items-center gap-1.5 text-xs font-bold animate-pulse">
                  <AlertCircle size={14} /> Naming format error!
                </span>
              )}
            </div>
            <Input
              type="text"
              placeholder="e.g., LIGHT_v11 or FX_FLUID_v02"
              value={formData.jobName}
              onChange={handleJobNameChange}
              className={`h-12 text-sm ${
                hasError
                  ? "border-destructive focus-visible:ring-destructive/50"
                  : ""
              }`}
            />
            <div
              className={`p-3 rounded-md border text-xs leading-relaxed ${
                hasError
                  ? "bg-destructive/5 border-destructive/20 text-destructive"
                  : "bg-surface-deep border-border/50 text-muted-foreground"
              }`}
            >
              <p className="font-bold mb-1 text-primary flex items-center gap-1.5">
                <FileText size={14} /> Naming Rule:
              </p>
              <p>
                Can be a single word or multiple blocks but{" "}
                <span className="text-primary font-bold">must end with _v</span>{" "}
                and version number (e.g.,{" "}
                <span className="text-foreground">_v1</span>,{" "}
                <span className="text-foreground">_v12</span>).
              </p>
            </div>
            {submitError && (
              <p className="text-xs font-bold text-destructive">{submitError}</p>
            )}
          </div>

          <div className="space-y-3">
            <Label className="text-muted-foreground font-bold text-sm">
              Artist Name
            </Label>
            <Input
              type="text"
              value={formData.user}
              onChange={handleUserChange}
              placeholder="e.g. John Doe"
              className="h-12 text-sm"
            />
          </div>

          <div className="space-y-3">
            <Label className="text-muted-foreground font-bold text-sm">
              Log Directory
            </Label>
            <Input
              type="text"
              value={formData.logDirectory}
              onChange={handleLogDirectoryChange}
              placeholder="/tmp/render_logs"
              className="h-12 text-sm"
            />
          </div>

          <div className="space-y-3">
            <Label className="text-muted-foreground font-bold text-sm">
              Render Engine Environment
            </Label>
            <Select value={formData.engine} onValueChange={handleEngineChange}>
              <SelectTrigger className="h-12 text-sm">
                <SelectValue placeholder="Select Engine" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Houdini (Mantra/Karma)">
                  Houdini (Mantra/Karma)
                </SelectItem>
                <SelectItem value="Maya (Arnold/V-Ray)">
                  Maya (Arnold/V-Ray)
                </SelectItem>
                <SelectItem value="Unreal Engine 5 (MRQ)">
                  Unreal Engine 5 (MRQ)
                </SelectItem>
                <SelectItem value="Blender (Cycles)">
                  Blender (Cycles)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="space-y-3">
              <Label className="text-muted-foreground font-bold text-sm">
                Start Frame
              </Label>
              <Input
                type="number"
                value={formData.startFrame}
                onChange={handleStartFrameChange}
                className="h-12 text-center text-sm"
              />
            </div>
            <div className="space-y-3">
              <Label className="text-muted-foreground font-bold text-sm">
                End Frame
              </Label>
              <Input
                type="number"
                value={formData.endFrame}
                onChange={handleEndFrameChange}
                className="h-12 text-center text-sm"
              />
            </div>
            <div className="space-y-3">
              <Label className="text-muted-foreground font-bold text-sm">
                Priority
              </Label>
              <Input
                type="number"
                min={1}
                max={100}
                value={formData.priority}
                onChange={handlePriorityChange}
                className="h-12 text-center text-sm"
              />
            </div>
          </div>

          <div className="space-y-3">
            <Label className="text-muted-foreground font-bold text-sm">
              Render Command
            </Label>
            <Textarea
              value={formData.renderCommand}
              onChange={handleRenderCommandChange}
              rows={3}
              className="resize-none text-sm leading-relaxed"
            />
          </div>

          <div className="flex items-center justify-end gap-4 pt-5 border-t border-border mt-8">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="h-11 px-5"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="h-11 px-6"
            >
              <Play size={14} className="fill-current" />
              {isSubmitting ? "Queueing..." : "Queue Job"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
