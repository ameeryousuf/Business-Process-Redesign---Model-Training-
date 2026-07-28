"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { getUser, clearSession, fetchAllProcesses, fetchProcessBundle } from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";

export default function ProcessesPage() {
  const router = useRouter();
  const authed = useAuthGuard();
  const [processes, setProcesses] = useState([]);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [redesigningId, setRedesigningId] = useState(null);
  const [loadSeq, setLoadSeq] = useState(0);
  const requestIdRef = useRef(0);

  const load = useCallback(async (targetSearch) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAllProcesses({ search: targetSearch });
      if (requestId !== requestIdRef.current) return;
      setProcesses(result || []);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err.message);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setLoadSeq((n) => n + 1);
      }
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    load(search);
  }, [authed, search, load]);

  useEffect(() => {
    const handle = setTimeout(() => {
      setSearch(searchInput.trim());
    }, 300);
    return () => clearTimeout(handle);
  }, [searchInput]);

  if (!authed) {
    return null;
  }

  const handleLogout = () => {
    clearSession();
    router.push("/login");
  };

  const handleRedesign = async (processId) => {
    setRedesigningId(processId);
    setError(null);
    try {
      const bundle = await fetchProcessBundle(processId);
      sessionStorage.setItem("pending_redesign_bundle", JSON.stringify(bundle));
      router.push("/");
    } catch (err) {
      setError(`Could not fetch process ${processId}: ${err.message}`);
      setRedesigningId(null);
    }
  };

  const user = getUser();

  return (
    <main className="min-h-screen">
      <div className="border-b" style={{ borderColor: "var(--panel-border)" }}>
        <div className="px-6 md:px-16 py-6 flex items-center justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-gray-400 mb-1">
              Digital Twin Server
            </p>
            <h1 className="font-display text-2xl font-semibold tracking-tight">
              Processes
            </h1>
          </div>
          <div className="flex items-center gap-4">
            {user && <span className="text-sm text-gray-500">{user.name || user.email}</span>}
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-gray-600 underline underline-offset-2"
            >
              Log out
            </button>
          </div>
        </div>
      </div>

      <div className="px-6 md:px-16 py-10 space-y-6 max-w-6xl mx-auto">
        <div className="relative flex items-center">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by process name, code, or ID…"
            className="w-full px-4 py-2.5 rounded-lg border text-sm focus:outline-none focus:ring-2"
            style={{ borderColor: "var(--panel-border)", background: "var(--panel-bg)" }}
          />
          {loading && searchInput && (
            <span className="absolute right-4 w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        <div key={loadSeq}>
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="rounded-xl border border-red-200 bg-red-50 p-4 overflow-hidden"
              >
                <p className="text-red-600 text-sm">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          <div
            className="rounded-2xl border card-shadow overflow-hidden"
            style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
          >
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr style={{ background: "var(--accent-soft)" }}>
                  <th className="text-left font-medium text-xs uppercase tracking-wider text-gray-500 px-5 py-3">
                    Process Name
                  </th>
                  <th className="text-left font-medium text-xs uppercase tracking-wider text-gray-500 px-5 py-3">
                    Code
                  </th>
                  <th className="text-left font-medium text-xs uppercase tracking-wider text-gray-500 px-5 py-3">
                    Version
                  </th>
                  <th className="text-left font-medium text-xs uppercase tracking-wider text-gray-500 px-5 py-3">
                    Company
                  </th>
                  <th className="text-right font-medium text-xs uppercase tracking-wider text-gray-500 px-5 py-3">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-gray-400">
                      Loading processes…
                    </td>
                  </tr>
                )}

                {!loading && processes.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-gray-400">
                      No processes found.
                    </td>
                  </tr>
                )}

                {!loading &&
                  processes.map((p, idx) => (
                    <motion.tr
                      key={p.process_id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.25, delay: Math.min(idx, 30) * 0.02 }}
                      className="border-t hover:bg-gray-50/60 transition-colors"
                      style={{ borderColor: "var(--panel-border)" }}
                    >
                      <td className="px-5 py-3.5 text-gray-900 font-medium">{p.process_name}</td>
                      <td className="px-5 py-3.5 font-mono text-xs text-gray-500">{p.process_code}</td>
                      <td className="px-5 py-3.5">
                        <span
                          className="font-mono text-xs px-2 py-0.5 rounded-md"
                          style={{ color: "var(--accent)", background: "var(--accent-soft)" }}
                        >
                          v{p.process_version ?? 0}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-gray-500 text-xs">
                        {p.company?.company_name || p.company?.name || "—"}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          onClick={() => handleRedesign(p.process_id)}
                          disabled={redesigningId === p.process_id}
                          className="text-xs font-medium px-3 py-1.5 rounded-md text-white transition-colors disabled:opacity-50 inline-flex items-center gap-1.5"
                          style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-2))" }}
                        >
                          {redesigningId === p.process_id && (
                            <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          )}
                          {redesigningId === p.process_id ? "Fetching…" : "Redesign"}
                        </button>
                      </td>
                    </motion.tr>
                  ))}
              </tbody>
            </table>
          </div>

          {!loading && processes.length > 0 && (
            <p className="text-sm text-gray-500">{processes.length} processes</p>
          )}
        </div>
      </div>
    </main>
  );
}
