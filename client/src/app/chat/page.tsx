"use client";

import { useEffect, useState, useRef } from "react";
import { createClient } from "../../supabase/browserClient";
import { useRouter } from "next/navigation";
import ObservabilitySection from "../../components/ObservabilitySection";
import SettingsSection from "../../components/SettingsSection";

export default function ChatDashboard() {
  const supabase = createClient();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [activeMainTab, setActiveMainTab] = useState<"chat" | "observability" | "settings">("chat");
  
  // File Upload State
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState(false);

  // Workspace Files State
  const [workspaceFiles, setWorkspaceFiles] = useState<{ file_id: string; file_name: string; status: string; created_at: string }[]>([]);
  const [reprocessingFileId, setReprocessingFileId] = useState<string | null>(null);
  const [deletingFileId, setDeletingFileId] = useState<string | null>(null);

  // Chat State
  const [messages, setMessages] = useState<{ role: "human" | "ai"; content: string }[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isChatting, setIsChatting] = useState(false);
  const sessionId = useRef(`session-${Math.random().toString(36).substring(7)}`);

  // Helper for R2 presigned URL upload with progress tracking
  const uploadToR2WithProgress = (url: string, fileToUpload: File, onProgress: (percent: number) => void): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", url);
      xhr.setRequestHeader("Content-Type", fileToUpload.type);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during upload to R2"));
      xhr.send(fileToUpload);
    });
  };

  useEffect(() => {
    const initApp = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login");
        return;
      }

      // Check if user has a workspace
      let { data: workspaces, error } = await supabase
        .from("workspace")
        .select("id")
        .eq("cust_id", session.user.id);

      if (error) {
        console.error("Error fetching workspace", error);
        return;
      }

      if (workspaces && workspaces.length > 0) {
        setWorkspaceId(workspaces[0].id);
      } else {
        // Create a dummy workspace if they don't have one
        const { data: newWorkspace, error: insertError } = await supabase
          .from("workspace")
          .insert({
            cust_id: session.user.id,
            temperature: 0.7,
            model_name: "llama-3.3-70b-versatile",
            provider: "groq",
            system_prompt: "You are a helpful assistant.",
            search_enabled: false
          })
          .select("id")
          .single();

        if (newWorkspace) {
          setWorkspaceId(newWorkspace.id);
        }
      }
      setLoading(false);
    };

    initApp();
  }, [router]);

  // Fetch files for the current workspace
  const fetchFiles = async () => {
    if (!workspaceId) return;
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("/api/customer/getFiles", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({ workspace_id: workspaceId })
      });

      if (res.ok) {
        const data = await res.json();
        setWorkspaceFiles(data.files || []);
      }
    } catch (err) {
      console.error("Error fetching files:", err);
    }
  };

  // Fetch files on mount and when workspaceId changes
  useEffect(() => {
    if (workspaceId) fetchFiles();
  }, [workspaceId]);

  // Handle reprocessing a failed file
  const handleReprocess = async (fileId: string) => {
    if (!workspaceId) return;
    setReprocessingFileId(fileId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      const res = await fetch("/api/customer/reprocessDocument", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          fileName: fileId
        })
      });

      if (!res.ok) throw new Error("Reprocess request failed");

      // Update local state to show processing
      setWorkspaceFiles(prev =>
        prev.map(f => f.file_id === fileId ? { ...f, status: "processing" } : f)
      );

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const { data, error } = await supabase
            .from("files")
            .select("status")
            .eq("file_id", fileId)
            .maybeSingle();

          if (data) {
            if (data.status === "completed" || data.status === "failed") {
              setWorkspaceFiles(prev =>
                prev.map(f => f.file_id === fileId ? { ...f, status: data.status } : f)
              );
              setReprocessingFileId(null);
              clearInterval(pollInterval);
            }
          }
        } catch (pollErr) {
          console.error("Reprocess poll error:", pollErr);
        }
      }, 3000);

    } catch (err) {
      console.error("Reprocess error:", err);
      setReprocessingFileId(null);
    }
  };

  // Handle deleting a file from DB, R2, and Pinecone
  const handleDeleteFile = async (fileId: string) => {
    if (!workspaceId) return;
    if (!confirm("Are you sure you want to delete this file? This will permanently remove its record, R2 storage, and Pinecone vectors.")) return;

    setDeletingFileId(fileId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      const res = await fetch("/api/customer/deleteFile", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          file_id: fileId
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.message || "Failed to delete file");
      }

      // Remove file from local state list immediately
      setWorkspaceFiles(prev => prev.filter(f => f.file_id !== fileId));
    } catch (err: any) {
      console.error("Delete file error:", err);
      alert(err.message || "Failed to delete file");
    } finally {
      setDeletingFileId(null);
    }
  };

  const handleFileUpload = async () => {
    if (!file || !workspaceId) return;
    setIsUploading(true);
    setUploadProgress(0);
    setUploadStatus("Getting secure upload URL...");

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Not authenticated");

      // 1. Get Presigned URL
      const presignedRes = await fetch("/api/customer/uploadFile", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          fileName: file.name,
          fileType: file.type
        })
      });

      if (!presignedRes.ok) throw new Error("Failed to get presigned URL");
      const { uploadUrl, uniqueFileName, key } = await presignedRes.json();

      setUploadStatus("Uploading file to Cloudflare R2... 0%");
      // 2. Upload directly to R2 with XHR progress monitoring
      await uploadToR2WithProgress(uploadUrl, file, (percent) => {
        setUploadProgress(percent);
        setUploadStatus(`Uploading file to Cloudflare R2... ${percent}%`);
      });

      // 3. R2 upload complete — insert file record into Supabase with 'uploaded' status
      setUploadStatus("Saving file record...");
      const { error: dbError } = await supabase
        .from("files")
        .insert({
          file_id: uniqueFileName,
          file_name: file.name,
          workspace_id: workspaceId,
          file_path: key,
          status: "uploaded"
        });

      if (dbError) {
        console.error("Failed to insert file record:", dbError);
      }

      setUploadStatus("Queuing document for background processing...");
      // 3. Process document in backend
      const processRes = await fetch("/api/customer/processDocument", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session.access_token
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          fileName: uniqueFileName
        })
      });

      if (!processRes.ok) throw new Error("Backend processing failed");

      setUploadStatus("⏳ Document uploaded! Processing in background (creating embeddings)...");
      setFile(null);

      // Refresh file list to show the new file
      await fetchFiles();

      // 4. Poll Supabase database for file status completion
      const pollInterval = setInterval(async () => {
        try {
          const { data, error } = await supabase
            .from("files")
            .select("status")
            .eq("file_id", uniqueFileName)
            .maybeSingle();

          if (error) {
            console.error("Polling status error:", error);
            return;
          }

          if (data) {
            if (data.status === "completed") {
              setUploadStatus("✅ Document processing complete! Ready for chat.");
              setIsUploading(false);
              setUploadProgress(100);
              await fetchFiles();
              clearInterval(pollInterval);
            } else if (data.status === "failed") {
              setUploadStatus("❌ Document processing failed. Use the reprocess button below.");
              setIsUploading(false);
              await fetchFiles();
              clearInterval(pollInterval);
            }
          }
        } catch (pollErr) {
          console.error("Polling error:", pollErr);
        }
      }, 3000); // Check every 3 seconds

    } catch (err: any) {
      console.error(err);
      setUploadStatus(`❌ Error: ${err.message}`);
      setIsUploading(false);
    }
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || !workspaceId) return;

    const userMessage = inputValue;
    setMessages(prev => [...prev, { role: "human", content: userMessage }]);
    setInputValue("");
    setIsChatting(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();

      const response = await fetch("/api/chat/sendMessage", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": session?.access_token || ""
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          customer_id: session?.user.id,
          session_id: sessionId.current,
          message: userMessage
        })
      });

      if (!response.ok) throw new Error("Chat failed");
      
      // If FastAPI sends a stream, we read it chunk by chunk
      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        setMessages(prev => [...prev, { role: "ai", content: "" }]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          
          setMessages(prev => {
            const newMsgs = [...prev];
            const lastIdx = newMsgs.length - 1;
            newMsgs[lastIdx] = { ...newMsgs[lastIdx], content: newMsgs[lastIdx].content + chunk };
            return newMsgs;
          });
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: "ai", content: "❌ Failed to connect to AI engine." }]);
    } finally {
      setIsChatting(false);
    }
  };

  const handleLogout = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        await fetch("/api/customer/logout", {
          method: "POST",
          headers: { "Authorization": session.access_token }
        });
      }
    } catch (err) {
      console.error("Logout cache clearance error:", err);
    }
    await supabase.auth.signOut();
    router.push("/login");
  };

  if (loading) {
    return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Loading Test Dashboard...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Main Navigation Header */}
        <div className="flex justify-between items-center bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex gap-3">
            <button
              onClick={() => setActiveMainTab("chat")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                activeMainTab === "chat"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              💬 Chatbot & Ingestion
            </button>
            <button
              onClick={() => setActiveMainTab("observability")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                activeMainTab === "observability"
                  ? "bg-purple-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              📊 Observability Analytics
            </button>
            <button
              onClick={() => setActiveMainTab("settings")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                activeMainTab === "settings"
                  ? "bg-emerald-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              ⚙️ Workspace Settings
            </button>
          </div>

          <button onClick={handleLogout} className="text-sm text-red-400 hover:text-red-300 font-medium px-3.5 py-1.5 rounded-lg bg-gray-950 border border-gray-800">
            Logout
          </button>
        </div>

        {/* Active Tab Views */}
        {activeMainTab === "observability" && workspaceId ? (
          <ObservabilitySection workspaceId={workspaceId} />
        ) : activeMainTab === "settings" && workspaceId ? (
          <SettingsSection workspaceId={workspaceId} onWorkspaceChange={(newId) => setWorkspaceId(newId)} />
        ) : (
          <div className="flex gap-8">
            {/* Left Column: Upload */}
            <div className="w-1/3 space-y-6">
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-bold text-white">Data Ingestion</h2>
                </div>
                
                <div className="space-y-4">
                  <input
                    type="file"
                    accept=".pdf,.txt,.md"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer"
                  />
                  <button
                    onClick={handleFileUpload}
                    disabled={!file || isUploading}
                    className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isUploading ? "Uploading & Processing..." : "Upload Document"}
                  </button>

                  {isUploading && (
                    <div className="w-full bg-gray-950 rounded-full h-3 overflow-hidden border border-gray-800 p-0.5">
                      <div
                        className="bg-blue-500 h-full rounded-full transition-all duration-200"
                        style={{ width: `${uploadProgress}%` }}
                      ></div>
                    </div>
                  )}

                  {uploadStatus && (
                    <div className="text-sm text-gray-300 bg-gray-800/50 p-3 rounded border border-gray-700 break-words">
                      {uploadStatus}
                    </div>
                  )}
                </div>
              </div>

              {/* Uploaded Files List */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Uploaded Files</h3>
                {workspaceFiles.length === 0 ? (
                  <p className="text-sm text-gray-500">No files uploaded yet.</p>
                ) : (
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {workspaceFiles.map((f) => (
                      <div
                        key={f.file_id}
                        className="flex items-center justify-between gap-2 p-3 rounded-lg bg-gray-800/50 border border-gray-700"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-200 truncate" title={f.file_name}>
                            {f.file_name}
                          </p>
                          <span
                            className={`text-xs font-medium ${
                              f.status === "completed"
                                ? "text-green-400"
                                : f.status === "failed"
                                ? "text-red-400"
                                : "text-yellow-400"
                            }`}
                          >
                            {f.status === "completed" ? "✅ Completed" : f.status === "failed" ? "❌ Failed" : "⏳ Processing"}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {f.status === "failed" && (
                            <button
                              onClick={() => handleReprocess(f.file_id)}
                              disabled={reprocessingFileId === f.file_id || deletingFileId === f.file_id}
                              className="text-xs bg-yellow-600 hover:bg-yellow-700 text-white px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
                            >
                              {reprocessingFileId === f.file_id ? "Reprocessing..." : "Reprocess"}
                            </button>
                          )}

                          <button
                            onClick={() => handleDeleteFile(f.file_id)}
                            disabled={deletingFileId === f.file_id || reprocessingFileId === f.file_id}
                            className="text-xs bg-red-600/80 hover:bg-red-600 text-white px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
                            title="Delete file, R2 object, and Pinecone vectors"
                          >
                            {deletingFileId === f.file_id ? "Deleting..." : "🗑️ Delete"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="text-xs text-gray-500">
                Workspace ID: <br/><code className="text-blue-400">{workspaceId}</code>
              </div>
            </div>

            {/* Right Column: Chat */}
            <div className="w-2/3 bg-gray-900 border border-gray-800 rounded-xl flex flex-col h-[80vh]">
              <div className="p-4 border-b border-gray-800">
                <h2 className="text-xl font-bold text-white">Test RAG Chatbot</h2>
              </div>
              
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    Upload a document on the left, then ask a question here!
                  </div>
                ) : (
                  messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === "human" ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[80%] rounded-xl p-4 ${
                        msg.role === "human" 
                          ? "bg-blue-600 text-white" 
                          : "bg-gray-800 text-gray-200 border border-gray-700"
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  ))
                )}
              </div>

              <form onSubmit={handleChat} className="p-4 border-t border-gray-800">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Ask about your documents..."
                    className="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500"
                    disabled={isChatting}
                  />
                  <button
                    type="submit"
                    disabled={isChatting || !inputValue.trim()}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
