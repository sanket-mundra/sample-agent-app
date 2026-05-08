import React from "react";

export default function ToolCallBlock({ call }) {
  const { server_name, tool_name, arguments: args, result, error } = call;
  return (
    <details className="tool-call">
      <summary>
        <span className="server-name">{server_name}</span>
        <span className="tool-name">{tool_name}</span>
        {error ? " · error" : result ? "" : " · pending"}
      </summary>
      <div className="body">
        <div>
          <strong>Arguments</strong>
          <pre>{JSON.stringify(args || {}, null, 2)}</pre>
        </div>
        {error ? (
          <div className="error">
            <strong>Error</strong>
            <pre>{error}</pre>
          </div>
        ) : (
          <div>
            <strong>Result</strong>
            <pre>{result ?? "(no result)"}</pre>
          </div>
        )}
      </div>
    </details>
  );
}
