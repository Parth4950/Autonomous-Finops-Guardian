import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

type ToastVariant = "default" | "success" | "error" | "info";

interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastItem extends ToastInput {
  id: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_STYLES: Record<ToastVariant, string> = {
  default: "border-border bg-card",
  success: "border-emerald-500/30 bg-emerald-500/10",
  error: "border-red-500/30 bg-red-500/10",
  info: "border-blue-500/30 bg-blue-500/10",
};

const VARIANT_ICONS: Record<ToastVariant, typeof Info> = {
  default: Info,
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

const VARIANT_ICON_COLORS: Record<ToastVariant, string> = {
  default: "text-foreground",
  success: "text-emerald-400",
  error: "text-red-400",
  info: "text-blue-400",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (input: ToastInput) => {
      const id = crypto.randomUUID();
      const variant = input.variant ?? "default";
      setToasts((current) => [...current, { ...input, id, variant }]);
      window.setTimeout(() => dismiss(id), 5000);
    },
    [dismiss]
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (title, description) => push({ title, description, variant: "success" }),
      error: (title, description) => push({ title, description, variant: "error" }),
      info: (title, description) => push({ title, description, variant: "info" }),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 top-4 z-[100] flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((item) => {
          const Icon = VARIANT_ICONS[item.variant];
          return (
            <div
              key={item.id}
              className={cn(
                "pointer-events-auto rounded-lg border p-4 shadow-lg",
                VARIANT_STYLES[item.variant]
              )}
            >
              <div className="flex items-start gap-3">
                <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", VARIANT_ICON_COLORS[item.variant])} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-foreground">{item.title}</p>
                  {item.description && (
                    <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  className="rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                  aria-label="Dismiss"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
