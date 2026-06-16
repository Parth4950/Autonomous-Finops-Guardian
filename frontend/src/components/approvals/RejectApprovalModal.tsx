import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface RejectApprovalModalProps {
  open: boolean;
  resourceId: string | null;
  isSubmitting?: boolean;
  onClose: () => void;
  onConfirm: (notes: string) => void;
}

export function RejectApprovalModal({
  open,
  resourceId,
  isSubmitting = false,
  onClose,
  onConfirm,
}: RejectApprovalModalProps) {
  const [notes, setNotes] = useState("Requires additional validation.");

  useEffect(() => {
    if (open) {
      setNotes("Requires additional validation.");
    }
  }, [open, resourceId]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isSubmitting) onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, isSubmitting, onClose]);

  if (!open || !resourceId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close modal"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={() => !isSubmitting && onClose()}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="reject-modal-title"
        className="relative w-full max-w-md rounded-xl border border-border bg-[#161A1F] p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Reject Remediation</p>
            <h2 id="reject-modal-title" className="mt-1 text-lg font-semibold text-foreground">
              Block this action?
            </h2>
            <p className="mt-2 font-mono text-xs text-muted-foreground">{resourceId}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            disabled={isSubmitting}
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-5 space-y-2">
          <label htmlFor="reject-notes" className="text-sm font-medium text-foreground">
            Rejection notes
          </label>
          <textarea
            id="reject-notes"
            rows={4}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            disabled={isSubmitting}
            className="w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none ring-primary/40 placeholder:text-muted-foreground focus:ring-2"
            placeholder="Explain why this remediation should not proceed..."
          />
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" disabled={isSubmitting} onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="outline"
            disabled={isSubmitting}
            className="border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300"
            onClick={() => onConfirm(notes.trim() || "Rejected via Approval Center")}
          >
            {isSubmitting ? "Rejecting…" : "Reject"}
          </Button>
        </div>
      </div>
    </div>
  );
}
