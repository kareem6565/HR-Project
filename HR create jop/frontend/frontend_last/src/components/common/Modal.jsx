import React, { useEffect, useRef, useId, useState } from "react";
import { X } from "lucide-react";

const MODAL_EXIT_MS = 160;

// Accessible confirm/dialog modal (UI-01 upgrade).
// Usage:
// <Modal open={open} title="Cancel interview?" onClose={close}>
//   ...body...
//   <div className="modal-actions">...</div>
// </Modal>
export default function Modal({ open, title, onClose, children, className = "" }) {
  const panelRef = useRef(null);
  const previouslyFocusedElementRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const [isMounted, setIsMounted] = useState(open);
  const [isClosing, setIsClosing] = useState(false);
  onCloseRef.current = onClose;

  const generatedId = useId();
  const titleId = `modal-title-${generatedId}`;

  useEffect(() => {
    if (open) {
      setIsMounted(true);
      setIsClosing(false);
      return undefined;
    }

    if (!isMounted) return undefined;

    setIsClosing(true);
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setIsMounted(false);
      setIsClosing(false);
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setIsMounted(false);
      setIsClosing(false);
    }, MODAL_EXIT_MS);

    return () => window.clearTimeout(timeoutId);
  }, [open, isMounted]);

  // Focus placement on open and restoration on actual close
  useEffect(() => {
    if (open) {
      previouslyFocusedElementRef.current = document.activeElement;
      panelRef.current?.focus();
    } else if (!isMounted && previouslyFocusedElementRef.current) {
      if (typeof previouslyFocusedElementRef.current.focus === "function") {
        previouslyFocusedElementRef.current.focus();
      }
      previouslyFocusedElementRef.current = null;
    }
  }, [open, isMounted]);

  // Restore focus if unmounted while still open
  useEffect(() => {
    return () => {
      if (
        previouslyFocusedElementRef.current &&
        typeof previouslyFocusedElementRef.current.focus === "function"
      ) {
        previouslyFocusedElementRef.current.focus();
      }
    };
  }, []);

  // Keyboard navigation & focus trap
  useEffect(() => {
    if (!isMounted) return undefined;

    const onKey = (e) => {
      if (e.key === "Escape") {
        if (isClosing) return;
        e.preventDefault();
        onCloseRef.current?.();
      } else if (e.key === "Tab") {
        if (!panelRef.current) return;
        const focusable = Array.from(
          panelRef.current.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (
          e.shiftKey &&
          (document.activeElement === first || document.activeElement === panelRef.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isMounted, isClosing]);

  if (!isMounted) return null;

  // Safe overlay dismiss: do not silently discard typed form data on accidental backdrop click
  const handleOverlayClick = (e) => {
    if (isClosing || e.target !== e.currentTarget) return;

    if (panelRef.current) {
      const inputs = panelRef.current.querySelectorAll(
        'textarea, input:not([type="hidden"]):not([type="button"]):not([type="submit"]):not([type="checkbox"]):not([type="radio"])'
      );
      for (const el of inputs) {
        if (el.value && el.value.trim().length > 0) {
          // Unsaved typed input detected: prevent accidental backdrop dismissal
          return;
        }
      }
    }
    onCloseRef.current?.();
  };

  return (
    <div className={`modal-overlay${isClosing ? " is-closing" : ""}`} onClick={handleOverlayClick}>
      <div
        ref={panelRef}
        className={`modal-panel ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 id={titleId}>{title}</h3>
          <button
            type="button"
            className="icon-btn"
            onClick={onClose}
            disabled={isClosing}
            aria-label="Close dialog"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
