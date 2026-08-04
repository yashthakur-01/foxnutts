"use client";

import { useEffect, useState, useRef } from "react";
import { createClient } from "../../supabase/browserClient";
import { useRouter } from "next/navigation";

export default function ChatDashboard() {
  const supabase = createClient();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  
  // File Upload State
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);

  // Chat State
  const [messages, setMessages] = useState<{ role: "human" | "ai"; content: string }[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isChatting, setIsChatting] = useState(false);
  const sessionId = useRef(`session-${Math.random().toString(36).substring(7)}`);

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

  const handleFileUpload = async () => {
    if (!file || !workspaceId) return;
    setIsUploading(true);
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
      const { uploadUrl, uniqueFileName } = await presignedRes.json();

      setUploadStatus("Uploading file to Cloudflare R2...");
      // 2. Upload directly to R2
      const r2Res = await fetch(uploadUrl, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file
      });

      if (!r2Res.ok) throw new Error("Failed to upload to R2");

      setUploadStatus("Processing document with FastAPI...");
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

      setUploadStatus("✅ Document uploaded and processed successfully!");
      setFile(null);
    } catch (err: any) {
      console.error(err);
      setUploadStatus(`❌ Error: ${err.message}`);
    } finally {
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
    await supabase.auth.signOut();
    router.push("/login");
  };

  if (loading) {
    return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Loading Test Dashboard...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="max-w-6xl mx-auto flex gap-8">
        
        {/* Left Column: Upload */}
        <div className="w-1/3 space-y-6">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-white">Data Ingestion</h2>
              <button onClick={handleLogout} className="text-sm text-red-400 hover:text-red-300">Logout</button>
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
              {uploadStatus && (
                <div className="text-sm text-gray-300 bg-gray-800/50 p-3 rounded border border-gray-700 break-words">
                  {uploadStatus}
                </div>
              )}
            </div>
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
    </div>
  );
}
