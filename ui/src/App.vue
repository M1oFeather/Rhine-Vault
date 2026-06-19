<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  type ChatMessage,
  type McpCapabilities,
  type ModelConfig,
  type RetrievalProfile,
  buildContextBundle,
  callMcpTool,
  defaultModels,
  mcpCapabilities,
  readMcpResource,
  retrievalLab,
  retrievalProfiles,
  sendChatMessage,
} from "./api";
import GameIcon from "./components/GameIcon.vue";

type Activity = "retrieve" | "chat" | "nodes" | "review" | "mcp" | "settings";

const activity = ref<Activity>("retrieve");
const profiles = ref<RetrievalProfile[]>([]);
const selectedProfileId = ref("technical-documentation");
const query = ref("approval constraints");
const resultLimit = ref(8);
const relationDepth = ref(1);
const nodeType = ref("");
const authority = ref("");
const tags = ref("");
const includeDeprecated = ref(false);
const runState = ref<Record<string, unknown> | null>(null);
const running = ref(false);

const models = ref<ModelConfig[]>(loadModels());
const selectedModelId = ref(models.value[0]?.id ?? "");
const chatInput = ref("");
const chatMessages = ref<ChatMessage[]>([]);
const activeController = ref<AbortController | null>(null);
const mcpState = ref<McpCapabilities | null>(null);
const selectedMcpTool = ref("search_nodes");
const mcpArgumentsText = ref('{"workspace_id":"demo-workspace","query":"approval"}');
const mcpResourceUri = ref("rhine://workspace/demo-workspace/schema/memory-node");

const selectedModel = computed(() => {
  return models.value.find((model) => model.id === selectedModelId.value) ?? models.value[0];
});

onMounted(async () => {
  const payload = await retrievalProfiles();
  profiles.value = payload.profiles;
  selectedProfileId.value = payload.default_profile_id;
  mcpState.value = await mcpCapabilities();
});

async function runRetrievalLab(): Promise<void> {
  running.value = true;
  try {
    runState.value = await retrievalLab({
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
    });
  } finally {
    running.value = false;
  }
}

async function runContextBundle(): Promise<void> {
  running.value = true;
  try {
    runState.value = await buildContextBundle({
      query: query.value,
      profile_id: selectedProfileId.value,
    });
  } finally {
    running.value = false;
  }
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
  try {
    const answer = await sendChatMessage(selectedModel.value, chatMessages.value, controller.signal);
    const contentAnswer =
      typeof answer.answer === "string" ? answer.answer : JSON.stringify(answer, null, 2);
    chatMessages.value.push({role: "assistant", content: contentAnswer});
    runState.value = answer;
  } finally {
    activeController.value = null;
  }
}

function pauseChat(): void {
  activeController.value?.abort();
  activeController.value = null;
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
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="64px" class="activity-bar">
      <el-tooltip content="检索" placement="right">
        <el-button :type="activity === 'retrieve' ? 'primary' : 'info'" circle @click="activity = 'retrieve'">
          <GameIcon name="search" label="检索" />
        </el-button>
      </el-tooltip>
      <el-tooltip content="对话" placement="right">
        <el-button :type="activity === 'chat' ? 'primary' : 'info'" circle @click="activity = 'chat'">
          <GameIcon name="chat" label="对话" />
        </el-button>
      </el-tooltip>
      <el-tooltip content="节点" placement="right">
        <el-button :type="activity === 'nodes' ? 'primary' : 'info'" circle @click="activity = 'nodes'">
          <GameIcon name="nodes" label="节点" />
        </el-button>
      </el-tooltip>
      <el-tooltip content="审核" placement="right">
        <el-button :type="activity === 'review' ? 'primary' : 'info'" circle @click="activity = 'review'">
          <GameIcon name="review" label="审核" />
        </el-button>
      </el-tooltip>
      <el-tooltip content="MCP" placement="right">
        <el-button :type="activity === 'mcp' ? 'primary' : 'info'" circle @click="activity = 'mcp'">
          <GameIcon name="link" label="MCP" />
        </el-button>
      </el-tooltip>
      <el-tooltip content="设置" placement="right">
        <el-button :type="activity === 'settings' ? 'primary' : 'info'" circle @click="activity = 'settings'">
          <GameIcon name="settings" label="设置" />
        </el-button>
      </el-tooltip>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <strong>Rhine-Vault Phase 4</strong>
        <span class="topbar-note">Core-only backend · Element UI client</span>
      </el-header>

      <el-main class="workspace">
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
            <el-space>
              <el-button type="primary" :loading="running" @click="runRetrievalLab">运行 Retrieval Lab</el-button>
              <el-button :loading="running" @click="runContextBundle">构建 Context Bundle</el-button>
            </el-space>
          </el-form>
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
                  <el-button type="primary" @click="sendChat">发送</el-button>
                  <el-button @click="pauseChat">暂停当前</el-button>
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

        <section v-if="activity === 'nodes'" class="work-panel">
          <h2>节点</h2>
          <el-empty description="节点目录将继续通过 REST API 接入 Element 表格/树。" />
        </section>

        <section v-if="activity === 'review'" class="work-panel">
          <h2>审核</h2>
          <el-empty description="Phase 2 审核流仍保留在后端 API，Element 页面将在后续替换原生 HTML 控件。" />
        </section>
      </el-main>

      <el-footer class="run-state">
        <strong>运行状态</strong>
        <pre>{{ JSON.stringify(runState, null, 2) }}</pre>
      </el-footer>
    </el-container>
  </el-container>
</template>


