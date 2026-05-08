import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api.js";
import ToolCallBlock from "./ToolCallBlock.jsx";

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.getHistory().then(setMessages).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setError(null);
    setSending(true);
    const optimistic = {
      role: "user",
      content: text,
      timestamp: Date.now() / 1000,
      tool_calls: [],
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");
    try {
      const res = await api.sendMessage(text);
      setMessages((prev) => [...prev, res.message]);
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  async function clear() {
    if (!confirm("Clear chat history?")) return;
    try {
      await api.clearHistory();
      setMessages([]);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Chat</h2>
        <button className="secondary" onClick={clear}>Clear</button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div style={{ color: "#6e6e73", textAlign: "center", padding: "2rem" }}>
            Start a conversation. Configure your LLM in the Settings tab first.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.tool_calls && m.tool_calls.length > 0 && (
              <div>
                {m.tool_calls.map((c, j) => (
                  <ToolCallBlock key={j} call={c} />
                ))}
              </div>
            )}
            {m.content && (
              m.role === "assistant" ? (
                <div className="markdown"><ReactMarkdown>{m.content}</ReactMarkdown></div>
              ) : (
                <div>{m.content}</div>
              )
            )}
          </div>
        ))}
        {sending && <div className="msg assistant" style={{ opacity: 0.6 }}>Thinking…</div>}
      </div>
      <div className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type a message (Shift+Enter for newline)…"
          disabled={sending}
        />
        <button className="primary" onClick={send} disabled={sending || !input.trim()}>
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
