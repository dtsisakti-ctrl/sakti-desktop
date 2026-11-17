import { cloneElement, createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactElement, type ReactNode } from "react";
import { ApiError } from "../api/client";
import { t, tx } from "../i18n";

// ------------------------------------------------------------------ status marks
export function AttemptStatus({ status }: { status: string }) {
  return <span className={`status s-${status}`} title={status}>{tx("status", status)}</span>;
}
export function ExamStatus({ status }: { status: string }) {
  return <span className={`status s-${status}`} title={status}>{tx("exam", status)}</span>;
}
export function Severity({ level }: { level: string }) {
  return <span className={`sev ${level}`}>{tx("sev", level)}</span>;
}

// ------------------------------------------------------------------ errors & empty states
export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return t("error.network");
    if (e.status === 403) return `${t("error.forbidden")} (${e.message})`;
    return `${e.message} (${e.code})`;
  }
  return String(e);
}

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const details = error instanceof ApiError && Array.isArray(error.details) ? error.details : null;
  return (
    <div className="notice error" role="alert">
      {errorText(error)}
      {details && (
        <ul>
          {details.map((d, i) => (
            <li key={i}>{typeof d === "object" && d ? Object.values(d as object).join(": ") : String(d)}</li>
          ))}
        </ul>
      )}
      {onRetry && (
        <div style={{ marginTop: "0.5rem" }}>
          <button className="btn btn-sm" onClick={onRetry}>{t("common.retry")}</button>
        </div>
      )}
    </div>
  );
}

export function Empty({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {hint && <p>{hint}</p>}
      {children}
    </div>
  );
}

export function Loading() {
  return <p className="muted" aria-live="polite">{t("common.loading")}</p>;
}

// ------------------------------------------------------------------ modal (native <dialog>)
export function Modal({ title, open, onClose, children, footer }: {
  title: string; open: boolean; onClose: () => void; children: ReactNode; footer: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="modal" onClose={onClose} aria-labelledby="modal-title">
      {open && (
        <>
          <div className="modal-body">
            <h3 id="modal-title">{title}</h3>
            {children}
          </div>
          <div className="modal-foot">{footer}</div>
        </>
      )}
    </dialog>
  );
}

// ------------------------------------------------------------------ toasts
interface Toast {
  id: number;
  text: string;
  kind: "ok" | "error";
}
const ToastCtx = createContext<(text: string, kind?: "ok" | "error") => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, text, kind }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {items.map((x) => (
          <div key={x.id} className={`toast ${x.kind === "error" ? "error" : ""}`}>{x.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

// ------------------------------------------------------------------ form field
/** Label + control + hint. The hint is linked with aria-describedby so it is not part of the
 *  field's accessible name (screen readers announce "Mulai jendela", then the hint). */
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactElement }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const control = cloneElement(children as ReactElement<Record<string, unknown>>, {
    id,
    "aria-describedby": hint ? hintId : undefined,
  });
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {control}
      {hint && <span id={hintId} className="hint">{hint}</span>}
    </div>
  );
}
