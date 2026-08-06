"use client";

import { useEffect, useState } from "react";
import { createClient } from "../supabase/browserClient";

interface SettingsSectionProps {
  workspaceId: string;
  onWorkspaceChange: (newWorkspaceId: string) => void;
}

interface WorkspaceItem {
  id: string;
  workspace_name?: string;
  workspace_url?: string;
  created_at: string;
}

export default function SettingsSection({ workspaceId, onWorkspaceChange }: SettingsSectionProps) {
  const supabase = createClient();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Form State
  const [workspaceName, setWorkspaceName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [modelName, setModelName] = useState("llama-3.3-70b-versatile");
  const [provider, setProvider] = useState("groq");
  const [similarityThreshold, setSimilarityThreshold] = useState(0.6);
  const [chunkSize, setChunkSize] = useState(1024);
  const [chunkOverlap, setChunkOverlap] = useState(250);
  const [searchEnabled, setSearchEnabled] = useState(false);

  // Workspaces List State
  const [userWorkspaces, setUserWorkspaces] = useState<WorkspaceItem[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [newWsUrl, setNewWsUrl] = useState("");
  const [creatingWs, setCreatingWs] = useState(false);
  const [createWsError, setCreateWsError] = useState("");

  // 1. Fetch user's workspaces and active config
  useEffect(() => {
    fetchWorkspacesAndConfig();
  }, [workspaceId]);

  const fetchWorkspacesAndConfig = async () => {
    setLoading(true);
    setSaveStatus(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      // Fetch all user workspaces
      const wsRes = await fetch("/api/customer/getWorkspaces", {
        headers: { "Authorization": session.access_token }
      });
      if (wsRes.ok) {
        const wsData = await wsRes.json();
        setUserWorkspaces(wsData.workspaces || []);
      }

      // Fetch config for active workspace
      const configRes = await fetch("/api/customer/getWorkspaceConfig", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({ workspace_id: workspaceId })
      });

      if (configRes.ok) {
        const { config } = await configRes.json();
        if (config) {
          setWorkspaceName(config.workspace_name || "Default Workspace");
          setSystemPrompt(config.system_prompt || "You are a helpful assistant.");
          setTemperature(Number(config.temperature ?? 0.7));
          setModelName(config.model_name || "llama-3.3-70b-versatile");
          setProvider(config.provider || "groq");
          setSimilarityThreshold(Number(config.similarity_threshold ?? 0.6));
          setChunkSize(Number(config.chunk_size ?? 1024));
          setChunkOverlap(Number(config.chunk_overlap ?? 250));
          setSearchEnabled(Boolean(config.search_enabled));
        }
      }
    } catch (err) {
      console.error("Error loading workspace config:", err);
    } finally {
      setLoading(false);
    }
  };

  // 2. Save Configuration Updates
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveStatus(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      const res = await fetch("/api/customer/updateConfig", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          workspace_name: workspaceName,
          system_prompt: systemPrompt,
          temperature,
          model_name: modelName,
          provider,
          similarity_threshold: similarityThreshold,
          chunk_size: chunkSize,
          chunk_overlap: chunkOverlap,
          search_enabled: searchEnabled
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to update configuration");
      }

      setSaveStatus({ message: "Settings saved successfully! Redis workspace cache purged.", type: "success" });
      fetchWorkspacesAndConfig();
    } catch (err: any) {
      console.error("Save config error:", err);
      setSaveStatus({ message: err.message || "Failed to save settings", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  // 3. Create New Workspace
  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim() || !newWsUrl.trim()) {
      setCreateWsError("Please provide both workspace name and URL slug.");
      return;
    }

    setCreatingWs(true);
    setCreateWsError("");

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      const res = await fetch("/api/customer/createWorkspace", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({
          workspace_name: newWsName.trim(),
          workspace_url: newWsUrl.trim().toLowerCase().replace(/[^a-z0-9-]/g, "-")
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to create workspace");
      }

      setShowCreateModal(false);
      setNewWsName("");
      setNewWsUrl("");

      // Switch to the newly created workspace
      const newWs = data.workspace?.[0] || data.workspace;
      if (newWs?.id) {
        onWorkspaceChange(newWs.id);
      } else {
        fetchWorkspacesAndConfig();
      }
    } catch (err: any) {
      console.error("Create workspace error:", err);
      setCreateWsError(err.message || "Failed to create workspace");
    } finally {
      setCreatingWs(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-400">Loading workspace settings...</div>;
  }

  return (
    <div className="space-y-6">
      
      {/* Workspace Switcher Header Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">Active Workspace</h2>
          <p className="text-sm text-gray-400">Manage LLM parameters, threshold limits, and switch workspaces</p>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <select
            value={workspaceId}
            onChange={(e) => onWorkspaceChange(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500 flex-1 md:flex-initial"
          >
            {userWorkspaces.map((ws, idx) => (
              <option key={ws.id} value={ws.id}>
                {ws.workspace_name || `Demo Workspace ${idx + 1} (${ws.id.substring(0, 8)})`}
              </option>
            ))}
          </select>

          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors whitespace-nowrap"
          >
            ➕ Create New Workspace
          </button>
        </div>
      </div>

      {saveStatus && (
        <div
          className={`p-4 rounded-xl text-sm font-medium border ${
            saveStatus.type === "success"
              ? "bg-emerald-950/80 border-emerald-800 text-emerald-300"
              : "bg-red-950/80 border-red-800 text-red-300"
          }`}
        >
          {saveStatus.message}
        </div>
      )}

      {/* Main Settings Form */}
      <form onSubmit={handleSaveSettings} className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Left Column: Model & Threshold Settings */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <h3 className="text-lg font-semibold text-white border-b border-gray-800 pb-3">
            🤖 LLM & Retrieval Parameters
          </h3>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Workspace Name</label>
            <input
              type="text"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="e.g. Finance AI Workspace"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">LLM Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="groq">Groq (Ultra-Fast Inference)</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Model Name</label>
            <select
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (Groq)</option>
              <option value="mixtral-8x7b-32768">mixtral-8x7b-32768 (Groq)</option>
              <option value="gpt-4o">gpt-4o (OpenAI)</option>
              <option value="gpt-4o-mini">gpt-4o-mini (OpenAI)</option>
            </select>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-sm font-medium text-gray-300">Temperature</label>
              <span className="text-xs font-mono text-blue-400 bg-gray-800 px-2 py-0.5 rounded">{temperature}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <p className="text-xs text-gray-500 mt-1">Lower values are more precise; higher values are more creative.</p>
          </div>

          {/* Relevance / Similarity Threshold Setting */}
          <div className="bg-blue-950/40 border border-blue-800/60 p-4 rounded-xl space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-sm font-semibold text-blue-300">
                🎯 Context Relevance Threshold
              </label>
              <span className="text-xs font-mono font-bold text-blue-300 bg-blue-900/80 px-2.5 py-1 rounded-md border border-blue-700">
                {similarityThreshold.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={similarityThreshold}
              onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
              className="w-full accent-blue-400 cursor-pointer"
            />
            <p className="text-xs text-blue-300/80">
              Chit-chat & document chunks below this vector similarity score will be categorized as <span className="font-semibold text-red-400">Low Relevance</span>.
            </p>
          </div>
        </div>

        {/* Right Column: Prompt & Chunking Parameters */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5 flex flex-col justify-between">
          <div className="space-y-5">
            <h3 className="text-lg font-semibold text-white border-b border-gray-800 pb-3">
              📝 Prompt System & Ingestion
            </h3>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">System Prompt</label>
              <textarea
                rows={5}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-3 text-sm focus:border-blue-500 focus:outline-none resize-none font-mono"
                placeholder="You are a helpful assistant..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Chunk Size (chars)</label>
                <input
                  type="number"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(parseInt(e.target.value) || 1024)}
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Chunk Overlap (chars)</label>
                <input
                  type="number"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(parseInt(e.target.value) || 250)}
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 border border-gray-700">
              <div>
                <p className="text-sm font-medium text-white">Enable Web Search Fallback</p>
                <p className="text-xs text-gray-400">Search web when document context is missing</p>
              </div>
              <input
                type="checkbox"
                checked={searchEnabled}
                onChange={(e) => setSearchEnabled(e.target.checked)}
                className="h-5 w-5 rounded accent-blue-600 cursor-pointer"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-gray-800 flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="w-full md:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? "Saving Configuration..." : "💾 Save Workspace Settings"}
            </button>
          </div>
        </div>
      </form>

      {/* Modal: Create Workspace */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-md w-full space-y-4">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3">
              <h3 className="text-lg font-bold text-white">Create New Workspace</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-white text-lg font-bold"
              >
                ✕
              </button>
            </div>

            {createWsError && (
              <div className="p-3 bg-red-950/80 border border-red-800 text-red-300 text-xs rounded-lg">
                {createWsError}
              </div>
            )}

            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Workspace Name</label>
                <input
                  type="text"
                  required
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  placeholder="e.g. Legal Research Workspace"
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Workspace URL Slug</label>
                <input
                  type="text"
                  required
                  value={newWsUrl}
                  onChange={(e) => setNewWsUrl(e.target.value)}
                  placeholder="e.g. legal-research-ws"
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none font-mono"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold disabled:opacity-50"
                >
                  {creatingWs ? "Creating..." : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
