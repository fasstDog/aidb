<script setup>
import { computed } from "vue";
import { useDialog, useMessage } from "naive-ui";
import { schemaFields, isSecretField } from "../api";
import {
  state,
  engineById,
  rebuildForm,
  readEngineConfig,
  fillConnectionForm,
  refreshConnections,
  selectConnection,
} from "../store";
import { api } from "../api";

const message = useMessage();
const dialog = useDialog();

const engineOptions = computed(() =>
  state.engines.map((e) => ({
    label: e.id + (e.family ? " · " + e.family : ""),
    value: e.id,
  }))
);

const currentEngine = computed(() => engineById(state.connForm.engine));
const fields = computed(() => schemaFields(currentEngine.value));

function onEngineChange(id) {
  rebuildForm(id);
}

async function onSave() {
  try {
    const payload = {
      name: (state.connForm.name || "").trim(),
      engine: state.connForm.engine,
      config: readEngineConfig(),
    };
    if (!payload.name) {
      message.error("请填写名称");
      return;
    }
    if (!payload.engine) {
      message.error("请选择引擎");
      return;
    }
    const id = state.connForm.id;
    let saved;
    if (id) {
      saved = await api("/api/connections/" + encodeURIComponent(id), {
        method: "PUT",
        body: payload,
      });
    } else {
      saved = await api("/api/connections", { method: "POST", body: payload });
    }
    message.success("已保存");
    await refreshConnections();
    await selectConnection(saved.id);
  } catch (err) {
    message.error(err.message || "保存失败");
  }
}

async function onPing() {
  const id = state.connForm.id || state.selectedId;
  if (!id) {
    message.warning("请先保存连接");
    return;
  }
  try {
    await api("/api/connections/" + encodeURIComponent(id) + "/ping", { method: "POST" });
    message.success("连通正常");
  } catch (err) {
    message.error(err.message || "连通失败");
  }
}

function onNew() {
  state.selectedId = null;
  fillConnectionForm(null);
  state.treeRoot = null;
  state.treeMsg = "请选择数据源";
  state.versions = [];
}

function onDelete() {
  const id = state.connForm.id || state.selectedId;
  if (!id) return;
  dialog.warning({
    title: "删除连接",
    content: "删除该连接？",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await api("/api/connections/" + encodeURIComponent(id), { method: "DELETE" });
        state.selectedId = null;
        await refreshConnections();
        fillConnectionForm(null);
        state.treeRoot = null;
        message.success("已删除");
      } catch (err) {
        message.error(err.message || "删除失败");
      }
    },
  });
}

function fieldRequired(field) {
  return !!field.required && !isSecretField(field);
}
</script>

<template>
  <h2 class="pane-title">数据源</h2>
  <div style="margin-bottom: 12px">
    <div
      v-for="conn in state.connections"
      :key="conn.id"
      class="conn-item"
      :class="{ active: conn.id === state.selectedId }"
      @click="selectConnection(conn.id)"
    >
      <span>{{ conn.name || conn.id }}</span>
      <span class="meta">{{ conn.engine }}</span>
    </div>
    <n-empty v-if="!state.connections.length" description="暂无数据源" size="small" />
  </div>
  <n-form label-placement="top" size="small">
    <n-form-item label="引擎">
      <n-select
        :value="state.connForm.engine"
        :options="engineOptions"
        :placeholder="'选择引擎'"
        @update:value="onEngineChange"
      />
    </n-form-item>
    <n-form-item label="名称" required>
      <n-input v-model:value="state.connForm.name" placeholder="订单库" />
    </n-form-item>
    <n-form-item
      v-for="field in fields"
      :key="field.key"
      :label="field.label || field.key"
      :required="fieldRequired(field)"
    >
      <n-input-number
        v-if="field.type === 'int'"
        v-model:value="state.connForm.config[field.key]"
        style="width: 100%"
      />
      <n-input
        v-else-if="field.type === 'text'"
        v-model:value="state.connForm.config[field.key]"
        type="textarea"
        :rows="3"
      />
      <n-input
        v-else-if="isSecretField(field)"
        v-model:value="state.connForm.config[field.key]"
        type="password"
        show-password-on="click"
        placeholder="留空则保持不变"
        autocomplete="new-password"
      />
      <n-input v-else v-model:value="state.connForm.config[field.key]" />
    </n-form-item>
    <div class="form-actions">
      <n-button type="primary" size="small" @click="onSave">保存</n-button>
      <n-button size="small" @click="onPing">测连通</n-button>
      <n-button size="small" secondary @click="onNew">新建</n-button>
      <n-button size="small" secondary @click="onDelete">删除</n-button>
    </div>
  </n-form>
</template>
