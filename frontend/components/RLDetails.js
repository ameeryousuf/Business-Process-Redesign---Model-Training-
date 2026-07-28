"use client";
import { motion } from "framer-motion";

function Card({ children, delay = 0, className = "" }) {
  return (
    <motion.div
      className={`rounded-2xl p-6 border card-shadow ${className}`}
      style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay }}
    >
      {children}
    </motion.div>
  );
}

function CardTitle({ children }) {
  return <p className="font-display text-sm font-semibold text-gray-900 mb-4">{children}</p>;
}

function HyperparamRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-mono text-gray-800">{value}</span>
    </div>
  );
}

function StepQValues({ step, delay }) {
  const values = step.q_values || [];
  const maxAbs = Math.max(...values.map((v) => Math.abs(v.q_value)), 0.0001);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.3, delay }}
      className="py-3 border-t first:border-t-0"
      style={{ borderColor: "var(--panel-border)" }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-gray-400">Step {String(step.step).padStart(2, "0")}</span>
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-md"
          style={{ color: "var(--accent)", background: "var(--accent-soft)" }}
        >
          {step.heuristic}
        </span>
      </div>
      {step.state && (
        <p className="text-[11px] text-gray-400 mb-2">
          State: time=<span className="text-gray-600">{step.state.time_bucket}</span>, cost=
          <span className="text-gray-600">{step.state.cost_bucket}</span>
          {step.state.eligible_heuristics?.length > 0 && (
            <> · eligible: {step.state.eligible_heuristics.join(", ")}</>
          )}
        </p>
      )}
      <div className="space-y-1.5">
        {values.map((v) => {
          const widthPct = (Math.abs(v.q_value) / maxAbs) * 100;
          return (
            <div key={v.action} className="flex items-center gap-2">
              <span
                className="w-40 shrink-0 text-xs truncate"
                style={{ color: v.chosen ? "var(--accent)" : "var(--text-muted)", fontWeight: v.chosen ? 600 : 400 }}
                title={v.label}
              >
                {v.chosen ? "→ " : ""}
                {v.label}
              </span>
              <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(widthPct, v.q_value !== 0 ? 3 : 0)}%`,
                    background: v.chosen ? "var(--accent)" : "var(--panel-border)"
                  }}
                />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-[11px] text-gray-400">
                {v.q_value.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

export default function RLDetails({ rlDetails, trace }) {
  if (!rlDetails) return null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card delay={0}>
          <CardTitle>Algorithm</CardTitle>
          <p className="text-sm text-gray-600 leading-relaxed">{rlDetails.algorithm}</p>
          <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--panel-border)" }}>
            <Stat label="Q-Table Size" value={rlDetails.q_table_size?.toLocaleString()} />
          </div>
        </Card>

        <Card delay={0.05}>
          <CardTitle>Hyperparameters</CardTitle>
          <HyperparamRow label="Learning rate (α)" value={rlDetails.hyperparameters.learning_rate_alpha} />
          <HyperparamRow label="Discount factor (γ)" value={rlDetails.hyperparameters.discount_factor_gamma} />
          <HyperparamRow label="Epsilon start" value={rlDetails.hyperparameters.epsilon_start} />
          <HyperparamRow label="Epsilon end" value={rlDetails.hyperparameters.epsilon_end} />
          <HyperparamRow
            label="Epsilon decay"
            value={`${Math.round(rlDetails.hyperparameters.epsilon_decay_fraction_of_episodes * 100)}% of episodes`}
          />
          <HyperparamRow label="Training episodes" value={rlDetails.hyperparameters.training_episodes.toLocaleString()} />
        </Card>

        <Card delay={0.1}>
          <CardTitle>State Space</CardTitle>
          <p className="text-sm text-gray-600 leading-relaxed">{rlDetails.state_space.description}</p>
          <div className="flex gap-2 mt-4 flex-wrap">
            {rlDetails.state_space.time_buckets.map((b) => (
              <span key={`t-${b}`} className="text-[11px] font-mono px-2 py-0.5 rounded-md" style={{ background: "var(--baseline-soft)", color: "var(--baseline)" }}>
                time:{b}
              </span>
            ))}
            {rlDetails.state_space.cost_buckets.map((b) => (
              <span key={`c-${b}`} className="text-[11px] font-mono px-2 py-0.5 rounded-md" style={{ background: "var(--good-soft)", color: "var(--good)" }}>
                cost:{b}
              </span>
            ))}
          </div>
        </Card>
      </div>

      <Card delay={0.15}>
        <CardTitle>Reward Function</CardTitle>
        <p className="font-mono text-sm px-3 py-2 rounded-lg mb-3" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
          {rlDetails.reward_function.formula}
        </p>
        <p className="text-sm text-gray-600 leading-relaxed mb-3">{rlDetails.reward_function.description}</p>
        <p className="text-xs text-gray-400 leading-relaxed">{rlDetails.reward_function.rejection_rule}</p>
        <p className="font-mono text-xs text-gray-400 mt-4 pt-4 border-t" style={{ borderColor: "var(--panel-border)" }}>
          Update rule: {rlDetails.update_rule}
        </p>
      </Card>

      <Card delay={0.2}>
        <CardTitle>Action Space</CardTitle>
        <div className="flex flex-wrap gap-2">
          {rlDetails.action_space.map((a) => (
            <span
              key={a.action}
              className="text-xs font-medium px-2.5 py-1 rounded-md"
              style={{ color: "var(--accent)", background: "var(--accent-soft)" }}
            >
              {a.label}
            </span>
          ))}
        </div>
      </Card>

      {trace && trace.length > 0 && (
        <Card delay={0.25}>
          <CardTitle>Per-Step Q-Value Comparison</CardTitle>
          <p className="text-xs text-gray-400 mb-3">
            At each decision point, the agent picked the eligible action with the highest learned Q-value for
            that state. Bars show every eligible alternative considered.
          </p>
          {trace.map((step, idx) => (
            <StepQValues key={step.step} step={step} delay={idx * 0.03} />
          ))}
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <p className="font-display text-2xl font-semibold text-gray-900">{value}</p>
      <p className="text-[10px] uppercase tracking-wider text-gray-400 mt-0.5">{label}</p>
    </div>
  );
}
