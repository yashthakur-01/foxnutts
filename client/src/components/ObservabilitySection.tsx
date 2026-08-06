"use client";

import { useEffect, useState } from "react";
import { createClient } from "../supabase/browserClient";

interface ObservabilitySectionProps {
  workspaceId: string;
}

interface Metrics {
  total_queries: number;
  total_tokens: number;
  avg_duration_ms: number;
  context_found_rate: number;
  csat_score: number;
  likes: number;
  dislikes: number;
  total_rated: number;
}

interface Trace {
  id: string;
  session_id: string;
  query: string;
  final_response: string;
  total_tokens: number;
  total_duration_ms: number;
  trajectory: any[];
  error_messages: any[];
  query_context_pairs: Array<{
    query: string;
    context_received: string;
    context_found?: boolean;
  }>;
  created_at: string;
}

interface GapItem {
  trace_id: string;
  session_id: string;
  query: string;
  context_received: string;
  context_found: boolean;
  created_at: string;
}

export default function ObservabilitySection({ workspaceId }: ObservabilitySectionProps) {
  const supabase = createClient();
  const [activeTab, setActiveTab] = useState<"traces" | "gaps" | "config">("traces");

  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [gaps, setGaps] = useState<GapItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Selected Trace Modal for Deep Inspection
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null);

  // Config Hyperparameter State
  const [similarityThreshold, setSimilarityThreshold] = useState<number>(0.6);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [configMessage, setConfigMessage] = useState("");

  const fetchObservabilityData = async () => {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const headers = {
        "Content-Type": "application/json",
        "Authorization": session.access_token,
      };

      // 1. Fetch Metrics
      const resMetrics = await fetch("/api/customer/observability/metrics", {
        method: "POST",
        headers,
        body: JSON.stringify({ workspace_id: workspaceId }),
      });
      const dataMetrics = await resMetrics.json();
      if (dataMetrics.success) setMetrics(dataMetrics.metrics);

      // 2. Fetch Traces
      const resTraces = await fetch("/api/customer/observability/traces", {
        method: "POST",
        headers,
        body: JSON.stringify({ workspace_id: workspaceId, limit: 30 }),
      });
      const dataTraces = await resTraces.json();
      if (dataTraces.success) setTraces(dataTraces.traces || []);

      // 3. Fetch Knowledge Gaps
      const resGaps = await fetch("/api/customer/observability/gaps", {
        method: "POST",
        headers,
        body: JSON.stringify({ workspace_id: workspaceId, limit: 30 }),
      });
      const dataGaps = await resGaps.json();
      if (dataGaps.success) setGaps(dataGaps.gaps || []);

      // 4. Fetch Workspace Similarity Threshold Hyperparameter
      const { data: wsData } = await supabase
        .from("workspace")
        .select("similarity_threshold")
        .eq("id", workspaceId)
        .single();

      if (wsData && wsData.similarity_threshold !== undefined) {
        setSimilarityThreshold(wsData.similarity_threshold);
      }

    } catch (err) {
      console.error("Failed to load observability data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (workspaceId) {
      fetchObservabilityData();
    }
  }, [workspaceId]);

  const handleSaveConfig = async () => {
    setIsSavingConfig(true);
    setConfigMessage("");
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("/api/customer/updateConfig", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token,
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          similarity_threshold: similarityThreshold,
        }),
      });

      const data = await res.json();
      if (data.success) {
        setConfigMessage("✅ Similarity threshold saved successfully!");
      } else {
        setConfigMessage(`❌ Error: ${data.message}`);
      }
    } catch (err) {
      setConfigMessage("❌ Failed to save configuration.");
    } finally {
      setIsSavingConfig(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            📊 AI Engine Observability
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Real-time analytics, vector context traces, and knowledge base gap detection.
          </p>
        </div>
        <button
          onClick={fetchObservabilityData}
          disabled={loading}
          className="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-sm font-medium py-2 px-4 rounded-lg transition-colors flex items-center gap-2"
        >
          {loading ? "Refreshing..." : "🔄 Refresh Metrics"}
        </button>
      </div>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Queries */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Total Queries</span>
          <div className="text-2xl font-extrabold text-white mt-2">
            {metrics ? metrics.total_queries : 0}
          </div>
          <span className="text-xs text-gray-500 mt-1 block">Chat Sessions Processed</span>
        </div>

        {/* Token Usage */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Total Tokens</span>
          <div className="text-2xl font-extrabold text-blue-400 mt-2">
            {metrics ? metrics.total_tokens.toLocaleString() : 0}
          </div>
          <span className="text-xs text-gray-500 mt-1 block">Prompt + Completion</span>
        </div>

        {/* Average Latency */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Avg Latency</span>
          <div className="text-2xl font-extrabold text-purple-400 mt-2">
            {metrics ? `${(metrics.avg_duration_ms / 1000).toFixed(2)}s` : "0s"}
          </div>
          <span className="text-xs text-gray-500 mt-1 block">End-to-End Duration</span>
        </div>

        {/* Context Match Rate */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Context Match Rate</span>
          <div className="text-2xl font-extrabold text-emerald-400 mt-2">
            {metrics ? `${metrics.context_found_rate}%` : "0%"}
          </div>
          <span className="text-xs text-gray-500 mt-1 block">Reranker Passed Threshold</span>
        </div>

        {/* CSAT Score */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">CSAT Score</span>
          {metrics && metrics.total_rated > 0 ? (
            <>
              <div className="text-2xl font-extrabold text-amber-400 mt-2">
                {metrics.csat_score}%
              </div>
              <span className="text-xs text-gray-500 mt-1 block">
                👍 {metrics.likes} / 👎 {metrics.dislikes}
              </span>
            </>
          ) : (
            <>
              <div className="text-lg font-bold text-gray-500 mt-2">
                No ratings yet
              </div>
              <span className="text-xs text-gray-500 mt-1 block">0 likes or dislikes</span>
            </>
          )}
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-gray-800 gap-4">
        <button
          onClick={() => setActiveTab("traces")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "traces"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          🔍 Traces & Context Inspector ({traces.length})
        </button>
        <button
          onClick={() => setActiveTab("gaps")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "gaps"
              ? "border-red-500 text-red-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          ⚠️ Knowledge Base Gaps ({gaps.length})
        </button>
        <button
          onClick={() => setActiveTab("config")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "config"
              ? "border-purple-500 text-purple-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          ⚙️ Reranker Threshold Settings
        </button>
      </div>

      {/* TAB 1: TRACES TABLE */}
      {activeTab === "traces" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-gray-800 flex justify-between items-center">
            <h3 className="text-lg font-bold text-white">Execution Traces & Retrieved Context</h3>
            <span className="text-xs text-gray-500">Latest 30 requests</span>
          </div>

          {traces.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No query traces logged yet. Send messages in the chat to record execution traces!
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-300">
                <thead className="bg-gray-950 text-gray-400 uppercase text-xs">
                  <tr>
                    <th className="p-4">Time</th>
                    <th className="p-4">User Query</th>
                    <th className="p-4">Tokens</th>
                    <th className="p-4">Latency</th>
                    <th className="p-4">Context Status</th>
                    <th className="p-4">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {traces.map((trace) => {
                    const pairs = Array.isArray(trace.query_context_pairs) ? trace.query_context_pairs : [];
                    const hasContext = pairs.some(p => p.context_found !== false && p.context_received && p.context_received.trim().length > 0);

                    return (
                      <tr key={trace.id} className="hover:bg-gray-850 transition-colors">
                        <td className="p-4 text-xs text-gray-400 whitespace-nowrap">
                          {new Date(trace.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                        <td className="p-4 max-w-xs truncate font-medium text-white" title={trace.query}>
                          {trace.query}
                        </td>
                        <td className="p-4 font-mono text-xs text-blue-400">
                          {trace.total_tokens}
                        </td>
                        <td className="p-4 font-mono text-xs text-purple-400">
                          {trace.total_duration_ms}ms
                        </td>
                        <td className="p-4">
                          {hasContext ? (
                            <span className="px-2.5 py-1 text-xs rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 font-medium">
                              ✅ Context Matched
                            </span>
                          ) : (
                            <span className="px-2.5 py-1 text-xs rounded-full bg-red-950 text-red-400 border border-red-800 font-medium">
                              ⚠️ Low Relevance
                            </span>
                          )}
                        </td>
                        <td className="p-4">
                          <button
                            onClick={() => setSelectedTrace(trace)}
                            className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-500/30 text-xs px-3 py-1.5 rounded-lg transition-colors"
                          >
                            Inspect Pair & Flow
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: KNOWLEDGE BASE GAPS */}
      {activeTab === "gaps" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="mb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              ⚠️ Unanswered Queries (Knowledge Base Gaps)
            </h3>
            <p className="text-sm text-gray-400 mt-1">
              Queries asked by visitors where vector search / Jina reranker did not find relevant context in your uploaded files.
            </p>
          </div>

          {gaps.length === 0 ? (
            <div className="bg-gray-950 border border-gray-800 rounded-xl p-8 text-center text-gray-400">
              🎉 No knowledge base gaps detected! All user queries matched uploaded document context.
            </div>
          ) : (
            <div className="space-y-3">
              {gaps.map((gap, idx) => (
                <div
                  key={idx}
                  className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-4 bg-gray-950 border border-red-900/30 rounded-xl gap-4"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-red-300 flex items-center gap-2">
                      <span>❓ "{gap.query}"</span>
                    </p>
                    <span className="text-xs text-gray-500">
                      Logged at: {new Date(gap.created_at).toLocaleString()}
                    </span>
                  </div>
                  <span className="bg-red-950 text-red-400 border border-red-800 text-xs font-semibold px-3 py-1.5 rounded-lg">
                    Missing Document Info
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: CONFIG HYPERPARAMETER SETTINGS */}
      {activeTab === "config" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-2xl space-y-6">
          <div>
            <h3 className="text-lg font-bold text-white">⚙️ Vector Relevance Score Hyperparameter</h3>
            <p className="text-sm text-gray-400 mt-1">
              Adjust the Jina Reranker relevance score threshold. Queries with document similarity scores below this threshold will be marked as unanswered gaps.
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <label className="text-sm font-medium text-gray-200">
                Similarity Threshold (<code className="text-purple-400">{similarityThreshold}</code>)
              </label>
              <span className="text-xs text-gray-400">Range: 0.1 (Strictness: Low) to 0.9 (Strictness: High)</span>
            </div>

            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={similarityThreshold}
              onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-950 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />

            <div className="flex justify-between text-xs text-gray-500">
              <span>0.1 (Accept Low Similarity)</span>
              <span>0.6 (Default Recommended)</span>
              <span>0.9 (Require Exact Matches)</span>
            </div>

            <button
              onClick={handleSaveConfig}
              disabled={isSavingConfig}
              className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium py-2.5 px-6 rounded-lg transition-colors disabled:opacity-50"
            >
              {isSavingConfig ? "Saving Settings..." : "Save Threshold"}
            </button>

            {configMessage && (
              <p className="text-sm font-medium mt-2">{configMessage}</p>
            )}
          </div>
        </div>
      )}

      {/* INSPECT TRACE MODAL */}
      {selectedTrace && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            {/* Modal Header */}
            <div className="p-5 border-b border-gray-800 flex justify-between items-center bg-gray-950">
              <div>
                <h3 className="text-lg font-bold text-white">Trace Inspection</h3>
                <span className="text-xs text-gray-400 font-mono">Session ID: {selectedTrace.session_id}</span>
              </div>
              <button
                onClick={() => setSelectedTrace(null)}
                className="text-gray-400 hover:text-white text-xl font-bold p-1"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm">
              {/* User Query & Answer */}
              <div className="space-y-3">
                <div className="bg-blue-950/40 border border-blue-900/50 p-4 rounded-xl">
                  <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider block mb-1">User Query</span>
                  <p className="text-white font-medium">{selectedTrace.query}</p>
                </div>

                <div className="bg-gray-950 border border-gray-800 p-4 rounded-xl">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-1">Final AI Response</span>
                  <p className="text-gray-200 whitespace-pre-wrap">{selectedTrace.final_response}</p>
                </div>
              </div>

              {/* Query:Context Pairs */}
              <div>
                <h4 className="text-sm font-bold text-white mb-3">Query-Context Pairs (`query_context_pairs`)</h4>
                {selectedTrace.query_context_pairs?.length === 0 ? (
                  <p className="text-xs text-gray-500 italic">No vector context pairs recorded for this query.</p>
                ) : (
                  <div className="space-y-3">
                    {selectedTrace.query_context_pairs?.map((pair, i) => (
                      <div key={i} className="bg-gray-950 border border-gray-800 p-4 rounded-xl space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="text-xs font-bold text-purple-400">Sub-Query {i + 1}: "{pair.query}"</span>
                          {pair.context_found !== false && pair.context_received ? (
                            <span className="text-xs text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">Passed Threshold</span>
                          ) : (
                            <span className="text-xs text-red-400 bg-red-950 px-2 py-0.5 rounded border border-red-800">Below Threshold</span>
                          )}
                        </div>
                        <div className="text-xs text-gray-300 font-mono bg-gray-900 p-3 rounded-lg max-h-40 overflow-y-auto whitespace-pre-wrap border border-gray-800">
                          {pair.context_received || "No context passed relevance score threshold."}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Trajectory Steps */}
              <div>
                <h4 className="text-sm font-bold text-white mb-3">LangGraph Trajectory Flow</h4>
                <div className="space-y-2">
                  {selectedTrace.trajectory?.map((step, i) => (
                    <div key={i} className="flex justify-between items-center p-3 bg-gray-950 border border-gray-800 rounded-lg text-xs">
                      <span className="font-semibold text-blue-400">Node: {step.node}</span>
                      <span className="text-gray-400 font-mono">{step.duration_ms}ms</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-800 bg-gray-950 flex justify-end">
              <button
                onClick={() => setSelectedTrace(null)}
                className="bg-gray-800 hover:bg-gray-700 text-white font-medium text-xs px-4 py-2 rounded-lg transition-colors"
              >
                Close Trace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
