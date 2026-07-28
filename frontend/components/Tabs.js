"use client";
import { motion, AnimatePresence } from "framer-motion";

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
