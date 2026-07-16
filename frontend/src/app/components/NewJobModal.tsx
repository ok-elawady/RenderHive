"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { AlertCircle, Play, X } from "lucide-react";
import {
  buildJobRequest,
  createJob,
  formatApiError,
  getDefaultRenderCommand,
} from "../lib/api";
import type { JobFormValues } from "../lib/api";

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
    userId: 1,
    engine: defaultEngine,
    priority: "MED",
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

    if (formData.userId < 1) {
      setSubmitError("User ID must be a valid Django user ID.");
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

  const handleJobNameChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      jobName: event.target.value,
    }));
    if (hasError) setHasError(false);
    if (submitError) setSubmitError("");
  };

  const handleUserIdChange = (event: ChangeEvent<HTMLInputElement>): void => {
    const nextUserId = Number(event.target.value);

    setFormData((currentFormData) => ({
      ...currentFormData,
      userId: Number.isFinite(nextUserId)
        ? Math.max(1, Math.trunc(nextUserId))
        : 1,
    }));
    if (submitError) setSubmitError("");
  };

  const handleEngineChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    const nextEngine = event.target.value;

    setFormData((currentFormData) => ({
      ...currentFormData,
      engine: nextEngine,
      renderCommand: getDefaultRenderCommand(
        nextEngine,
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

  const handleEndFrameChange = (event: ChangeEvent<HTMLInputElement>): void => {
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
    event: ChangeEvent<HTMLSelectElement>,
  ): void => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      priority: event.target.value as JobFormValues["priority"],
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] w-full max-w-2xl max-h-[92vh] rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/90 overflow-hidden transform-gpu origin-center animate-[modalPopIn_0.3s_ease-out_forwards]">
        <div className="flex items-center justify-between border-b border-[#D7DBE3] dark:border-[#343B4D] px-8 py-5 bg-[#F7F8FA]/80 dark:bg-[#0E1016]/40">
          <div className="flex items-center gap-3">
            <div className="h-2.5 w-2.5 rounded-full bg-[#5A1FA6] shadow-[0_0_8px_#5A1FA6]"></div>
            <h3 className="text-lg font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
              Submit New Pipeline Job
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[#6B7280] dark:text-[#8A92A5] hover:text-[#1A1D23] dark:hover:text-[#F5F7FA] transition-colors cursor-pointer"
          >
            <X size={22} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="p-8 space-y-6 font-mono text-sm max-h-[calc(92vh-78px)] overflow-y-auto"
        >
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
                Job ID / Scene Name
              </label>
              {hasError && (
                <span className="text-[#FF5D73] flex items-center gap-1.5 text-xs font-bold animate-pulse">
                  <AlertCircle size={14} /> Naming format error!
                </span>
              )}
            </div>
            <input
              type="text"
              placeholder="e.g., LIGHT_v11 or FX_FLUID_v02"
              value={formData.jobName}
              onChange={handleJobNameChange}
              className={`w-full bg-[#F7F8FA] dark:bg-[#161B24] border rounded-xl px-5 py-3.5 text-[#1A1D23] dark:text-[#F5F7FA] placeholder-[#6B7280] dark:placeholder-[#8A92A5] focus:outline-none transition-all text-sm tracking-wide ${
                hasError
                  ? "border-[#FF5D73] bg-[#FF5D73]/5 shadow-[0_0_15px_rgba(255,93,115,0.15)] focus:border-[#FF5D73]"
                  : "border-[#D7DBE3] dark:border-[#31384A] focus:border-[#5A1FA6]"
              }`}
            />
            <div
              className={`p-3 rounded-lg border text-xs leading-relaxed ${
                hasError
                  ? "bg-[#FF5D73]/5 border-[#FF5D73]/20 text-[#FF5D73]"
                  : "bg-[#F7F8FA] dark:bg-[#1F2330]/60 border-[#D7DBE3] dark:border-[#343B4D]/50 text-[#6B7280] dark:text-[#8A92A5]"
              }`}
            >
              <p className="font-bold mb-1 text-[#9C73F2]">
                {"\uD83D\uDCDD"} Naming Rule:
              </p>
              <p>
                Can be a single word or multiple blocks but{" "}
                <span className="text-[#9C73F2] font-bold">
                  must end with _v
                </span>{" "}
                and version number (e.g.,{" "}
                <span className="text-[#1A1D23] dark:text-[#F5F7FA]">_v1</span>,{" "}
                <span className="text-[#1A1D23] dark:text-[#F5F7FA]">_v12</span>
                ).
              </p>
            </div>
            {submitError && (
              <p className="text-xs font-bold text-[#FF5D73]">{submitError}</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[0.45fr_1fr] gap-6">
            <div className="space-y-2">
              <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
                User ID
              </label>
              <input
                type="number"
                min={1}
                value={formData.userId}
                onChange={handleUserIdChange}
                className="w-full bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-4 py-3 text-[#1A1D23] dark:text-[#F5F7FA] text-center text-sm focus:outline-none focus:border-[#5A1FA6]"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
                Log Directory
              </label>
              <input
                type="text"
                value={formData.logDirectory}
                onChange={handleLogDirectoryChange}
                placeholder="/tmp/render_logs"
                className="w-full bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-5 py-3.5 text-[#1A1D23] dark:text-[#F5F7FA] placeholder-[#6B7280] dark:placeholder-[#8A92A5] focus:outline-none focus:border-[#5A1FA6] text-sm"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
              Render Engine Environment
            </label>
            <select
              value={formData.engine}
              onChange={handleEngineChange}
              className="w-full bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-5 py-3.5 text-[#1A1D23] dark:text-[#F5F7FA] focus:outline-none focus:border-[#5A1FA6] text-sm cursor-pointer"
            >
              <option>Houdini (Mantra/Karma)</option>
              <option>Maya (Arnold/V-Ray)</option>
              <option>Unreal Engine 5 (MRQ)</option>
              <option>Blender (Cycles)</option>
            </select>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
                Start Frame
              </label>
              <input
                type="number"
                value={formData.startFrame}
                onChange={handleStartFrameChange}
                className="w-full bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-4 py-3 text-[#1A1D23] dark:text-[#F5F7FA] text-center text-sm focus:outline-none focus:border-[#5A1FA6]"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
                End Frame
              </label>
              <input
                type="number"
                value={formData.endFrame}
                onChange={handleEndFrameChange}
                className="w-full bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-4 py-3 text-[#1A1D23] dark:text-[#F5F7FA] text-center text-sm focus:outline-none focus:border-[#5A1FA6]"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
                Priority
              </label>
              <select
                value={formData.priority}
                onChange={handlePriorityChange}
                className="w-full bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-4 py-3 text-[#1A1D23] dark:text-[#F5F7FA] focus:outline-none focus:border-[#5A1FA6] text-center text-sm cursor-pointer"
              >
                <option value="HIGH">HIGH</option>
                <option value="MED">MED</option>
                <option value="LOW">LOW</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[#6B7280] dark:text-[#8A92A5] font-bold text-sm">
              Render Command
            </label>
            <textarea
              value={formData.renderCommand}
              onChange={handleRenderCommandChange}
              rows={3}
              className="w-full resize-none bg-[#F7F8FA] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] rounded-xl px-5 py-3.5 text-[#1A1D23] dark:text-[#F5F7FA] placeholder-[#6B7280] dark:placeholder-[#8A92A5] focus:outline-none focus:border-[#5A1FA6] text-sm leading-relaxed"
            />
          </div>

          <div className="flex items-center justify-end gap-4 pt-5 border-t border-[#D7DBE3] dark:border-[#343B4D]/60 mt-8">
            <button
              type="button"
              onClick={onClose}
              className="bg-[#FFFFFF] dark:bg-[#161B24] border border-[#D7DBE3] dark:border-[#31384A] hover:bg-[#F1F3F6] dark:hover:bg-[#1F2330] text-[#6B7280] dark:text-[#8A92A5] hover:text-[#1A1D23] dark:hover:text-[#F5F7FA] px-5 py-3 rounded-xl text-sm transition-all cursor-pointer font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 bg-[#5A1FA6] hover:bg-[#6C2AC4] text-[#F5F7FA] font-bold px-6 py-3 rounded-xl text-sm shadow-lg shadow-[#5A1FA6]/30 transition-all cursor-pointer disabled:cursor-wait disabled:opacity-70"
            >
              <Play size={14} className="fill-current" />
              {isSubmitting ? "Queueing..." : "Queue Job"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
