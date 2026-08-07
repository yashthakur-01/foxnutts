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
  const [allowedDomains, setAllowedDomains] = useState("*");

  // Embed Widget Customization State
  const [widgetPosition, setWidgetPosition] = useState<"bottom-right" | "bottom-left">("bottom-right");
  const [copiedSnippet, setCopiedSnippet] = useState(false);

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
          setAllowedDomains(config.allowed_domains || "*");
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
          search_enabled: searchEnabled,
          allowed_domains: allowedDomains
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to update configuration");
      }

      setSaveStatus({ message: "Settings & security policies saved successfully!", type: "success" });
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

  // Construct Embed Snippet
  const appOrigin = typeof window !== "undefined" ? window.location.origin : "https://yourdomain.com";
  const embedSnippetCode = `<script 
  src="${appOrigin}/widget.v1.js" 
  data-workspace-id="${workspaceId}"
  data-position="${widgetPosition}"
  async
></script>`;

  const handleCopySnippet = () => {
    navigator.clipboard.writeText(embedSnippetCode);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2500);
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
          <p className="text-sm text-gray-400">Manage LLM parameters, threshold limits, and embed widget settings</p>
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

          {/* Context Relevance Threshold Setting */}
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

        {/* Right Column: Prompt & Allowed Domains */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5 flex flex-col justify-between">
          <div className="space-y-5">
            <h3 className="text-lg font-semibold text-white border-b border-gray-800 pb-3">
              📝 System Prompt & Security
            </h3>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">System Prompt</label>
              <textarea
                rows={4}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-3 text-sm focus:border-blue-500 focus:outline-none resize-none font-mono"
                placeholder="You are a helpful assistant..."
              />
            </div>

            {/* Allowed Domains Security Field */}
            <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2">
              <label className="block text-sm font-semibold text-slate-200">
                🛡️ Allowed Embedding Domains (Security Whitelist)
              </label>
              <input
                type="text"
                value={allowedDomains}
                onChange={(e) => setAllowedDomains(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg p-2.5 text-sm focus:border-blue-500 focus:outline-none font-mono"
                placeholder="e.g. example.com, myshop.com (or * for all)"
              />
              <p className="text-xs text-slate-400">
                Comma-separated host domains authorized to embed this widget. Use <code className="text-blue-400 font-mono">*</code> to allow any domain during development.
              </p>
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
              className="w-full md:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors disabled:opacity-50 cursor-pointer"
            >
              {saving ? "Saving Configuration..." : "💾 Save Workspace Settings"}
            </button>
          </div>
        </div>
      </form>

      {/* Website Integration & Embed Snippet Generator Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-gray-800 pb-3">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span>🔌</span> Website Embed Widget Snippet
            </h3>
            <p className="text-xs text-gray-400">
              Copy & paste this script snippet before the <code className="text-blue-400 font-mono">&lt;/body&gt;</code> tag on any website to embed your AI assistant.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Widget Position:</label>
            <select
              value={widgetPosition}
              onChange={(e) => setWidgetPosition(e.target.value as any)}
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-blue-500"
            >
              <option value="bottom-right">Bottom Right</option>
              <option value="bottom-left">Bottom Left</option>
            </select>
          </div>
        </div>

        {/* Code Box with Copy Button */}
        <div className="relative bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs text-emerald-400 overflow-x-auto">
          <pre>{embedSnippetCode}</pre>
          
          <button
            onClick={handleCopySnippet}
            className="absolute top-3 right-3 bg-blue-600 hover:bg-blue-700 text-white font-sans text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 shadow-md cursor-pointer"
          >
            {copiedSnippet ? (
              <>
                <span>✓</span> Copied!
              </>
            ) : (
              <>
                <span>📋</span> Copy Snippet
              </>
            )}
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-950/50 p-3 rounded-lg border border-slate-800/80">
          <span>💡</span>
          <span>
            The script runs asynchronously (<code className="text-blue-400">async</code>) without slowing down host website rendering. It loads the widget UI isolated inside an iframe.
          </span>
        </div>
      </div>

      {/* Modal: Create Workspace */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-md w-full space-y-4">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3">
              <h3 className="text-lg font-bold text-white">Create New Workspace</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-white text-lg font-bold cursor-pointer"
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
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold disabled:opacity-50 cursor-pointer"
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
