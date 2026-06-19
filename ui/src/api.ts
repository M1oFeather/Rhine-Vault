export type RetrievalProfile = {
  profile_id: string;
  name: string;
  relation_depth: number;
  result_limit: number;
};

export type ModelConfig = {
  id: string;
  displayName: string;
  provider: "fake" | "openai-compatible";
  providerKind: "fake" | "deepseek" | "openai" | "custom" | "local";
  baseUrl: string;
  model: string;
  apiKey?: string;
  thinkingEnabled?: boolean;
  reasoningEffort?: string;
};

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type McpToolDefinition = {
  name: string;
  description: string;
  write_scope: string;
  input_schema: Record<string, unknown>;
};

export type McpCapabilities = {
  phase: string;
  transport_neutral: boolean;
  tools: McpToolDefinition[];
  resources: string[];
  forbidden_tools: string[];
  approval_policy: string;
  streamable_http: {
    enabled: boolean;
    mount_path: string;
    error?: string | null;
  };
};

export const workspaceId = "demo-workspace";

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
    signal
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function retrievalProfiles(): Promise<{
  default_profile_id: string;
  profiles: RetrievalProfile[];
}> {
  return getJson(`/api/retrieval/profiles?workspace_id=${workspaceId}`);
}

export function retrievalLab(body: {
  query: string;
  profile_id: string;
  result_limit: number;
  relation_depth: number;
  node_type?: string;
  authority?: string;
  tags: string[];
  include_deprecated: boolean;
}): Promise<Record<string, unknown>> {
  return postJson("/api/retrieval/lab", {workspace_id: workspaceId, ...body});
}

export function buildContextBundle(body: {
  query: string;
  profile_id: string;
}): Promise<Record<string, unknown>> {
  return postJson("/api/context", {workspace_id: workspaceId, ...body});
}

export function mcpCapabilities(): Promise<McpCapabilities> {
  return getJson("/api/mcp/capabilities");
}

export function callMcpTool(
  toolName: string,
  argumentsJson: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return postJson(`/api/mcp/tools/${toolName}`, {arguments: argumentsJson});
}

export function readMcpResource(uri: string): Promise<Record<string, unknown>> {
  return getJson(`/api/mcp/resources?uri=${encodeURIComponent(uri)}`);
}

export function sendChatMessage(
  model: ModelConfig,
  messages: ChatMessage[],
  signal?: AbortSignal
): Promise<Record<string, unknown>> {
  if (model.provider === "fake") {
    const lastUserMessage = [...messages].reverse().find((message) => message.role === "user");
    return postJson(
      "/api/llm/fake",
      {
        workspace_id: workspaceId,
        query: lastUserMessage?.content ?? ""
      },
      signal
    );
  }
  return postJson(
    "/api/llm/openai-compatible/chat",
    {
      workspace_id: workspaceId,
      base_url: model.baseUrl,
      model: model.model,
      api_key: model.apiKey || undefined,
      messages,
      thinking_enabled: Boolean(model.thinkingEnabled),
      reasoning_effort: model.reasoningEffort || undefined
    },
    signal
  );
}

export function defaultModels(): ModelConfig[] {
  return [
    {
      id: "fake-offline",
      displayName: "FakeLLM 离线测试",
      provider: "fake",
      providerKind: "fake",
      baseUrl: "",
      model: "fake"
    },
    {
      id: "deepseek-v4-flash",
      displayName: "DeepSeek V4 Flash",
      provider: "openai-compatible",
      providerKind: "deepseek",
      baseUrl: "https://api.deepseek.com",
      model: "deepseek-v4-flash"
    },
    {
      id: "deepseek-v4-pro",
      displayName: "DeepSeek V4 Pro",
      provider: "openai-compatible",
      providerKind: "deepseek",
      baseUrl: "https://api.deepseek.com",
      model: "deepseek-v4-pro",
      thinkingEnabled: true,
      reasoningEffort: "high"
    }
  ];
}
