"use client";
import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const ROLE_META = {
  R: { label: "Responsible", var: "--raci-r" },
  A: { label: "Accountable", var: "--raci-a" },
  C: { label: "Consulted", var: "--raci-c" },
  I: { label: "Informed", var: "--raci-i" },
};

function RoleBadge({ role, pct }) {
  if (!role) return <span className="text-gray-200">&middot;</span>;
  const meta = ROLE_META[role] || ROLE_META.I;
  return (
    <span
      title={`${meta.label}${pct != null ? ` — ${pct}% allocation` : ""}`}
      className="inline-flex items-center justify-center w-6 h-6 rounded-md text-[11px] font-semibold cursor-default"
      style={{ color: `var(${meta.var})`, background: `color-mix(in srgb, var(${meta.var}) 14%, transparent)` }}
    >
      {role}
    </span>
  );
}

function buildMatrix(raciMatrix) {
  const people = [];
  const seen = new Set();

  for (const row of raciMatrix) {
    for (const a of row.assignments) {
      if (a.name && !seen.has(a.name)) {
        seen.add(a.name);
        people.push(a.name);
      }
    }
  }

  const rows = raciMatrix
    .filter((row) => !row.is_subprocess)
    .map((row) => {
      const byPerson = {};
      for (const a of row.assignments) {
        byPerson[a.name] = a;
      }
      return { task: row, byPerson };
    });

  return { people, rows };
}

export default function RaciMatrix({ asIs, toBe }) {
  const [mode, setMode] = useState("as_is");

  if (!asIs || !toBe) return null;

  const analysis = mode === "as_is" ? asIs : toBe;
  const { people, rows } = useMemo(() => buildMatrix(analysis.raci_matrix || []), [analysis]);

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
                  layoutId="raci-toggle"
                  className="absolute inset-0 rounded-md"
                  style={{ background: key === "as_is" ? "var(--baseline)" : "var(--good)" }}
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <span className="relative z-10">{key === "as_is" ? "AS-IS" : "TO-BE"}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {Object.entries(ROLE_META).map(([code, meta]) => (
            <div key={code} className="flex items-center gap-1.5">
              <span
                className="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold"
                style={{ color: `var(${meta.var})`, background: `color-mix(in srgb, var(${meta.var}) 14%, transparent)` }}
              >
                {code}
              </span>
              <span className="text-[11px] text-gray-400">{meta.label}</span>
            </div>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="overflow-x-auto rounded-xl border"
          style={{ borderColor: "var(--panel-border)" }}
        >
          {rows.length === 0 || people.length === 0 ? (
            <p className="text-sm text-gray-400 italic p-6">No resource-assignment data available for this process.</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr style={{ background: "var(--accent-soft)" }}>
                  <th className="text-left font-medium text-xs uppercase tracking-wider text-gray-500 px-4 py-3 sticky left-0" style={{ background: "var(--accent-soft)" }}>
                    Task
                  </th>
                  {people.map((person) => (
                    <th key={person} className="text-center font-medium text-xs text-gray-600 px-3 py-3 whitespace-nowrap">
                      {person}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <motion.tr
                    key={row.task.task_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.3, delay: idx * 0.03 }}
                    className="border-t hover:bg-gray-50/60 transition-colors"
                    style={{ borderColor: "var(--panel-border)" }}
                  >
                    <td className="px-4 py-2.5 text-gray-800 sticky left-0 bg-white" style={{ background: "var(--panel-bg)" }}>
                      {row.task.name}
                    </td>
                    {people.map((person) => {
                      const a = row.byPerson[person];
                      return (
                        <td key={person} className="text-center px-3 py-2.5">
                          <RoleBadge role={a?.role} pct={a?.time_allocation_percentage} />
                        </td>
                      );
                    })}
                  </motion.tr>
                ))}
              </tbody>
            </table>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
