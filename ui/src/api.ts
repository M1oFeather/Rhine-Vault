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

export type NodeTypeOption = {
  id: string;
  display_name: string;
  description?: string;
  category?: string;
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

export type LibrarySnapshot = {
  snapshot_id: string;
  workspace_id: string;
  version: string;
  manifest_hash: string;
  manifest: Record<string, unknown>;
  snapshot_path: string;
  created_at: string;
};

export type WorkspaceDependency = {
  project_workspace_id: string;
  alias: string;
  library_workspace_id: string;
  version_requirement: string;
  resolved_version: string;
  manifest_hash: string;
  status: string;
};

export type WorkspaceRecord = {
  workspace_id: string;
  workspace_type: "project" | "library";
  display_name: string;
  root_path?: string;
  vault_root?: string;
};

export type ApiRecord = Record<string, any>;

export let workspaceId = localStorage.getItem("rhine-vault-workspace-id") || "demo-workspace";

export function getWorkspaceId(): string {
  return workspaceId;
}

export function setWorkspaceId(nextWorkspaceId: string): void {
  workspaceId = nextWorkspaceId;
  localStorage.setItem("rhine-vault-workspace-id", nextWorkspaceId);
}

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
    signal,
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
  enable_vector: boolean;
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

export function createManualProposal(body: {
  title: string;
  node_type: string;
  content: string;
  authority: string;
  tags: string[];
}): Promise<ApiRecord> {
  return postJson("/api/manual", {workspace_id: workspaceId, ...body});
}

export function importDocument(path: string): Promise<ApiRecord> {
  return postJson("/api/documents/import", {workspace_id: workspaceId, path});
}

export function documentImporters(): Promise<ApiRecord> {
  return getJson("/api/documents/importers");
}

export function listNodeTypes(locale = "zh"): Promise<{
  default_locale: string;
  locale: string;
  extension_policy: Record<string, unknown>;
  node_types: NodeTypeOption[];
}> {
  return getJson(`/api/node-types?locale=${encodeURIComponent(locale)}`);
}

export function listWorkspaces(): Promise<WorkspaceRecord[]> {
  return getJson("/api/workspaces");
}

export function registerWorkspace(body: {
  workspace_id: string;
  workspace_type: "project" | "library";
  display_name?: string;
}): Promise<WorkspaceRecord> {
  return postJson("/api/workspaces", body);
}

export function importPtilopsisSeed(body: {
  workspace_id?: string;
  display_name?: string;
  stage: boolean;
  approve: boolean;
}): Promise<ApiRecord> {
  return postJson("/api/seeds/ptilopsis", body);
}

export function scanProject(root: string): Promise<ApiRecord> {
  return postJson("/api/projects/scan", {workspace_id: workspaceId, root});
}

export function captureConversation(messages: ChatMessage[]): Promise<ApiRecord> {
  return postJson("/api/conversations/capture", {
    workspace_id: workspaceId,
    session_id: `element-chat-${Date.now()}`,
    messages: messages.map((message, index) => ({
      message_id: `message-${Date.now()}-${index + 1}`,
      role: message.role,
      content: message.content,
    })),
  });
}

export function listProposals(): Promise<ApiRecord[]> {
  return getJson(`/api/proposals?workspace_id=${workspaceId}`);
}

export function stageProposal(proposalId: string, temporaryIds: string[]): Promise<ApiRecord[]> {
  return postJson(`/api/proposals/${proposalId}/stage`, {
    workspace_id: workspaceId,
    temporary_ids: temporaryIds,
  });
}

export function rejectProposal(proposalId: string): Promise<ApiRecord> {
  return postJson(`/api/proposals/${proposalId}/reject`, {workspace_id: workspaceId});
}

export function listStaging(status = "pending"): Promise<ApiRecord[]> {
  return getJson(`/api/staging?workspace_id=${workspaceId}&status=${encodeURIComponent(status)}`);
}

export function approveStaging(entryIds: string[]): Promise<ApiRecord[]> {
  return postJson("/api/staging/approve", {
    workspace_id: workspaceId,
    entry_ids: entryIds,
  });
}

export function listNodes(): Promise<ApiRecord[]> {
  return getJson(`/api/nodes?workspace_id=${workspaceId}`);
}

export function listNodeRevisions(nodeId: string): Promise<ApiRecord[]> {
  return getJson(`/api/nodes/${encodeURIComponent(nodeId)}/revisions?workspace_id=${workspaceId}`);
}

export function rollbackNode(nodeId: string, revision: number): Promise<ApiRecord> {
  return postJson(`/api/nodes/${encodeURIComponent(nodeId)}/rollback`, {
    workspace_id: workspaceId,
    revision,
  });
}

export function listChangesets(): Promise<ApiRecord[]> {
  return getJson(`/api/changesets?workspace_id=${workspaceId}`);
}

export function listAuditEvents(): Promise<ApiRecord[]> {
  return getJson(`/api/audit-events?workspace_id=${workspaceId}`);
}

export function detectExternalChanges(): Promise<ApiRecord[]> {
  return postJson("/api/external-changes/detect", {workspace_id: workspaceId});
}

export function listExternalChanges(): Promise<ApiRecord[]> {
  return getJson(`/api/external-changes?workspace_id=${workspaceId}`);
}

export function approveExternalChange(changeId: string): Promise<ApiRecord> {
  return postJson(`/api/external-changes/${encodeURIComponent(changeId)}/approve`, {
    workspace_id: workspaceId,
  });
}

export function rejectExternalChange(changeId: string): Promise<ApiRecord> {
  return postJson(`/api/external-changes/${encodeURIComponent(changeId)}/reject`, {
    workspace_id: workspaceId,
  });
}

export function createWorkspaceSnapshot(): Promise<ApiRecord> {
  return postJson("/api/recovery/snapshots/workspace", {workspace_id: workspaceId});
}

export function buildImportPlan(packagePath: string): Promise<ApiRecord> {
  return postJson("/api/recovery/import-plan", {package_path: packagePath});
}

export function applyImportPlan(body: {
  package_path: string;
  target_workspace_id?: string;
  approve: boolean;
  overwrite: boolean;
}): Promise<ApiRecord> {
  return postJson("/api/recovery/import-apply", body);
}

export function emergencyReadonly(): Promise<ApiRecord> {
  return getJson(`/api/recovery/emergency-readonly?workspace_id=${workspaceId}`);
}

export function localGraph(body: {
  node_id?: string;
  depth: number;
  limit: number;
}): Promise<ApiRecord> {
  const params = new URLSearchParams({
    workspace_id: workspaceId,
    depth: String(body.depth),
    limit: String(body.limit),
  });
  if (body.node_id) {
    params.set("node_id", body.node_id);
  }
  return getJson(`/api/graph/local?${params.toString()}`);
}

export function vectorSearch(body: {query: string; result_limit: number}): Promise<ApiRecord> {
  return postJson("/api/vector/search", {workspace_id: workspaceId, ...body});
}

export function vectorBackends(): Promise<ApiRecord> {
  return getJson("/api/vector/backends");
}

export function mcpCapabilities(): Promise<McpCapabilities> {
  return getJson("/api/mcp/capabilities");
}

export function callMcpTool(
  toolName: string,
  argumentsJson: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return postJson(`/api/mcp/tools/${toolName}`, {arguments: argumentsJson});
}

export function readMcpResource(uri: string): Promise<Record<string, unknown>> {
  return getJson(`/api/mcp/resources?uri=${encodeURIComponent(uri)}`);
}

export function processIndexJobs(workspace_id: string): Promise<Record<string, unknown>> {
  return postJson("/api/index-jobs/process", {workspace_id});
}

export function rebuildIndexJobs(workspace_id: string): Promise<Record<string, unknown>[]> {
  return postJson("/api/index-jobs/rebuild", {workspace_id});
}

export function listIndexChunks(workspace_id: string): Promise<Record<string, unknown>[]> {
  return getJson(`/api/index-chunks?workspace_id=${encodeURIComponent(workspace_id)}`);
}

export function publishLibrarySnapshot(body: {
  workspace_id: string;
  version: string;
  git_tag?: string;
  commit_hash?: string;
}): Promise<LibrarySnapshot> {
  return postJson(`/api/libraries/${body.workspace_id}/snapshots`, {
    version: body.version,
    git_tag: body.git_tag || undefined,
    commit_hash: body.commit_hash || undefined,
  });
}

export function listLibrarySnapshots(workspace_id: string): Promise<LibrarySnapshot[]> {
  return getJson(`/api/libraries/${encodeURIComponent(workspace_id)}/snapshots`);
}

export function lockWorkspaceDependency(body: {
  project_workspace_id: string;
  alias: string;
  library_workspace_id: string;
  version: string;
  version_requirement?: string;
}): Promise<WorkspaceDependency> {
  return postJson(`/api/workspaces/${body.project_workspace_id}/dependencies`, {
    alias: body.alias,
    library_workspace_id: body.library_workspace_id,
    version: body.version,
    version_requirement: body.version_requirement || undefined,
  });
}

export function listWorkspaceDependencies(
  project_workspace_id: string,
): Promise<WorkspaceDependency[]> {
  return getJson(`/api/workspaces/${encodeURIComponent(project_workspace_id)}/dependencies`);
}

export function dependencyUpgradeReport(
  project_workspace_id: string,
  alias: string,
): Promise<Record<string, unknown>> {
  return getJson(
    `/api/workspaces/${encodeURIComponent(project_workspace_id)}/dependencies/${encodeURIComponent(alias)}/upgrade-report`,
  );
}

export function sendChatMessage(
  model: ModelConfig,
  messages: ChatMessage[],
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  if (model.provider === "fake") {
    const lastUserMessage = [...messages].reverse().find((message) => message.role === "user");
    return postJson(
      "/api/llm/fake",
      {
        workspace_id: workspaceId,
        query: lastUserMessage?.content ?? "",
      },
      signal,
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
      reasoning_effort: model.reasoningEffort || undefined,
    },
    signal,
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
      model: "fake",
    },
    {
      id: "deepseek-v4-flash",
      displayName: "DeepSeek V4 Flash",
      provider: "openai-compatible",
      providerKind: "deepseek",
      baseUrl: "https://api.deepseek.com",
      model: "deepseek-v4-flash",
    },
    {
      id: "deepseek-v4-pro",
      displayName: "DeepSeek V4 Pro",
      provider: "openai-compatible",
      providerKind: "deepseek",
      baseUrl: "https://api.deepseek.com",
      model: "deepseek-v4-pro",
      thinkingEnabled: true,
      reasoningEffort: "high",
    },
  ];
}
