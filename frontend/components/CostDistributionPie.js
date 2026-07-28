"use client";
import { motion } from "framer-motion";

const SEGMENT_META = [
  { key: "process_cost", label: "Process", color: "var(--accent)" },
  { key: "rework_cost", label: "Rework", color: "var(--critical)" },
  { key: "waiting_cost", label: "Waiting", color: "var(--slack)" },
];

function Donut({ distribution, delay }) {
  const size = 150;
  const radius = 55;
  const circumference = 2 * Math.PI * radius;
  const segments = SEGMENT_META.map((meta) => ({ ...meta, value: distribution?.[meta.key] || 0 }));
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;

  let cumulativeLen = 0;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--panel-border)" strokeWidth="20" />
        {segments.map((seg, idx) => {
          const arcLen = (seg.value / total) * circumference;
          const dashoffset = -cumulativeLen;
          cumulativeLen += arcLen;

          if (arcLen <= 0) return null;

          return (
            <motion.circle
              key={seg.key}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth="20"
              strokeDasharray={`${arcLen} ${circumference}`}
              initial={{ strokeDashoffset: circumference, opacity: 0 }}
              whileInView={{ strokeDashoffset: dashoffset, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, delay: delay + idx * 0.12, ease: [0.22, 1, 0.36, 1] }}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-lg font-semibold">${total.toFixed(2)}</span>
        <span className="text-[10px] uppercase tracking-wider text-gray-400">Total Cost</span>
      </div>
    </div>
  );
}

function Legend({ distribution }) {
  const total = SEGMENT_META.reduce((sum, s) => sum + (distribution?.[s.key] || 0), 0) || 1;

  return (
    <div className="flex-1 space-y-2.5 min-w-[140px]">
      {SEGMENT_META.map((meta) => {
        const value = distribution?.[meta.key] || 0;
        const pct = total > 0 ? (value / total) * 100 : 0;
        return (
          <div key={meta.key} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2 text-gray-600">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: meta.color }} />
              {meta.label}
            </span>
            <span className="font-mono text-xs text-gray-500">
              ${value.toFixed(2)} <span className="text-gray-300">({pct.toFixed(1)}%)</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Panel({ label, distribution, accentColor, delay }) {
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
      <div className="flex items-center gap-6 flex-wrap">
        <Donut distribution={distribution} delay={delay} />
        <Legend distribution={distribution} />
      </div>
    </motion.div>
  );
}

export default function CostDistributionPie({ asIs, toBe }) {
  if (!asIs || !toBe) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Panel label="AS-IS" distribution={asIs.cost_distribution} accentColor="var(--baseline)" delay={0} />
      <Panel label="TO-BE" distribution={toBe.cost_distribution} accentColor="var(--good)" delay={0.1} />
    </div>
  );
}
