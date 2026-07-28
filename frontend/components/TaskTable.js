"use client";
import { motion } from "framer-motion";

function buildRows(asIsTasks, toBeTasks) {
  const asIsById = new Map(asIsTasks.map((t) => [t.task_id, t]));
  const toBeById = new Map(toBeTasks.map((t) => [t.task_id, t]));

  const orderedIds = [];
  const seen = new Set();
  for (const t of asIsTasks) {
    if (!seen.has(t.task_id)) {
      seen.add(t.task_id);
      orderedIds.push(t.task_id);
    }
  }
  for (const t of toBeTasks) {
    if (!seen.has(t.task_id)) {
      seen.add(t.task_id);
      orderedIds.push(t.task_id);
    }
  }

  return orderedIds.map((id) => ({
    id,
    asIs: asIsById.get(id) || null,
    toBe: toBeById.get(id) || null,
  }));
}

function Hours({ value }) {
  if (value == null) return <span className="text-gray-200">—</span>;
  return <span className="font-mono">{value.toFixed(2)}h</span>;
}

function GroupHeader({ label, color, colSpan }) {
  return (
    <th
      colSpan={colSpan}
      className="text-center font-mono text-[10px] uppercase tracking-widest px-2 py-2"
      style={{ color, background: `${color}12` }}
    >
      {label}
    </th>
  );
}

export default function TaskTable({ asIs, toBe }) {
  if (!asIs || !toBe) return null;

  const rows = buildRows(asIs.tasks || [], toBe.tasks || []);

  if (rows.length === 0) {
    return <p className="text-sm text-gray-400 italic py-4">No task data available for this process.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border" style={{ borderColor: "var(--panel-border)" }}>
      <table className="w-full border-collapse text-sm min-w-[900px]">
        <thead>
          <tr>
            <th
              rowSpan={2}
              className="text-left font-medium text-xs uppercase tracking-wider text-gray-500 px-4 py-3 align-bottom sticky left-0"
              style={{ background: "var(--accent-soft)" }}
            >
              Task
            </th>
            <GroupHeader label="AS-IS" color="var(--baseline)" colSpan={4} />
            <GroupHeader label="TO-BE" color="var(--good)" colSpan={4} />
          </tr>
          <tr style={{ background: "var(--accent-soft)" }}>
            {["Process", "Rework", "Waiting", "Cost"].map((h) => (
              <th key={`as-${h}`} className="text-right font-medium text-[11px] text-gray-500 px-3 py-2 whitespace-nowrap">
                {h}
              </th>
            ))}
            {["Process", "Rework", "Waiting", "Cost"].map((h) => (
              <th key={`to-${h}`} className="text-right font-medium text-[11px] text-gray-500 px-3 py-2 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const name = row.asIs?.name || row.toBe?.name || row.id;
            const eliminated = row.asIs && !row.toBe;
            const added = !row.asIs && row.toBe;

            return (
              <motion.tr
                key={row.id}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: idx * 0.03 }}
                className="border-t hover:bg-gray-50/60 transition-colors"
                style={{ borderColor: "var(--panel-border)" }}
              >
                <td
                  className="px-4 py-2.5 text-gray-800 sticky left-0"
                  style={{ background: "var(--panel-bg)" }}
                >
                  {name}
                  {eliminated && (
                    <span className="ml-2 text-[10px] font-mono uppercase" style={{ color: "var(--critical)" }}>
                      removed
                    </span>
                  )}
                  {added && (
                    <span className="ml-2 text-[10px] font-mono uppercase" style={{ color: "var(--good)" }}>
                      new
                    </span>
                  )}
                </td>
                <td className="text-right px-3 py-2.5 text-gray-700"><Hours value={row.asIs?.process_time_hours} /></td>
                <td className="text-right px-3 py-2.5 text-gray-700"><Hours value={row.asIs?.rework_time_hours} /></td>
                <td className="text-right px-3 py-2.5 text-gray-700"><Hours value={row.asIs?.waiting_time_hours} /></td>
                <td className="text-right px-3 py-2.5 font-mono text-gray-700">
                  {row.asIs ? `$${row.asIs.cost.toFixed(2)}` : <span className="text-gray-200">—</span>}
                </td>
                <td className="text-right px-3 py-2.5 text-gray-700"><Hours value={row.toBe?.process_time_hours} /></td>
                <td className="text-right px-3 py-2.5 text-gray-700"><Hours value={row.toBe?.rework_time_hours} /></td>
                <td className="text-right px-3 py-2.5 text-gray-700"><Hours value={row.toBe?.waiting_time_hours} /></td>
                <td className="text-right px-3 py-2.5 font-mono text-gray-700">
                  {row.toBe ? `$${row.toBe.cost.toFixed(2)}` : <span className="text-gray-200">—</span>}
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
