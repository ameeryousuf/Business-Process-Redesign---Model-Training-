"use client";
import { useState, useRef, Fragment } from "react";
import BpmnDiagram from "@/components/BpmnDiagram";

export default function Home() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [expandedStep, setExpandedStep] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileSelect = (selectedFile) => {
    if (!selectedFile) return;

    const validExtensions = [".bpmn", ".xml"];
    const isValid = validExtensions.some((ext) =>
      selectedFile.name.toLowerCase().endsWith(ext)
    );

    if (!isValid) {
      setError("Please upload a .bpmn or .xml file.");
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://127.0.0.1:8000/redesign", {
        method: "POST",
        body: formData,
      });

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

  return (
    <main className="min-h-screen" style={{ background: "var(--page-bg)" }}>
      <div className="border-b" style={{ borderColor: "var(--panel-border)" }}>
        <div className="px-6 md:px-16 py-6 flex items-baseline gap-3">
          <h1 className="font-display text-2xl font-semibold tracking-tight">
            BPM Redesign Engine
          </h1>
          <span className="font-mono text-xs text-gray-400 uppercase tracking-widest">
            RL-driven process optimization
          </span>
        </div>
      </div>

      <div className="px-6 md:px-16 py-10 space-y-6">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className="rounded-2xl p-8 border-2 border-dashed transition-colors"
          style={{
            borderColor: isDragging ? "var(--accent)" : "var(--panel-border)",
            background: isDragging ? "var(--accent-soft)" : "var(--panel-bg)",
          }}
        >
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-center md:text-left">
              <p className="font-medium text-gray-900">
                {file ? file.name : "Drop a .bpmn file here, or browse to select one"}
              </p>
              <p className="text-gray-400 text-sm mt-1">
                Accepts BPMN 2.0 XML process files
              </p>
            </div>

            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".bpmn,.xml"
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

              <button
                onClick={handleSubmit}
                disabled={loading || !file}
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-colors inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: "var(--accent)" }}
              >
                {loading && (
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                {loading ? "Processing" : "Redesign Process"}
              </button>

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
        </div>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
            <p className="text-red-700 font-medium text-sm">Something went wrong</p>
            <p className="text-red-600/80 text-sm mt-1">{error}</p>
          </div>
        )}

        {result && (
          <div className="space-y-6">
            <div
              className="rounded-2xl p-7 border"
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
                />
                <DeltaRow
                  label="Cost"
                  before={result.as_is.total_cost_usd}
                  after={result.to_be.total_cost_usd}
                  unit="$"
                  pct={result.improvement.cost_reduction_percent}
                  prefixUnit
                />
              </div>
            </div>

            <div
              className="rounded-2xl p-7 border"
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
              className="rounded-2xl p-7 border"
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
                  className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-md font-medium"
                >
                  Download BPMN
                </button>
              </div>
              <BpmnDiagram xml={result.to_be_bpmn_xml} height={520} />
            </div>

            <div
              className="rounded-2xl p-7 border overflow-x-auto"
              style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
            >
              <p className="font-mono text-xs uppercase tracking-widest text-gray-400 mb-5">
                Redesign Trace
              </p>

              <table className="w-full border-collapse min-w-[760px]">
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
                      <tr
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
                          {step.time_delta_pct > 0 && (
                            <div className="text-xs font-mono" style={{ color: "var(--good)" }}>
                              −{step.time_delta_pct}%
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
                              style={{ color: step.cost_delta_pct > 0 ? "var(--good)" : "var(--baseline)" }}
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
                      </tr>
                      {expandedStep === step.step && (
                        <tr
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
                        </tr>
                      )}
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
          </div>
        )}
      </div>
    </main>
  );
}

function DeltaRow({ label, before, after, unit, pct, prefixUnit }) {
  const format = (val) => (prefixUnit ? `${unit}${val}` : `${val}${unit}`);

  return (
    <div>
      <p className="text-xs uppercase tracking-widest text-gray-400 mb-2.5">{label}</p>
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
    </div>
  );
}