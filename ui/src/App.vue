<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  type ApiRecord,
  type ChatMessage,
  type LibrarySnapshot,
  type McpCapabilities,
  type ModelConfig,
  type RetrievalProfile,
  type WorkspaceDependency,
  approveExternalChange,
  approveStaging,
  buildContextBundle,
  buildImportPlan,
  callMcpTool,
  captureConversation,
  createManualProposal,
  createWorkspaceSnapshot,
  defaultModels,
  dependencyUpgradeReport,
  detectExternalChanges,
  emergencyReadonly,
  importDocument,
  listAuditEvents,
  listChangesets,
  listExternalChanges,
  listIndexChunks,
  listLibrarySnapshots,
  listNodeRevisions,
  listNodes,
  listProposals,
  listStaging,
  listWorkspaceDependencies,
  lockWorkspaceDependency,
  mcpCapabilities,
  processIndexJobs,
  publishLibrarySnapshot,
  readMcpResource,
  rebuildIndexJobs,
  rejectExternalChange,
  rejectProposal,
  retrievalLab,
  retrievalProfiles,
  rollbackNode,
  scanProject,
  sendChatMessage,
  stageProposal,
  vectorBackends,
  vectorSearch,
} from "./api";
import GameIcon from "./components/GameIcon.vue";
import type { GameIconName } from "./icons/gameIconPack";

type Activity =
  | "capture"
  | "retrieve"
  | "chat"
  | "nodes"
  | "review"
  | "mcp"
  | "library"
  | "recovery"
  | "settings";

const tabs: { id: Activity; label: string; icon: GameIconName; description: string }[] = [
  { id: "capture", label: "知识采集", icon: "upload", description: "手动、文档与项目导入" },
  { id: "retrieve", label: "检索实验台", icon: "search", description: "Context Bundle 与向量召回" },
  { id: "chat", label: "对话", icon: "chat", description: "模型问答与采集前对话" },
  { id: "nodes", label: "节点目录", icon: "nodes", description: "正式知识浏览入口" },
  { id: "review", label: "审核队列", icon: "review", description: "候选知识与审批流" },
  { id: "mcp", label: "MCP 边界", icon: "link", description: "受限工具与资源" },
  { id: "library", label: "Library", icon: "book", description: "索引、快照与依赖锁" },
  { id: "recovery", label: "恢复", icon: "download", description: "Snapshot、Import Plan 与只读恢复" },
  { id: "settings", label: "系统设置", icon: "settings", description: "模型配置与本地偏好" },
];

const activity = ref<Activity>("capture");
const profiles = ref<RetrievalProfile[]>([]);
const selectedProfileId = ref("technical-documentation");
const query = ref("approval constraints");
const resultLimit = ref(8);
const relationDepth = ref(1);
const nodeType = ref("");
const authority = ref("");
const tags = ref("");
const includeDeprecated = ref(false);
const enableVector = ref(false);
const runState = ref<Record<string, unknown> | null>(null);
const running = ref(false);
const busyAction = ref("");
const runStateCollapsed = ref(false);
const notice = ref("就绪");
const sidebarCollapsed = ref(false);

const models = ref<ModelConfig[]>(loadModels());
const selectedModelId = ref(models.value[0]?.id ?? "");
const chatInput = ref("");
const chatMessages = ref<ChatMessage[]>([]);
const activeController = ref<AbortController | null>(null);
const mcpState = ref<McpCapabilities | null>(null);
const selectedMcpTool = ref("search_nodes");
const mcpArgumentsText = ref('{"workspace_id":"demo-workspace","query":"approval"}');
const mcpResourceUri = ref("rhine://workspace/demo-workspace/schema/memory-node");
const indexWorkspaceId = ref("demo-workspace");
const libraryWorkspaceId = ref("library-neoforge-1-21-1");
const libraryVersion = ref("1.0.0");
const libraryGitTag = ref("v1.0.0");
const libraryCommitHash = ref("");
const projectWorkspaceId = ref("demo-workspace");
const dependencyAlias = ref("neoforge");
const versionRequirement = ref("~1.0.0");
const snapshots = ref<LibrarySnapshot[]>([]);
const dependencies = ref<WorkspaceDependency[]>([]);
const manualTitle = ref("新的知识节点");
const manualNodeType = ref("Note");
const manualAuthority = ref("approved");
const manualTags = ref("rhine");
const manualContent = ref("在这里记录需要进入审核流程的知识。");
const documentPath = ref("");
const projectRoot = ref("");
const proposals = ref<ApiRecord[]>([]);
const selectedProposalId = ref("");
const selectedTemporaryIds = ref<string[]>([]);
const stagingEntries = ref<ApiRecord[]>([]);
const selectedStagingIds = ref<string[]>([]);
const nodes = ref<ApiRecord[]>([]);
const selectedNodeId = ref("");
const nodeRevisions = ref<ApiRecord[]>([]);
const rollbackRevision = ref(1);
const changesets = ref<ApiRecord[]>([]);
const auditEvents = ref<ApiRecord[]>([]);
const externalChanges = ref<ApiRecord[]>([]);
const selectedExternalChangeId = ref("");
const importPackagePath = ref("");
const recoveryState = ref<ApiRecord | null>(null);
const vectorQuery = ref("approved chunk indexes");
const vectorBackendState = ref<ApiRecord | null>(null);

const activeTabMeta = computed(() => {
  return tabs.find((tab) => tab.id === activity.value) ?? tabs[0];
});

const selectedProposal = computed(() => {
  return proposals.value.find((proposal) => proposal.proposal_id === selectedProposalId.value);
});

const selectedNode = computed(() => {
  return nodes.value.find((node) => node.node_id === selectedNodeId.value);
});

const selectedModel = computed(() => {
  return models.value.find((model) => model.id === selectedModelId.value) ?? models.value[0];
});

onMounted(async () => {
  await perform("初始化", async () => {
    const payload = await retrievalProfiles();
    profiles.value = payload.profiles;
    selectedProfileId.value = payload.default_profile_id;
    mcpState.value = await mcpCapabilities();
    await Promise.allSettled([
      refreshProposals(),
      refreshStaging(),
      refreshNodes(),
      refreshWorkflowState(),
    ]);
    return {ready: true};
  });
});

async function perform<T>(
  label: string,
  task: () => Promise<T>,
  options: {silent?: boolean; collapseOutput?: boolean} = {},
): Promise<T | null> {
  busyAction.value = label;
  if (!options.silent) {
    notice.value = `${label}...`;
  }
  try {
    const result = await task();
    if (result !== undefined) {
      runState.value = result as Record<string, unknown>;
    }
    if (!options.silent) {
      notice.value = `${label}完成`;
    }
    if (!options.collapseOutput) {
      runStateCollapsed.value = false;
    }
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    runState.value = {error: message, action: label};
    notice.value = `${label}失败`;
    runStateCollapsed.value = false;
    return null;
  } finally {
    busyAction.value = "";
  }
}

async function openActivity(next: Activity): Promise<void> {
  activity.value = next;
  if (next === "capture") {
    await perform("加载采集队列", refreshProposals, {silent: true, collapseOutput: true});
  } else if (next === "retrieve") {
    await runVectorBackendProbe({silent: true});
  } else if (next === "nodes") {
    await perform("加载节点目录", refreshNodes, {silent: true, collapseOutput: true});
  } else if (next === "review") {
    await perform(
      "加载审核队列",
      async () => {
        await Promise.all([refreshProposals(), refreshStaging(), refreshWorkflowState()]);
        return {proposals: proposals.value.length, staging: stagingEntries.value.length};
      },
      {silent: true, collapseOutput: true},
    );
  } else if (next === "mcp") {
    await perform("加载 MCP 能力", refreshMcpCapabilities, {silent: true, collapseOutput: true});
  } else if (next === "library") {
    await perform(
      "加载 Library 状态",
      async () => {
        await Promise.all([runListLibrarySnapshots(), runListWorkspaceDependencies()]);
        return {snapshots: snapshots.value.length, dependencies: dependencies.value.length};
      },
      {silent: true, collapseOutput: true},
    );
  }
}

async function runRetrievalLab(): Promise<void> {
  running.value = true;
  try {
    await perform("运行 Retrieval Lab", () => retrievalLab({
      query: query.value,
      profile_id: selectedProfileId.value,
      result_limit: resultLimit.value,
      relation_depth: relationDepth.value,
      node_type: nodeType.value || undefined,
      authority: authority.value || undefined,
      tags: tags.value
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      include_deprecated: includeDeprecated.value,
      enable_vector: enableVector.value,
    }));
  } finally {
    running.value = false;
  }
}

async function runContextBundle(): Promise<void> {
  running.value = true;
  try {
    await perform("构建 Context Bundle", () => buildContextBundle({
      query: query.value,
      profile_id: selectedProfileId.value,
    }));
  } finally {
    running.value = false;
  }
}

function splitTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function submitManualProposal(): Promise<void> {
  const proposal = await perform("创建手动 Proposal", () =>
    createManualProposal({
      title: manualTitle.value,
      node_type: manualNodeType.value,
      content: manualContent.value,
      authority: manualAuthority.value,
      tags: splitTags(manualTags.value),
    }),
  );
  if (!proposal) {
    return;
  }
  await refreshProposals();
  selectedProposalId.value = String(proposal.proposal_id ?? "");
  selectedTemporaryIds.value = ((proposal.proposed_nodes ?? []) as ApiRecord[]).map((node) =>
    String(node.temporary_id),
  );
  await openActivity("review");
}

async function captureChatAsProposal(): Promise<void> {
  if (chatMessages.value.length === 0) {
    runState.value = {error: "当前对话为空。"};
    return;
  }
  const proposal = await perform("采集当前对话", () => captureConversation(chatMessages.value));
  if (!proposal) {
    return;
  }
  await refreshProposals();
  selectedProposalId.value = String(proposal.proposal_id ?? "");
  selectedTemporaryIds.value = ((proposal.proposed_nodes ?? []) as ApiRecord[]).map((node) =>
    String(node.temporary_id),
  );
  await openActivity("review");
}

async function submitAndStageManualProposal(): Promise<void> {
  await submitManualProposal();
  if (selectedProposalId.value) {
    await runStageProposal();
  }
}

async function submitAndApproveManualProposal(): Promise<void> {
  await submitAndStageManualProposal();
  if (selectedStagingIds.value.length > 0) {
    await runApproveStaging();
    activity.value = "nodes";
  }
}

async function runDocumentImport(): Promise<void> {
  const result = await perform("导入文档", () => importDocument(documentPath.value));
  if (!result) {
    return;
  }
  await refreshProposals();
  await openActivity("review");
}

async function runProjectScan(): Promise<void> {
  const result = await perform("扫描项目", () => scanProject(projectRoot.value));
  if (!result) {
    return;
  }
  await refreshProposals();
  await openActivity("review");
}

async function refreshProposals(): Promise<ApiRecord[]> {
  proposals.value = await listProposals();
  if (!selectedProposalId.value && proposals.value.length > 0) {
    selectProposal(proposals.value[0]);
  }
  return proposals.value;
}

function selectProposal(row: ApiRecord | undefined): void {
  selectedProposalId.value = String(row?.proposal_id ?? "");
  selectedTemporaryIds.value = ((row?.proposed_nodes ?? []) as ApiRecord[]).map((node) =>
    String(node.temporary_id),
  );
}

async function runStageProposal(): Promise<void> {
  if (!selectedProposalId.value) {
    runState.value = {error: "请先选择 proposal。"};
    return;
  }
  const temporaryIds =
    selectedTemporaryIds.value.length > 0
      ? selectedTemporaryIds.value
      : ((selectedProposal.value?.proposed_nodes ?? []) as ApiRecord[]).map((node) =>
          String(node.temporary_id),
        );
  const result = await perform("保存为 staging", () =>
    stageProposal(selectedProposalId.value, temporaryIds),
  );
  if (result) {
    await refreshStaging();
    selectedStagingIds.value = (result as ApiRecord[]).map((entry) => String(entry.entry_id));
  }
}

async function runRejectProposal(): Promise<void> {
  if (!selectedProposalId.value) {
    runState.value = {error: "请先选择 proposal。"};
    return;
  }
  await perform("驳回 Proposal", () => rejectProposal(selectedProposalId.value));
  selectedProposalId.value = "";
  selectedTemporaryIds.value = [];
  await refreshProposals();
}

async function refreshStaging(): Promise<ApiRecord[]> {
  stagingEntries.value = await listStaging();
  selectedStagingIds.value = stagingEntries.value.map((entry) => String(entry.entry_id));
  return stagingEntries.value;
}

async function runApproveStaging(): Promise<void> {
  if (selectedStagingIds.value.length === 0) {
    runState.value = {error: "请至少选择一个 staging 条目。"};
    return;
  }
  await perform("批准 staging", () => approveStaging(selectedStagingIds.value));
  await Promise.all([refreshStaging(), refreshNodes(), refreshWorkflowState()]);
}

async function refreshNodes(): Promise<ApiRecord[]> {
  nodes.value = await listNodes();
  if (!selectedNodeId.value && nodes.value.length > 0) {
    selectNode(nodes.value[0]);
  } else if (selectedNodeId.value) {
    await refreshNodeRevisions();
  }
  return nodes.value;
}

function selectNode(row: ApiRecord | undefined): void {
  selectedNodeId.value = String(row?.node_id ?? "");
  void refreshNodeRevisions();
}

async function refreshNodeRevisions(): Promise<ApiRecord[]> {
  if (!selectedNodeId.value) {
    nodeRevisions.value = [];
    return nodeRevisions.value;
  }
  nodeRevisions.value = await listNodeRevisions(selectedNodeId.value);
  rollbackRevision.value = Number(nodeRevisions.value[0]?.revision ?? selectedNode.value?.revision ?? 1);
  return nodeRevisions.value;
}

async function runRollbackNode(): Promise<void> {
  if (!selectedNodeId.value) {
    runState.value = {error: "请先选择节点。"};
    return;
  }
  await perform("生成回滚 revision", () =>
    rollbackNode(selectedNodeId.value, rollbackRevision.value),
  );
  await Promise.all([refreshNodes(), refreshWorkflowState()]);
}

async function refreshWorkflowState(): Promise<ApiRecord> {
  const [changesetRows, auditRows, externalRows] = await Promise.all([
    listChangesets(),
    listAuditEvents(),
    listExternalChanges(),
  ]);
  changesets.value = changesetRows;
  auditEvents.value = auditRows;
  externalChanges.value = externalRows;
  if (!selectedExternalChangeId.value && externalChanges.value.length > 0) {
    selectedExternalChangeId.value = String(externalChanges.value[0].change_id);
  }
  return {
    changesets: changesets.value.length,
    audit_events: auditEvents.value.length,
    external_changes: externalChanges.value.length,
  };
}

function selectExternalChange(row: ApiRecord | undefined): void {
  selectedExternalChangeId.value = String(row?.change_id ?? "");
}

async function runDetectExternalChanges(): Promise<void> {
  await perform("检测外部变更", () => detectExternalChanges());
  await refreshWorkflowState();
}

async function runApproveExternalChange(): Promise<void> {
  if (!selectedExternalChangeId.value) {
    runState.value = {error: "请先选择 ExternalChange。"};
    return;
  }
  await perform("批准外部变更", () => approveExternalChange(selectedExternalChangeId.value));
  await Promise.all([refreshWorkflowState(), refreshNodes()]);
}

async function runRejectExternalChange(): Promise<void> {
  if (!selectedExternalChangeId.value) {
    runState.value = {error: "请先选择 ExternalChange。"};
    return;
  }
  await perform("驳回外部变更", () => rejectExternalChange(selectedExternalChangeId.value));
  await refreshWorkflowState();
}

async function runCreateWorkspaceSnapshot(): Promise<void> {
  const result = await perform("创建 Snapshot", () => createWorkspaceSnapshot());
  recoveryState.value = result;
  if (result) {
    importPackagePath.value = String(result.package_path ?? importPackagePath.value);
  }
}

async function runBuildImportPlan(): Promise<void> {
  recoveryState.value = await perform("验证 Import Plan", () =>
    buildImportPlan(importPackagePath.value),
  );
}

async function runEmergencyReadonly(): Promise<void> {
  recoveryState.value = await perform("读取 Emergency Read-Only", emergencyReadonly);
}

async function runVectorSearch(): Promise<void> {
  await perform("只读向量搜索", () =>
    vectorSearch({
      query: query.value || vectorQuery.value,
      result_limit: resultLimit.value,
    }),
  );
}

async function runVectorBackendProbe(
  options: {silent?: boolean} = {},
): Promise<ApiRecord | null> {
  vectorBackendState.value = await perform("评估向量后端", vectorBackends, {
    silent: options.silent,
    collapseOutput: true,
  });
  return vectorBackendState.value;
}

async function sendChat(): Promise<void> {
  const content = chatInput.value.trim();
  if (!content || !selectedModel.value) {
    return;
  }
  const userMessage: ChatMessage = {role: "user", content};
  chatMessages.value.push(userMessage);
  chatInput.value = "";
  const controller = new AbortController();
  activeController.value = controller;
  notice.value = "模型回复中...";
  try {
    const answer = await sendChatMessage(selectedModel.value, chatMessages.value, controller.signal);
    const contentAnswer =
      typeof answer.answer === "string" ? answer.answer : JSON.stringify(answer, null, 2);
    chatMessages.value.push({role: "assistant", content: contentAnswer});
    runState.value = answer;
    notice.value = "模型回复完成";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    runState.value = {error: message, action: "模型回复"};
    notice.value = controller.signal.aborted ? "已暂停当前回复" : "模型回复失败";
  } finally {
    activeController.value = null;
  }
}

function pauseChat(): void {
  activeController.value?.abort();
  activeController.value = null;
  notice.value = "已请求暂停";
}

function loadModels(): ModelConfig[] {
  const raw = localStorage.getItem("rhine-vault-ui-models");
  if (!raw) {
    return defaultModels();
  }
  try {
    const parsed = JSON.parse(raw) as ModelConfig[];
    return parsed.length > 0 ? parsed : defaultModels();
  } catch {
    return defaultModels();
  }
}

function persistModels(): void {
  localStorage.setItem("rhine-vault-ui-models", JSON.stringify(models.value));
  runState.value = {
    settings: "saved",
    active_model: selectedModel.value?.displayName,
    model_count: models.value.length,
  };
  notice.value = "模型配置已保存";
}

function addDeepSeekModel(): void {
  const id = `deepseek-${Date.now()}`;
  models.value.push({
    id,
    displayName: "DeepSeek 自定义模型",
    provider: "openai-compatible",
    providerKind: "deepseek",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
  });
  selectedModelId.value = id;
}

async function refreshMcpCapabilities(): Promise<void> {
  mcpState.value = await mcpCapabilities();
  runState.value = mcpState.value as unknown as Record<string, unknown>;
}

async function runMcpTool(): Promise<void> {
  if (!selectedMcpTool.value) {
    return;
  }
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(mcpArgumentsText.value) as Record<string, unknown>;
  } catch (error) {
    runState.value = {error: error instanceof Error ? error.message : String(error)};
    return;
  }
  runState.value = await callMcpTool(selectedMcpTool.value, parsed);
}

async function runMcpResourceRead(): Promise<void> {
  runState.value = await readMcpResource(mcpResourceUri.value);
}

async function runProcessIndexJobs(): Promise<void> {
  runState.value = await processIndexJobs(indexWorkspaceId.value);
}

async function runRebuildIndexJobs(): Promise<void> {
  runState.value = {rebuild_jobs: await rebuildIndexJobs(indexWorkspaceId.value)};
}

async function runListIndexChunks(): Promise<void> {
  runState.value = {chunks: await listIndexChunks(indexWorkspaceId.value)};
}

async function runPublishLibrarySnapshot(): Promise<void> {
  const snapshot = await publishLibrarySnapshot({
    workspace_id: libraryWorkspaceId.value,
    version: libraryVersion.value,
    git_tag: libraryGitTag.value,
    commit_hash: libraryCommitHash.value,
  });
  runState.value = snapshot as unknown as Record<string, unknown>;
  await runListLibrarySnapshots();
}

async function runListLibrarySnapshots(): Promise<void> {
  snapshots.value = await listLibrarySnapshots(libraryWorkspaceId.value);
  runState.value = {snapshots: snapshots.value as unknown as Record<string, unknown>[]};
}

async function runLockWorkspaceDependency(): Promise<void> {
  const dependency = await lockWorkspaceDependency({
    project_workspace_id: projectWorkspaceId.value,
    alias: dependencyAlias.value,
    library_workspace_id: libraryWorkspaceId.value,
    version: libraryVersion.value,
    version_requirement: versionRequirement.value,
  });
  runState.value = dependency as unknown as Record<string, unknown>;
  await runListWorkspaceDependencies();
}

async function runListWorkspaceDependencies(): Promise<void> {
  dependencies.value = await listWorkspaceDependencies(projectWorkspaceId.value);
  runState.value = {dependencies: dependencies.value as unknown as Record<string, unknown>[]};
}

async function runDependencyUpgradeReport(): Promise<void> {
  runState.value = await dependencyUpgradeReport(projectWorkspaceId.value, dependencyAlias.value);
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">RV</div>
        <strong>Rhine-Vault</strong>
        <small>Phase 6 · Vector & Recovery</small>
      </div>
      <nav class="sidebar-nav">
        <el-button
          v-for="tab in tabs"
          :key="tab.id"
          class="nav-item"
          :class="{ active: activity === tab.id }"
          text
          @click="openActivity(tab.id)"
        >
          <span class="nav-icon-dot">
            <GameIcon :name="tab.icon" :label="tab.label" :size="17" />
          </span>
          <span class="nav-label">
            <strong>{{ tab.label }}</strong>
            <small>{{ tab.description }}</small>
          </span>
        </el-button>
      </nav>
    </aside>

    <main class="workspace" :class="{ 'run-state-collapsed': runStateCollapsed }">
      <header class="workspace-topbar">
        <div class="workspace-title-group">
          <div>
            <strong>{{ activeTabMeta.label }}</strong>
            <small>{{ activeTabMeta.description }}</small>
          </div>
        </div>
        <div class="workspace-topbar-actions">
          <span class="notice-pill" :class="{ busy: Boolean(busyAction) }">{{ notice }}</span>
          <span class="connection-pill online">Core API</span>
          <span class="uptime-pill">Phase 6</span>
          <el-button
            class="topbar-icon-button"
            text
            :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="sidebarCollapsed = !sidebarCollapsed"
          >
            <GameIcon name="nodes" label="侧边栏" :size="16" />
          </el-button>
          <el-button
            class="topbar-icon-button active"
            text
            title="刷新 MCP 能力"
            :loading="busyAction === '加载 MCP 能力'"
            @click="refreshMcpCapabilities"
          >
            <GameIcon name="refresh" label="刷新" :size="16" />
          </el-button>
        </div>
      </header>

      <section class="main-panel">
        <section v-if="activity === 'capture'" class="work-panel">
          <h2>知识采集</h2>
          <div class="panel-grid">
            <el-card shadow="never">
              <template #header>手动候选知识</template>
              <el-form label-position="top">
                <el-row :gutter="12">
                  <el-col :span="10">
                    <el-form-item label="标题">
                      <el-input v-model="manualTitle" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="7">
                    <el-form-item label="节点类型">
                      <el-select v-model="manualNodeType">
                        <el-option label="Note" value="Note" />
                        <el-option label="Constraint" value="Constraint" />
                        <el-option label="ImportedDocumentSection" value="ImportedDocumentSection" />
                        <el-option label="ProjectOverview" value="ProjectOverview" />
                        <el-option label="ModuleMap" value="ModuleMap" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :span="7">
                    <el-form-item label="Authority">
                      <el-select v-model="manualAuthority">
                        <el-option label="approved" value="approved" />
                        <el-option label="canonical" value="canonical" />
                        <el-option label="reference" value="reference" />
                        <el-option label="experimental" value="experimental" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="标签">
                  <el-input v-model="manualTags" placeholder="逗号分隔" />
                </el-form-item>
                <el-form-item label="内容">
                  <el-input v-model="manualContent" type="textarea" :rows="8" />
                </el-form-item>
                <el-space wrap>
                  <el-button
                    type="primary"
                    :loading="busyAction === '创建手动 Proposal'"
                    @click="submitManualProposal"
                  >
                    保存并进入审核
                  </el-button>
                  <el-button
                    :loading="busyAction === '保存为 staging'"
                    @click="submitAndStageManualProposal"
                  >
                    保存并进入 staging
                  </el-button>
                </el-space>
              </el-form>
            </el-card>

            <el-card shadow="never">
              <template #header>导入入口</template>
              <el-form label-position="top">
                <el-form-item label="Markdown / TXT 文件路径">
                  <el-input v-model="documentPath" placeholder="E:\\Project\\docs\\note.md" />
                </el-form-item>
                <el-button :loading="busyAction === '导入文档'" @click="runDocumentImport">导入文档</el-button>
                <el-divider />
                <el-form-item label="项目目录">
                  <el-input v-model="projectRoot" placeholder="E:\\Project\\SomeProject" />
                </el-form-item>
                <el-button :loading="busyAction === '扫描项目'" @click="runProjectScan">扫描项目</el-button>
              </el-form>
            </el-card>
          </div>
        </section>

        <section v-if="activity === 'retrieve'" class="work-panel">
          <h2>Retrieval Lab</h2>
          <el-form label-position="top">
            <el-form-item label="查询">
              <el-input v-model="query" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="Retrieval Profile">
                  <el-select v-model="selectedProfileId">
                    <el-option
                      v-for="profile in profiles"
                      :key="profile.profile_id"
                      :label="profile.name"
                      :value="profile.profile_id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-form-item label="结果数">
                  <el-input-number v-model="resultLimit" :min="1" :max="30" />
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-form-item label="关系深度">
                  <el-input-number v-model="relationDepth" :min="0" :max="1" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="标签过滤">
                  <el-input v-model="tags" placeholder="逗号分隔" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="节点类型">
                  <el-select v-model="nodeType" clearable>
                    <el-option label="Constraint" value="Constraint" />
                    <el-option label="Note" value="Note" />
                    <el-option label="ImportedDocumentSection" value="ImportedDocumentSection" />
                    <el-option label="ProjectOverview" value="ProjectOverview" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="Authority">
                  <el-select v-model="authority" clearable>
                    <el-option label="canonical" value="canonical" />
                    <el-option label="approved" value="approved" />
                    <el-option label="reference" value="reference" />
                    <el-option label="historical" value="historical" />
                    <el-option label="experimental" value="experimental" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="状态">
                  <el-checkbox v-model="includeDeprecated">包含 deprecated</el-checkbox>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="向量召回">
              <el-switch v-model="enableVector" active-text="启用本地确定性向量通道" />
            </el-form-item>
            <el-space>
              <el-button type="primary" :loading="running" @click="runRetrievalLab">运行 Retrieval Lab</el-button>
              <el-button :loading="running" @click="runContextBundle">构建 Context Bundle</el-button>
              <el-button :loading="running" @click="runVectorSearch">只读向量搜索</el-button>
              <el-button :loading="busyAction === '评估向量后端'" @click="runVectorBackendProbe()">
                评估向量后端
              </el-button>
            </el-space>
          </el-form>
          <el-card v-if="vectorBackendState" shadow="never">
            <template #header>向量后端评估</template>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="Active">
                {{ vectorBackendState.active_backend }}
              </el-descriptions-item>
              <el-descriptions-item label="Default">
                {{ vectorBackendState.default_backend }}
              </el-descriptions-item>
              <el-descriptions-item label="Phase">
                {{ vectorBackendState.phase }}
              </el-descriptions-item>
            </el-descriptions>
            <el-table :data="vectorBackendState.backends ?? []" border class="phase5-table">
              <el-table-column prop="display_name" label="后端" min-width="260" />
              <el-table-column prop="status" label="状态" min-width="170" />
              <el-table-column label="Installed" width="110">
                <template #default="{ row }">{{ row.installed ? "yes" : "no" }}</template>
              </el-table-column>
              <el-table-column label="Enabled" width="110">
                <template #default="{ row }">{{ row.enabled ? "yes" : "no" }}</template>
              </el-table-column>
              <el-table-column label="Formal Authority" width="150">
                <template #default="{ row }">{{ row.formal_authority ? "yes" : "no" }}</template>
              </el-table-column>
            </el-table>
            <el-space wrap class="phase5-table">
              <el-tag
                v-for="constraint in vectorBackendState.constraints ?? []"
                :key="constraint"
                type="info"
              >
                {{ constraint }}
              </el-tag>
            </el-space>
          </el-card>
        </section>

        <section v-if="activity === 'chat'" class="work-panel chat-panel">
          <h2>对话</h2>
          <el-scrollbar class="chat-log">
            <div v-for="(message, index) in chatMessages" :key="index" :class="['chat-bubble', message.role]">
              <div class="chat-role">{{ message.role }}</div>
              <div>{{ message.content }}</div>
            </div>
          </el-scrollbar>
          <el-space direction="vertical" fill class="composer">
            <el-input v-model="chatInput" type="textarea" :rows="4" placeholder="输入消息" />
            <el-row :gutter="12">
              <el-col :span="12">
                <el-select v-model="selectedModelId">
                  <el-option
                    v-for="model in models"
                    :key="model.id"
                    :label="model.displayName"
                    :value="model.id"
                  />
                </el-select>
              </el-col>
              <el-col :span="12">
                <el-space>
                  <el-button type="primary" :loading="activeController !== null" @click="sendChat">发送</el-button>
                  <el-button @click="pauseChat">暂停当前</el-button>
                  <el-button :disabled="chatMessages.length === 0" @click="captureChatAsProposal">
                    采集当前对话
                  </el-button>
                </el-space>
              </el-col>
            </el-row>
          </el-space>
        </section>

        <section v-if="activity === 'settings'" class="work-panel">
          <h2>模型设置</h2>
          <el-space direction="vertical" fill>
            <el-button @click="addDeepSeekModel">添加 DeepSeek 模型</el-button>
            <el-table :data="models" border>
              <el-table-column label="显示名称" min-width="180">
                <template #default="{ row }">
                  <el-input v-model="row.displayName" />
                </template>
              </el-table-column>
              <el-table-column label="API 地址" min-width="220">
                <template #default="{ row }">
                  <el-input v-model="row.baseUrl" />
                </template>
              </el-table-column>
              <el-table-column label="模型" min-width="180">
                <template #default="{ row }">
                  <el-input v-model="row.model" />
                </template>
              </el-table-column>
              <el-table-column label="API Key" min-width="220">
                <template #default="{ row }">
                  <el-input v-model="row.apiKey" type="password" show-password />
                </template>
              </el-table-column>
            </el-table>
            <el-button type="primary" @click="persistModels">保存本地模型配置</el-button>
          </el-space>
        </section>

        <section v-if="activity === 'mcp'" class="work-panel">
          <h2>MCP 能力边界</h2>
          <el-space direction="vertical" fill class="mcp-panel">
            <el-alert
              :title="mcpState?.approval_policy ?? 'MCP capabilities are loading.'"
              type="info"
              :closable="false"
            />
            <el-descriptions :column="3" border>
              <el-descriptions-item label="阶段">
                {{ mcpState?.phase ?? "-" }}
              </el-descriptions-item>
              <el-descriptions-item label="Bridge">
                {{ mcpState?.transport_neutral ? "transport-neutral" : "-" }}
              </el-descriptions-item>
              <el-descriptions-item label="Streamable HTTP">
                {{ mcpState?.streamable_http.enabled ? "enabled" : "disabled" }}
              </el-descriptions-item>
              <el-descriptions-item label="Mount">
                {{ mcpState?.streamable_http.mount_path ?? "/mcp" }}
              </el-descriptions-item>
              <el-descriptions-item label="Error" :span="2">
                {{ mcpState?.streamable_http.error ?? "-" }}
              </el-descriptions-item>
            </el-descriptions>
            <el-table :data="mcpState?.tools ?? []" border>
              <el-table-column prop="name" label="工具" min-width="180" />
              <el-table-column prop="write_scope" label="写入范围" min-width="140" />
              <el-table-column prop="description" label="说明" min-width="320" />
            </el-table>
            <div>
              <h3>禁止工具</h3>
              <el-space wrap>
                <el-tag v-for="tool in mcpState?.forbidden_tools ?? []" :key="tool" type="danger">
                  {{ tool }}
                </el-tag>
              </el-space>
            </div>
            <div>
              <h3>资源模板</h3>
              <el-space wrap>
                <el-tag v-for="resource in mcpState?.resources ?? []" :key="resource" type="success">
                  {{ resource }}
                </el-tag>
              </el-space>
            </div>
            <el-form label-position="top">
              <el-row :gutter="12">
                <el-col :span="8">
                  <el-form-item label="调用工具">
                    <el-select v-model="selectedMcpTool">
                      <el-option
                        v-for="tool in mcpState?.tools ?? []"
                        :key="tool.name"
                        :label="tool.name"
                        :value="tool.name"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="16">
                  <el-form-item label="JSON 参数">
                    <el-input v-model="mcpArgumentsText" type="textarea" :rows="3" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-space>
                <el-button type="primary" @click="runMcpTool">调用白名单工具</el-button>
                <el-button @click="refreshMcpCapabilities">刷新能力</el-button>
              </el-space>
            </el-form>
            <el-form label-position="top">
              <el-form-item label="Resource URI">
                <el-input v-model="mcpResourceUri" />
              </el-form-item>
              <el-button @click="runMcpResourceRead">读取 Resource</el-button>
            </el-form>
          </el-space>
        </section>

        <section v-if="activity === 'library'" class="work-panel">
          <h2>索引与 Library</h2>
          <el-space direction="vertical" fill class="phase5-panel">
            <el-card shadow="never">
              <template #header>派生索引</template>
              <el-form label-position="top">
                <el-form-item label="Workspace ID">
                  <el-input v-model="indexWorkspaceId" />
                </el-form-item>
                <el-space>
                  <el-button type="primary" @click="runProcessIndexJobs">执行 IndexJob</el-button>
                  <el-button @click="runRebuildIndexJobs">重建派生索引</el-button>
                  <el-button @click="runListIndexChunks">加载 Chunks</el-button>
                </el-space>
              </el-form>
            </el-card>

            <el-card shadow="never">
              <template #header>Library Snapshot</template>
              <el-form label-position="top">
                <el-row :gutter="12">
                  <el-col :span="8">
                    <el-form-item label="Library Workspace ID">
                      <el-input v-model="libraryWorkspaceId" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="4">
                    <el-form-item label="版本">
                      <el-input v-model="libraryVersion" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="4">
                    <el-form-item label="Git Tag">
                      <el-input v-model="libraryGitTag" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="8">
                    <el-form-item label="Commit">
                      <el-input v-model="libraryCommitHash" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-space>
                  <el-button type="primary" @click="runPublishLibrarySnapshot">发布 Snapshot</el-button>
                  <el-button @click="runListLibrarySnapshots">列出 Snapshots</el-button>
                </el-space>
              </el-form>
              <el-table v-if="snapshots.length" :data="snapshots" border class="phase5-table">
                <el-table-column prop="version" label="版本" width="110" />
                <el-table-column prop="manifest_hash" label="Manifest Hash" min-width="260" />
                <el-table-column prop="created_at" label="发布时间" min-width="180" />
              </el-table>
            </el-card>

            <el-card shadow="never">
              <template #header>依赖锁定与升级报告</template>
              <el-form label-position="top">
                <el-row :gutter="12">
                  <el-col :span="8">
                    <el-form-item label="Project Workspace ID">
                      <el-input v-model="projectWorkspaceId" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="5">
                    <el-form-item label="依赖别名">
                      <el-input v-model="dependencyAlias" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="5">
                    <el-form-item label="锁定版本">
                      <el-input v-model="libraryVersion" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="6">
                    <el-form-item label="版本要求">
                      <el-input v-model="versionRequirement" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-space>
                  <el-button type="primary" @click="runLockWorkspaceDependency">锁定依赖</el-button>
                  <el-button @click="runListWorkspaceDependencies">列出依赖</el-button>
                  <el-button @click="runDependencyUpgradeReport">生成升级报告</el-button>
                </el-space>
              </el-form>
              <el-table v-if="dependencies.length" :data="dependencies" border class="phase5-table">
                <el-table-column prop="alias" label="别名" width="120" />
                <el-table-column prop="library_workspace_id" label="Library" min-width="220" />
                <el-table-column prop="resolved_version" label="版本" width="100" />
                <el-table-column prop="manifest_hash" label="Manifest Hash" min-width="260" />
              </el-table>
            </el-card>
          </el-space>
        </section>

        <section v-if="activity === 'nodes'" class="work-panel">
          <h2>节点目录</h2>
          <el-space wrap>
            <el-button type="primary" @click="refreshNodes">刷新节点</el-button>
            <el-button :disabled="!selectedNodeId" @click="refreshNodeRevisions">加载 revision</el-button>
          </el-space>
          <div class="node-layout">
            <el-table :data="nodes" border height="420" highlight-current-row @current-change="selectNode">
              <el-table-column prop="title" label="标题" min-width="220" />
              <el-table-column prop="node_type" label="类型" width="160" />
              <el-table-column prop="authority" label="Authority" width="130" />
              <el-table-column prop="revision" label="Rev" width="80" />
              <el-table-column prop="status" label="状态" width="110" />
            </el-table>
            <el-card shadow="never" class="detail-card">
              <template #header>节点详情</template>
              <template v-if="selectedNode">
                <h3>{{ selectedNode.title }}</h3>
                <p class="muted mono">{{ selectedNode.node_id }}</p>
                <p>{{ selectedNode.content }}</p>
                <el-space wrap>
                  <el-tag v-for="tag in selectedNode.tags ?? []" :key="tag">{{ tag }}</el-tag>
                </el-space>
                <el-divider />
                <el-form label-position="top">
                  <el-form-item label="回滚到 revision">
                    <el-input-number v-model="rollbackRevision" :min="1" />
                  </el-form-item>
                  <el-button type="warning" @click="runRollbackNode">生成回滚 revision</el-button>
                </el-form>
                <el-table :data="nodeRevisions" border class="phase5-table">
                  <el-table-column prop="revision" label="Rev" width="80" />
                  <el-table-column prop="change_id" label="ChangeSet" min-width="220" />
                  <el-table-column prop="created_at" label="时间" min-width="170" />
                </el-table>
              </template>
              <el-empty v-else description="暂无节点" />
            </el-card>
          </div>
        </section>

        <section v-if="activity === 'review'" class="work-panel">
          <h2>审核与工作流</h2>
          <el-tabs>
            <el-tab-pane label="Proposal">
              <el-space wrap>
                <el-button type="primary" @click="refreshProposals">加载 Proposal</el-button>
                <el-button @click="runStageProposal">保存为 staging</el-button>
                <el-button type="danger" @click="runRejectProposal">驳回 Proposal</el-button>
              </el-space>
              <el-row :gutter="12" class="review-grid">
                <el-col :span="10">
                  <el-table :data="proposals" border height="420" highlight-current-row @current-change="selectProposal">
                    <el-table-column prop="proposal_id" label="Proposal ID" min-width="220" />
                    <el-table-column prop="status" label="状态" width="120" />
                    <el-table-column prop="created_at" label="时间" min-width="160" />
                  </el-table>
                </el-col>
                <el-col :span="14">
                  <el-card shadow="never">
                    <template #header>候选节点</template>
                    <el-checkbox-group v-model="selectedTemporaryIds">
                      <div v-for="node in selectedProposal?.proposed_nodes ?? []" :key="node.temporary_id" class="candidate-row">
                        <el-checkbox :label="String(node.temporary_id)">
                          {{ node.title }} · {{ node.node_type }}
                        </el-checkbox>
                        <p>{{ node.content }}</p>
                      </div>
                    </el-checkbox-group>
                  </el-card>
                </el-col>
              </el-row>
            </el-tab-pane>

            <el-tab-pane label="Staging">
              <el-space wrap>
                <el-button type="primary" @click="refreshStaging">加载 Staging</el-button>
                <el-button type="success" @click="runApproveStaging">批准所选 staging</el-button>
              </el-space>
              <el-checkbox-group v-model="selectedStagingIds" class="staging-list">
                <article v-for="entry in stagingEntries" :key="entry.entry_id" class="staging-card">
                  <el-checkbox :label="String(entry.entry_id)">
                    {{ entry.candidate?.title ?? entry.entry_id }}
                  </el-checkbox>
                  <small class="mono">{{ entry.entry_id }}</small>
                  <p>{{ entry.candidate?.content }}</p>
                </article>
              </el-checkbox-group>
            </el-tab-pane>

            <el-tab-pane label="ExternalChange">
              <el-space wrap>
                <el-button type="primary" @click="runDetectExternalChanges">检测外部变更</el-button>
                <el-button @click="refreshWorkflowState">刷新工作流</el-button>
                <el-button type="success" @click="runApproveExternalChange">批准外部变更</el-button>
                <el-button type="danger" @click="runRejectExternalChange">驳回外部变更</el-button>
              </el-space>
              <el-table :data="externalChanges" border height="360" highlight-current-row @current-change="selectExternalChange">
                <el-table-column prop="change_id" label="Change ID" min-width="240" />
                <el-table-column prop="node_id" label="Node" min-width="180" />
                <el-table-column prop="status" label="状态" width="120" />
                <el-table-column prop="detected_at" label="检测时间" min-width="170" />
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="Audit">
              <el-button type="primary" @click="refreshWorkflowState">刷新 ChangeSet / Audit</el-button>
              <el-table :data="changesets" border class="phase5-table">
                <el-table-column prop="change_id" label="ChangeSet" min-width="240" />
                <el-table-column prop="status" label="状态" width="120" />
                <el-table-column prop="created_at" label="时间" min-width="170" />
              </el-table>
              <el-table :data="auditEvents" border class="phase5-table">
                <el-table-column prop="action" label="Action" min-width="180" />
                <el-table-column prop="actor_id" label="Actor" min-width="140" />
                <el-table-column prop="created_at" label="时间" min-width="170" />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </section>

        <section v-if="activity === 'recovery'" class="work-panel">
          <h2>恢复与迁移</h2>
          <div class="panel-grid">
            <el-card shadow="never">
              <template #header>Workspace Snapshot</template>
              <p class="muted">创建 `.rhine` snapshot package，不覆盖当前 vault。</p>
              <el-button type="primary" @click="runCreateWorkspaceSnapshot">创建 Snapshot</el-button>
            </el-card>
            <el-card shadow="never">
              <template #header>Import Plan</template>
              <el-form label-position="top">
                <el-form-item label=".rhine package path">
                  <el-input v-model="importPackagePath" />
                </el-form-item>
                <el-button @click="runBuildImportPlan">只读验证 Import Plan</el-button>
              </el-form>
            </el-card>
            <el-card shadow="never">
              <template #header>Emergency Read-Only</template>
              <p class="muted">直接读取 Markdown 节点，不修复、不写入。</p>
              <el-button @click="runEmergencyReadonly">读取只读节点</el-button>
            </el-card>
          </div>
          <el-card v-if="recoveryState" shadow="never">
            <template #header>恢复状态</template>
            <pre>{{ JSON.stringify(recoveryState, null, 2) }}</pre>
          </el-card>
        </section>
      </section>

      <section class="run-state">
        <header class="run-state-header">
          <strong>运行状态</strong>
          <el-space>
            <el-button text size="small" @click="runStateCollapsed = !runStateCollapsed">
              {{ runStateCollapsed ? "展开" : "折叠" }}
            </el-button>
            <el-button text size="small" @click="runState = null">清空</el-button>
          </el-space>
        </header>
        <pre v-if="!runStateCollapsed">{{ JSON.stringify(runState, null, 2) }}</pre>
      </section>
    </main>
  </div>
</template>


