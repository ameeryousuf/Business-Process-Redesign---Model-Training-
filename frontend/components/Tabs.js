"use client";
import { motion, AnimatePresence } from "framer-motion";

/**
 * `tabs`: [{ id, label, content }]. Renders a horizontally-scrollable pill tab bar
 * (mirrors the AS-IS/TO-BE toggle pattern already used elsewhere) plus an animated
 * panel switch below it. Controlled: the caller owns `active`/`onActiveChange`.
 *
 * IMPORTANT: the caller must render this with `key={active}` (see app/page.js).
 * In this app's current React/Next canary, a plain prop-driven update to this
 * component's rendered children sometimes never commits (verified via React
 * internals: the work-in-progress fiber computes the new tree correctly, but it
 * never gets promoted to `current`, leaving the DOM stuck on stale content even
 * though the parent's own re-render commits fine). Keying by `active` forces a
 * full remount on every tab switch instead of an in-place update, which sidesteps
 * the bug reliably. Don't remove the key without re-verifying tab switches work.
 */
export default function Tabs({ tabs, active, onActiveChange }) {
  const activeTab = tabs.find((t) => t.id === active) || tabs[0];

  return (
    <div>
      <div
        className="flex items-center gap-1 mb-6 overflow-x-auto rounded-xl border p-1"
        style={{ borderColor: "var(--panel-border)", background: "var(--panel-bg)" }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onActiveChange(tab.id)}
            className="relative px-4 py-2 text-sm font-medium rounded-lg transition-colors whitespace-nowrap shrink-0"
            style={{ color: active === tab.id ? "#fff" : "var(--text-muted)" }}
          >
            {active === tab.id && (
              <motion.span
                layoutId="main-tab-indicator"
                className="absolute inset-0 rounded-lg"
                style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-2))" }}
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative z-10">{tab.label}</span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab?.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.25 }}
        >
          {activeTab?.content}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
