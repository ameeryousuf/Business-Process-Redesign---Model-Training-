"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function CriticalPathView({ asIs, toBe }) {
  const [mode, setMode] = useState("as_is");

  if (!asIs || !toBe) return null;

  const analysis = mode === "as_is" ? asIs : toBe;
  const path = analysis.critical_path || [];
  const maxEf = path.length ? path[path.length - 1].early_finish : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div className="inline-flex rounded-lg p-1 bg-gray-100">
          {["as_is", "to_be"].map((key) => (
            <button
              key={key}
              onClick={() => setMode(key)}
              className="relative px-4 py-1.5 text-xs font-medium rounded-md transition-colors"
              style={{ color: mode === key ? "#fff" : "var(--text-muted)" }}
            >
              {mode === key && (
                <motion.span
                  layoutId="critical-path-toggle"
                  className="absolute inset-0 rounded-md"
                  style={{ background: key === "as_is" ? "var(--baseline)" : "var(--good)" }}
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <span className="relative z-10">{key === "as_is" ? "AS-IS" : "TO-BE"}</span>
            </button>
          ))}
        </div>
        <p className="font-mono text-xs text-gray-400">
          Total: <span className="text-gray-700">{analysis.critical_path_hours}h</span>
        </p>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
          className="overflow-x-auto"
        >
          <div className="min-w-[720px] space-y-2.5">
            {path.map((step, idx) => {
              const widthPct = maxEf > 0 ? ((step.early_finish - step.early_start) / maxEf) * 100 : 0;
              const offsetPct = maxEf > 0 ? (step.early_start / maxEf) * 100 : 0;

              return (
                <motion.div
                  key={step.task_id + idx}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.35, delay: idx * 0.04 }}
                  className="flex items-center gap-3"
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: step.is_critical ? "var(--critical)" : "var(--slack)" }}
                  />
                  <span className="w-48 shrink-0 text-sm text-gray-700 truncate" title={step.name}>
                    {step.name}
                  </span>
                  <div className="flex-1 h-6 rounded-md bg-gray-50 relative overflow-hidden">
                    <motion.div
                      className="absolute top-0 h-full rounded-md flex items-center px-2"
                      style={{
                        left: `${offsetPct}%`,
                        background: step.is_critical ? "var(--critical-soft)" : "var(--slack-soft)",
                        border: `1px solid ${step.is_critical ? "var(--critical)" : "var(--slack)"}`,
                      }}
                      initial={{ width: 0 }}
                      whileInView={{ width: `${Math.max(widthPct, 2)}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.6, delay: 0.1 + idx * 0.04 }}
                    >
                      <span
                        className="font-mono text-[10px] whitespace-nowrap"
                        style={{ color: step.is_critical ? "var(--critical)" : "var(--slack)" }}
                      >
                        {step.processing_time_hours}h
                      </span>
                    </motion.div>
                  </div>
                  <span className="w-14 shrink-0 text-right font-mono text-[11px] text-gray-400">
                    {step.slack > 0 ? `+${step.slack}h` : "0h"}
                  </span>
                </motion.div>
              );
            })}

            {path.length === 0 && (
              <p className="text-sm text-gray-400 italic py-4">No critical path could be determined for this process.</p>
            )}
          </div>
        </motion.div>
      </AnimatePresence>

      <div className="flex items-center gap-5 mt-5 pt-4 border-t" style={{ borderColor: "var(--panel-border)" }}>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ background: "var(--critical)" }} />
          <span className="text-xs text-gray-400">Critical (zero slack)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ background: "var(--slack)" }} />
          <span className="text-xs text-gray-400">Has slack</span>
        </div>
      </div>
    </div>
  );
}
