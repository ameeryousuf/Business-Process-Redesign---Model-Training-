"use client";
import { motion } from "framer-motion";

function Bar({ label, hours, maxHours, color, delay }) {
  const pct = maxHours > 0 ? Math.min(100, (hours / maxHours) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 text-xs text-gray-500">{label}</span>
      <div className="flex-1 h-2.5 rounded-full bg-gray-100 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          whileInView={{ width: `${pct}%` }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <span className="w-16 shrink-0 text-right font-mono text-xs text-gray-700">{hours.toFixed(2)}h</span>
    </div>
  );
}

function EfficiencyGauge({ pct, delay }) {
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(1, pct));

  return (
    <div className="relative w-32 h-32 shrink-0">
      <svg viewBox="0 0 110 110" className="w-full h-full -rotate-90">
        <circle cx="55" cy="55" r={radius} fill="none" stroke="var(--panel-border)" strokeWidth="9" />
        <motion.circle
          cx="55" cy="55" r={radius} fill="none"
          stroke="var(--accent)" strokeWidth="9" strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          whileInView={{ strokeDashoffset: circumference * (1 - clamped) }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-2xl font-semibold">{Math.round(clamped * 100)}%</span>
        <span className="text-[10px] uppercase tracking-wider text-gray-400">CTE</span>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="text-center">
      <p className="font-display text-lg font-semibold text-gray-900">{value}</p>
      <p className="text-[10px] uppercase tracking-wider text-gray-400 mt-0.5">{label}</p>
    </div>
  );
}

function Panel({ label, analysis, accentColor, delay }) {
  const maxHours = Math.max(analysis.cycle_time_hours, analysis.theoretical_cycle_time_hours, 0.01);
  const cost = analysis.cost_distribution
    ? analysis.cost_distribution.process_cost + analysis.cost_distribution.rework_cost + analysis.cost_distribution.waiting_cost
    : null;

  return (
    <motion.div
      className="rounded-2xl p-6 border card-shadow"
      style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay }}
    >
      <p
        className="font-mono text-xs uppercase tracking-widest px-2.5 py-1 rounded-md inline-block mb-5"
        style={{ color: accentColor, background: `${accentColor}18` }}
      >
        {label}
      </p>

      <div className="flex items-center gap-6">
        <EfficiencyGauge pct={analysis.cycle_time_efficiency} delay={delay + 0.1} />
        <div className="flex-1 space-y-3">
          <Bar label="Cycle Time" hours={analysis.cycle_time_hours} maxHours={maxHours} color="var(--baseline)" delay={delay + 0.1} />
          <Bar label="Theoretical CT" hours={analysis.theoretical_cycle_time_hours} maxHours={maxHours} color="var(--good)" delay={delay + 0.2} />
          <Bar label="Critical Path" hours={analysis.critical_path_hours} maxHours={maxHours} color="var(--slack)" delay={delay + 0.3} />
        </div>
      </div>

      <div
        className="grid grid-cols-3 gap-2 mt-6 pt-5 border-t"
        style={{ borderColor: "var(--panel-border)" }}
      >
        <Stat label="Cost" value={cost != null ? `$${cost.toFixed(2)}` : "—"} />
        <Stat label="Tasks" value={analysis.num_tasks ?? "—"} />
        <Stat label="Gateways" value={analysis.num_gateways ?? "—"} />
      </div>
    </motion.div>
  );
}

export default function CycleTimeAnalysis({ asIs, toBe }) {
  if (!asIs || !toBe) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Panel label="AS-IS" analysis={asIs} accentColor="var(--baseline)" delay={0} />
      <Panel label="TO-BE" analysis={toBe} accentColor="var(--good)" delay={0.1} />
    </div>
  );
}
