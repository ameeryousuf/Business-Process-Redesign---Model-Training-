"use client";
import { useState, useRef, useEffect, Fragment } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import BpmnDiagram from "@/components/BpmnDiagram";
import MotionSection from "@/components/MotionSection";
import CycleTimeAnalysis from "@/components/CycleTimeAnalysis";
import CriticalPathView from "@/components/CriticalPathView";
import RaciMatrix from "@/components/RaciMatrix";
import CostDistributionPie from "@/components/CostDistributionPie";
import TaskTable from "@/components/TaskTable";
import RLDetails from "@/components/RLDetails";
import Tabs from "@/components/Tabs";
import { runRedesign } from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";

const PENDING_BUNDLE_KEY = "pending_redesign_bundle";

export default function Home() {
  const authed = useAuthGuard();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [sourceLabel, setSourceLabel] = useState(null);
  const [expandedStep, setExpandedStep] = useState(null);
  const [activeResultTab, setActiveResultTab] = useState("flow");
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!authed) return;

    const raw = sessionStorage.getItem(PENDING_BUNDLE_KEY);
    if (!raw) return;

    sessionStorage.removeItem(PENDING_BUNDLE_KEY);

    let bundle;
    try {
      bundle = JSON.parse(raw);
    } catch (err) {
      setError("Could not read the fetched process data.");
      return;
    }

    setSourceLabel(bundle?.process?.process_name || `Process ${bundle?.process?.process_id ?? ""}`);
    setLoading(true);
    setError(null);

    runRedesign(bundle)
      .then((data) => {
        if (data.error) {
          setError(`Backend error: ${data.error}`);
        } else {
          setResult(data);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [authed]);

  if (!authed) {
    return null;
  }

  const handleFileSelect = (selectedFile) => {
    if (!selectedFile) return;

    const validExtensions = [".bpmn", ".xml", ".json"];
    const isValid = validExtensions.some((ext) =>
      selectedFile.name.toLowerCase().endsWith(ext)
    );

    if (!isValid) {
      setError("Please upload a .bpmn, .xml, or .json (SaaS process export) file.");
      return;
    }

    setFile(selectedFile);
    setResult(null);
    setError(null);
    setExpandedStep(null);
  };

  const handleFileChange = (e) => handleFileSelect(e.target.files[0]);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files[0]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleSubmit = async () => {
    if (!file) {
      setError("Please select a .bpmn file first.");
      return;
    }

    setLoading(true);
    setError(null);

    const isJson = file.name.toLowerCase().endsWith(".json");

    try {
      let response;

      if (isJson) {
        let processData;
        try {
          processData = JSON.parse(await file.text());
        } catch (parseErr) {
          throw new Error("Could not parse this file as JSON. Is it a valid SaaS process export?");
        }

        response = await fetch("http://127.0.0.1:8000/redesign/process", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(processData),
        });
      } else {
        const formData = new FormData();
        formData.append("file", file);

        response = await fetch("http://127.0.0.1:8000/redesign", {
          method: "POST",
          body: formData,
        });
      }

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}. Is the backend running?`);
      }

      const data = await response.json();

      if (data.error) {
        setError(`Backend error: ${data.error}`);
      } else {
        setResult(data);
      }
    } catch (err) {
      if (err.message.includes("fetch")) {
        setError("Could not reach the backend server. Make sure it's running at http://127.0.0.1:8000.");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setExpandedStep(null);
    setSourceLabel(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDownloadToBe = () => {
    if (!result?.to_be_bpmn_xml) return;

    const blob = new Blob([result.to_be_bpmn_xml], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "redesigned_process.bpmn";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const toggleStep = (stepNum) => {
    setExpandedStep(expandedStep === stepNum ? null : stepNum);
  };

  const resultTabs = result
    ? [
        {
          id: "flow",
          label: "Flow Analysis",
          content: (
            <div className="space-y-6">
              <div
                className="rounded-2xl p-7 border card-shadow"
                style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
              >
                <SectionHeading title="Cycle Time Analysis" subtitle="Cycle Time, Theoretical Cycle Time, Cycle Time Efficiency, Cost — Ch.7.1.1-7.1.2" noMarginTop />
                <CycleTimeAnalysis asIs={result.as_is_analysis} toBe={result.to_be_analysis} />
              </div>

              <div
                className="rounded-2xl p-7 border card-shadow"
                style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
              >
                <SectionHeading title="Cost Distribution" subtitle="Process vs. rework vs. waiting labor cost" noMarginTop />
                <CostDistributionPie asIs={result.as_is_analysis} toBe={result.to_be_analysis} />
              </div>

              <div
                className="rounded-2xl p-7 border card-shadow"
                style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
              >
                <SectionHeading title="Task Breakdown" subtitle="Process / rework / waiting time and cost, per task" noMarginTop />
                <TaskTable asIs={result.as_is_analysis} toBe={result.to_be_analysis} />
              </div>
            </div>
          ),
        },
        {
          id: "critical_path",
          label: "Critical Path",
          content: (
            <div
              className="rounded-2xl p-7 border card-shadow"
              style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
            >
              <SectionHeading title="Critical Path" subtitle="Forward/backward pass (ES, EF, LS, LF) along the dominant path — Ch.7.1.3" noMarginTop />
              <CriticalPathView asIs={result.as_is_analysis} toBe={result.to_be_analysis} />
            </div>
          ),
        },
        {
          id: "raci",
          label: "RACI Matrix",
          content: (
            <div
              className="rounded-2xl p-7 border card-shadow"
              style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
            >
              <SectionHeading title="RACI Matrix" subtitle="Responsible / Accountable / Consulted / Informed, per task" noMarginTop />
              <RaciMatrix asIs={result.as_is_analysis} toBe={result.to_be_analysis} />
            </div>
          ),
        },
        {
          id: "bpmn",
          label: "BPMN Diagram",
          content: (
            <div className="space-y-6">
              <div
                className="rounded-2xl p-7 border card-shadow"
                style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
              >
                <div className="flex items-center justify-between mb-4">
                  <p
                    className="font-mono text-xs uppercase tracking-widest px-2.5 py-1 rounded-md"
                    style={{ color: "var(--baseline)", background: "var(--baseline-soft)" }}
                  >
                    AS-IS
                  </p>
                </div>
                <BpmnDiagram xml={result.as_is_bpmn_xml} height={520} />
              </div>

              <div
                className="rounded-2xl p-7 border card-shadow"
                style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
              >
                <div className="flex items-center justify-between mb-4">
                  <p
                    className="font-mono text-xs uppercase tracking-widest px-2.5 py-1 rounded-md"
                    style={{ color: "var(--good)", background: "var(--good-soft)" }}
                  >
                    TO-BE
                  </p>
                  <button
                    onClick={handleDownloadToBe}
                    className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-md font-medium transition-colors"
                  >
                    Download BPMN
                  </button>
                </div>
                <BpmnDiagram xml={result.to_be_bpmn_xml} height={520} />
              </div>
            </div>
          ),
        },
        {
          id: "trace",
          label: "Redesign Trace",
          content: (
            <div
              className="rounded-2xl p-7 border overflow-x-auto card-shadow"
              style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
            >
              <SectionHeading title="Redesign Trace" subtitle="Each heuristic the agent applied, in order" noMarginTop />

              <table className="w-full border-collapse min-w-[760px] mt-2">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                    <th className="text-left text-xs uppercase tracking-wider text-gray-400 font-medium pb-3 pr-4 w-10">
                      #
                    </th>
                    <th className="text-left text-xs uppercase tracking-wider text-gray-400 font-medium pb-3 pr-4">
                      Action
                    </th>
                    <th className="text-left text-xs uppercase tracking-wider text-gray-400 font-medium pb-3 pr-4">
                      Applied To
                    </th>
                    <th className="text-right text-xs uppercase tracking-wider text-gray-400 font-medium pb-3 pr-4">
                      Time
                    </th>
                    <th className="text-right text-xs uppercase tracking-wider text-gray-400 font-medium pb-3 pr-4">
                      Cost
                    </th>
                    <th className="text-right text-xs uppercase tracking-wider text-gray-400 font-medium pb-3 w-16">
                      Why
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.redesign_trace.map((step, idx) => (
                    <Fragment key={step.step}>
                      <motion.tr
                        initial={{ opacity: 0 }}
                        whileInView={{ opacity: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.3, delay: idx * 0.05 }}
                        style={{
                          borderBottom:
                            expandedStep === step.step
                              ? "none"
                              : idx !== result.redesign_trace.length - 1
                                ? "1px solid var(--panel-border)"
                                : "none",
                        }}
                      >
                        <td className="py-3.5 pr-4 font-mono text-xs text-gray-300 align-top">
                          {String(step.step).padStart(2, "0")}
                        </td>
                        <td className="py-3.5 pr-4 align-top">
                          <span
                            className="inline-block text-xs font-medium px-2.5 py-1 rounded-md"
                            style={{ color: "var(--accent)", background: "var(--accent-soft)" }}
                          >
                            {step.heuristic}
                          </span>
                        </td>
                        <td className="py-3.5 pr-4 text-sm text-gray-700 align-top">
                          {step.applied_to}
                        </td>
                        <td className="py-3.5 pr-4 text-right align-top">
                          <div className="font-mono text-sm text-gray-900">
                            {step.time_before}h → {step.time_after}h
                          </div>
                          {step.time_delta_pct !== 0 && (
                            <div
                              className="text-xs font-mono"
                              style={{ color: step.time_delta_pct > 0 ? "var(--good)" : "var(--critical)" }}
                            >
                              {step.time_delta_pct > 0 ? "−" : "+"}
                              {Math.abs(step.time_delta_pct)}%
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 pr-4 text-right align-top">
                          <div className="font-mono text-sm text-gray-900">
                            ${step.cost_before} → ${step.cost_after}
                          </div>
                          {step.cost_delta_pct !== 0 && (
                            <div
                              className="text-xs font-mono"
                              style={{ color: step.cost_delta_pct > 0 ? "var(--good)" : "var(--critical)" }}
                            >
                              {step.cost_delta_pct > 0 ? "−" : "+"}
                              {Math.abs(step.cost_delta_pct)}%
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 text-right align-top">
                          <button
                            onClick={() => toggleStep(step.step)}
                            className="text-xs font-medium px-2.5 py-1 rounded-md hover:bg-gray-100 transition-colors"
                            style={{ color: "var(--accent)" }}
                          >
                            {expandedStep === step.step ? "Hide" : "Show"}
                          </button>
                        </td>
                      </motion.tr>
                      <AnimatePresence>
                        {expandedStep === step.step && (
                          <motion.tr
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            style={{
                              borderBottom:
                                idx !== result.redesign_trace.length - 1
                                  ? "1px solid var(--panel-border)"
                                  : "none",
                            }}
                          >
                            <td></td>
                            <td colSpan={5} className="pb-4 pr-4">
                              <div
                                className="text-sm text-gray-600 leading-relaxed p-4 rounded-lg"
                                style={{ background: "var(--accent-soft)" }}
                              >
                                {step.reason}
                              </div>
                            </td>
                          </motion.tr>
                        )}
                      </AnimatePresence>
                    </Fragment>
                  ))}
                </tbody>
              </table>

              <p
                className="text-xs text-gray-400 mt-5 pt-4 italic"
                style={{ borderTop: "1px solid var(--panel-border)" }}
              >
                {result.stopping_reason}
              </p>
            </div>
          ),
        },
        {
          id: "rl_details",
          label: "RL Details",
          content: <RLDetails rlDetails={result.rl_details} trace={result.redesign_trace} />,
        },
      ]
    : [];

  return (
    <main className="min-h-screen">
      <div className="border-b" style={{ borderColor: "var(--panel-border)" }}>
        <div className="px-6 md:px-16 py-14 md:py-20">
          <div className="flex items-center justify-between mb-4">
            <motion.p
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="font-mono text-xs uppercase tracking-[0.2em] text-gray-400"
            >
              RL-Driven Process Optimization
            </motion.p>
            <Link
              href="/processes"
              className="text-xs text-gray-400 hover:text-gray-600 underline underline-offset-2"
            >
              ← Back to Processes
            </Link>
          </div>
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="font-display text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05]"
          >
            BPM Redesign <span className="gradient-text">Engine</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.12 }}
            className="mt-5 max-w-2xl text-gray-500 text-base md:text-lg"
          >
            Upload a process — BPMN 2.0 or a SaaS process export — and get a quantitative,
            literature-grounded redesign: cycle time, theoretical cycle time, cycle time
            efficiency, critical path, and RACI, before and after.
          </motion.p>
        </div>
      </div>

      <div className="px-6 md:px-16 py-10 space-y-6 max-w-6xl mx-auto">
        {sourceLabel && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border p-4 flex items-center justify-between"
            style={{ background: "var(--accent-soft)", borderColor: "var(--panel-border)" }}
          >
            <p className="text-sm text-gray-700">
              <span className="font-medium">Loaded live from Digital Twin Server:</span> {sourceLabel}
            </p>
            <button
              onClick={handleReset}
              className="text-xs text-gray-500 hover:text-gray-700 underline underline-offset-2"
            >
              Upload a file instead
            </button>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.18 }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className="rounded-2xl p-8 border-2 border-dashed transition-colors card-shadow"
          style={{
            borderColor: isDragging ? "var(--accent)" : "var(--panel-border)",
            background: isDragging ? "var(--accent-soft)" : "var(--panel-bg)",
          }}
        >
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-center md:text-left">
              <p className="font-medium text-gray-900">
                {file ? file.name : "Drop a .bpmn or SaaS process .json file here, or browse to select one"}
              </p>
              <p className="text-gray-400 text-sm mt-1">
                Accepts BPMN 2.0 XML process files, or a SaaS process JSON export
              </p>
            </div>

            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".bpmn,.xml,.json"
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="px-4 py-2.5 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium cursor-pointer hover:bg-gray-200 transition-colors"
              >
                Choose File
              </label>

              <motion.button
                whileHover={{ scale: loading || !file ? 1 : 1.02 }}
                whileTap={{ scale: loading || !file ? 1 : 0.98 }}
                onClick={handleSubmit}
                disabled={loading || !file}
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-colors inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-2))" }}
              >
                {loading && (
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                {loading ? "Processing" : "Redesign Process"}
              </motion.button>

              {(file || result) && !loading && (
                <button
                  onClick={handleReset}
                  className="text-gray-400 hover:text-gray-600 text-sm underline underline-offset-2"
                >
                  Reset
                </button>
              )}
            </div>
          </div>
        </motion.div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="rounded-2xl border border-red-200 bg-red-50 p-4 overflow-hidden"
            >
              <p className="text-red-700 font-medium text-sm">Something went wrong</p>
              <p className="text-red-600/80 text-sm mt-1">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {result && (
          <div className="space-y-10 pt-2">
            <MotionSection>
              <div
                className="rounded-2xl p-7 border card-shadow"
                style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
              >
                <p className="font-mono text-xs uppercase tracking-widest text-gray-400 mb-5">
                  Redesign Impact
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                  <DeltaRow
                    label="Time"
                    before={result.as_is.total_time_hours}
                    after={result.to_be.total_time_hours}
                    unit="h"
                    pct={result.improvement.time_reduction_percent}
                    showMinutes
                    minutesBefore={result.as_is.total_time_minutes}
                    minutesAfter={result.to_be.total_time_minutes}
                  />
                  <DeltaRow
                    label="Cost"
                    before={result.as_is.total_cost_usd}
                    after={result.to_be.total_cost_usd}
                    unit="$"
                    pct={result.improvement.cost_reduction_percent}
                    prefixUnit
                    caption={result.currency === "generic_units" ? "synthetic unit-rates, not real currency" : null}
                  />
                </div>
              </div>
            </MotionSection>

            <MotionSection delay={0.05}>
              <Tabs key={activeResultTab} tabs={resultTabs} active={activeResultTab} onActiveChange={setActiveResultTab} />
            </MotionSection>
          </div>
        )}
      </div>
    </main>
  );
}

function SectionHeading({ title, subtitle, noMarginTop }) {
  return (
    <div className={noMarginTop ? "mb-5" : "mb-5 mt-1"}>
      <h2 className="font-display text-lg font-semibold text-gray-900">{title}</h2>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}

function DeltaRow({ label, before, after, unit, pct, prefixUnit, showMinutes, caption, minutesBefore, minutesAfter }) {
  const format = (val) => (prefixUnit ? `${unit}${val}` : `${val}${unit}`);
  const fmtMinutes = (hours, minutes) =>
    (minutes != null ? Math.round(minutes) : Math.round(hours * 60)).toLocaleString();

  return (
    <div>
      <p className="text-xs uppercase tracking-widest text-gray-400 mb-2.5">
        {label}
        {caption && <span className="normal-case tracking-normal text-gray-300"> · {caption}</span>}
      </p>
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-mono text-2xl" style={{ color: "var(--baseline)" }}>
          {format(before)}
        </span>
        <svg width="28" height="14" viewBox="0 0 28 14" className="text-gray-300 shrink-0">
          <path d="M0 7 H22 M16 1 L22 7 L16 13" stroke="currentColor" strokeWidth="1.5" fill="none" />
        </svg>
        <span className="font-mono text-2xl font-semibold" style={{ color: "var(--good)" }}>
          {format(after)}
        </span>
        <span
          className="font-mono text-sm px-2 py-0.5 rounded-md"
          style={{ color: "var(--good)", background: "var(--good-soft)" }}
        >
          −{pct}%
        </span>
      </div>
      {showMinutes && (
        <p className="font-mono text-xs text-gray-400 mt-1.5">
          {fmtMinutes(before, minutesBefore)} min → {fmtMinutes(after, minutesAfter)} min
        </p>
      )}
    </div>
  );
}
