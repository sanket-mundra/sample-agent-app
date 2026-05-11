import React, { useState } from "react";
import Chat from "./components/Chat.jsx";
import LLMSettings from "./components/LLMSettings.jsx";
import MCPSettings from "./components/MCPSettings.jsx";
import Observability from "./components/Observability.jsx";

const TABS = [
  { id: "chat", label: "Chat" },
  { id: "llm", label: "LLM Settings" },
  { id: "mcp", label: "MCP Servers" },
  { id: "observability", label: "Observability" },
];

export default function App() {
  const [tab, setTab] = useState("chat");
  return (
    <div className="app">
      <h1 style={{ fontSize: "1.25rem" }}>Sample Agent App</h1>
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "chat" && <Chat />}
      {tab === "llm" && <LLMSettings />}
      {tab === "mcp" && <MCPSettings />}
      {tab === "observability" && <Observability />}
    </div>
  );
}
