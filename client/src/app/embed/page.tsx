'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
}

function EmbedChatWidget() {
  const searchParams = useSearchParams();
  const workspaceId = searchParams.get('workspace_id') || '';

  const [isOpen, setIsOpen] = useState(false);
  const [visitorId, setVisitorId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'bot',
      text: 'Hello! How can I help you today?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [domainError, setDomainError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize Anonymous Visitor Session ID
  useEffect(() => {
    if (typeof window !== 'undefined') {
      let savedId = localStorage.getItem('widget_visitor_id');
      if (!savedId) {
        savedId = `anon_${crypto.randomUUID()}`;
        localStorage.setItem('widget_visitor_id', savedId);
      }
      setVisitorId(savedId);
    }
  }, []);

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Send postMessage to Parent Host Window to Resize Iframe
  const toggleWidget = (nextState: boolean) => {
    setIsOpen(nextState);

    if (typeof window !== 'undefined') {
      window.parent.postMessage(
        {
          type: 'TOGGLE_WIDGET',
          isOpen: nextState,
        },
        '*'
      );
    }
  };

  // Handle Sending Chat Messages
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userText = inputValue.trim();
    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);
    setDomainError(null);

    try {
      // Send chat request to public embed chat endpoint
      const response = await fetch('/api/embed/sendMessage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          session_id: visitorId,
          message: userText,
        }),
      });

      if (response.status === 403) {
        const errData = await response.json();
        setDomainError(errData.message || 'Domain not authorized to embed this widget.');
        setIsLoading(false);
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to fetch response');
      }

      // Handle streaming or plain text response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let botResponseText = '';

      const botMsgId = (Date.now() + 1).toString();
      const botMsg: Message = {
        id: botMsgId,
        sender: 'bot',
        text: '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMsg]);

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          botResponseText += chunk;

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === botMsgId ? { ...msg, text: botResponseText } : msg
            )
          );
        }
      } else {
        const data = await response.json();
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === botMsgId ? { ...msg, text: data.reply || data.content || 'Response received' } : msg
          )
        );
      }
    } catch (err: any) {
      console.error('Embed chat error:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'bot',
          text: 'Sorry, I am unable to connect right now. Please try again later.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Render State A: Collapsed Bubble Button (64px)
  if (!isOpen) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-transparent">
        <button
          onClick={() => toggleWidget(true)}
          className="w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-105 active:scale-95 focus:outline-none cursor-pointer"
          title="Open Assistant"
        >
          <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </button>
      </div>
    );
  }

  // Render State B: Expanded Chat Box Window (380px x 600px)
  return (
    <div className="w-full h-full flex flex-col bg-white rounded-2xl border border-gray-200 shadow-2xl overflow-hidden font-sans">
      {/* Widget Header */}
      <header className="bg-blue-600 px-4 py-3.5 text-white flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center space-x-2.5">
          <div className="w-3 h-3 bg-emerald-400 rounded-full animate-pulse" />
          <div>
            <h3 className="font-semibold text-sm leading-tight">AI Assistant</h3>
            <p className="text-[11px] text-blue-100 opacity-90">Powered by RAG</p>
          </div>
        </div>
        <button
          onClick={() => toggleWidget(false)}
          className="p-1 rounded-lg text-blue-100 hover:bg-blue-500 hover:text-white transition-colors cursor-pointer"
          title="Close Assistant"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </header>

      {/* Domain Authorization Error Alert */}
      {domainError && (
        <div className="bg-red-50 border-b border-red-200 text-red-700 text-xs p-3 font-medium">
          ⚠️ {domainError}
        </div>
      )}

      {/* Messages Scroll Area */}
      <main className="flex-1 p-4 overflow-y-auto space-y-3 bg-slate-50">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-xs sm:text-sm leading-relaxed shadow-sm ${
                msg.sender === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-white text-slate-800 border border-slate-200/80 rounded-bl-none'
              }`}
            >
              {msg.text}
            </div>
            <span className="text-[10px] text-slate-400 mt-1 px-1">{msg.timestamp}</span>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center space-x-2 bg-white border border-slate-200 p-3 rounded-2xl rounded-bl-none max-w-[80%] w-fit">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Message Input Form */}
      <form onSubmit={handleSendMessage} className="p-3 bg-white border-t border-slate-200 flex items-center space-x-2 shrink-0">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 bg-slate-100 text-slate-800 placeholder-slate-400 text-xs sm:text-sm px-3.5 py-2.5 rounded-xl border border-transparent focus:border-blue-500 focus:bg-white focus:outline-none transition-all"
        />
        <button
          type="submit"
          disabled={!inputValue.trim() || isLoading}
          className="p-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4 transform rotate-90" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
          </svg>
        </button>
      </form>
    </div>
  );
}

export default function EmbedPage() {
  return (
    <Suspense fallback={<div className="w-full h-full bg-transparent" />}>
      <EmbedChatWidget />
    </Suspense>
  );
}
