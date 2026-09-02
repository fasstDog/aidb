<script setup>
import { computed, onMounted, ref } from "vue";
import { useDialog, useMessage } from "naive-ui";
import { ArrowBackOutline, PulseOutline } from "@vicons/ionicons5";
import { api } from "../api";
import {
  state,
  setDark,
  loadEngines,
  loadGallery,
  refreshConnections,
  goHome,
  openCreateDrawer,
  openEditDrawer,
  pingConnection,
  pingOf,
  engineLabel,
  connectionSummary,
} from "../store";
import ConnectionGrid from "./ConnectionGrid.vue";
import ConnectionDrawer from "./ConnectionDrawer.vue";
import CatalogPane from "./CatalogPane.vue";
import EditorPane from "./EditorPane.vue";
import BundleModal from "./BundleModal.vue";
import EngineIcon from "./EngineIcon.vue";

const message = useMessage();
const dialog = useDialog();
const bundleShow = ref(false);
const bootError = ref("");
const pinging = ref(false);

const selected = computed(() =>
  state.connections.find((c) => c.id === state.selectedId) || null
);

onMounted(async () => {
  try {
    await loadEngines();
    await loadGallery();
    await refreshConnections();
  } catch (err) {
    bootError.value = err.message || String(err);
  }
});

function pingText(id) {
  const s = pingOf(id);
  if (s === "ok") return "通";
  if (s === "fail") return "失败";
  return "未测";
}

async function onPing() {
  if (!state.selectedId) return;
  pinging.value = true;
  try {
    await pingConnection(state.selectedId);
    message.success("连通正常");
  } catch (err) {
    message.error(err.message || "连通失败");
  } finally {
    pinging.value = false;
  }
}

function onDelete() {
  const conn = selected.value;
  if (!conn) return;
  dialog.warning({
    title: "删除连接",
    content: "删除「" + (conn.name || conn.id) + "」？",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await api("/api/connections/" + encodeURIComponent(conn.id), { method: "DELETE" });
        goHome();
        await refreshConnections();
        message.success("已删除");
      } catch (err) {
        message.error(err.message || "删除失败");
      }
    },
  });
}
</script>

<template>
  <n-layout style="height: 100vh">
    <n-layout-header bordered>
      <div class="app-header">
        <div>
          <h1>AIDB 配置台<span class="sub">连接 · 目录补丁 · 导入导出</span></h1>
        </div>
        <n-space align="center">
          <n-button v-if="state.view === 'home'" type="primary" size="small" @click="openCreateDrawer">
            新增数据源
          </n-button>
          <n-button size="small" @click="bundleShow = true">导入 / 导出</n-button>
          <n-text depth="3" style="font-size: 12px">深色</n-text>
          <n-switch :value="state.dark" @update:value="setDark" size="small" />
        </n-space>
      </div>
    </n-layout-header>
    <n-alert v-if="bootError" type="error" style="margin: 8px 12px">{{ bootError }}</n-alert>
    <n-layout-content
      v-if="state.view === 'home'"
      :native-scrollbar="false"
      content-style="padding: 24px; height: calc(100vh - 52px); overflow: auto;"
    >
      <ConnectionGrid />
    </n-layout-content>
    <n-layout v-else has-sider style="height: calc(100vh - 52px)">
      <n-layout-content :native-scrollbar="false" content-style="height: 100%; display: flex; flex-direction: column;">
        <div class="detail-bar">
          <n-button size="small" quaternary @click="goHome">
            <template #icon><n-icon :component="ArrowBackOutline" /></template>
            返回
          </n-button>
          <EngineIcon
            v-if="selected"
            :family="selected.family"
            :engine="selected.engine"
            :size="18"
          />
          <div class="detail-meta">
            <div class="detail-name">{{ selected ? (selected.name || selected.id) : "" }}</div>
            <div class="muted">
              {{ selected ? engineLabel(selected.engine) : "" }}
              <span v-if="selected && connectionSummary(selected.config)">
                · {{ connectionSummary(selected.config) }}
              </span>
            </div>
          </div>
          <n-space style="margin-left: auto" align="center">
            <n-badge :type="pingOf(state.selectedId) === 'ok' ? 'success' : pingOf(state.selectedId) === 'fail' ? 'error' : 'warning'" dot />
            <span class="muted">{{ pingText(state.selectedId) }}</span>
            <n-button size="small" :loading="pinging" @click="onPing">
              <template #icon><n-icon :component="PulseOutline" /></template>
              测通
            </n-button>
            <n-button size="small" @click="openEditDrawer(selected)">编辑</n-button>
            <n-button size="small" tertiary type="error" @click="onDelete">删除</n-button>
          </n-space>
        </div>
        <n-layout has-sider style="flex: 1; min-height: 0">
          <n-layout-sider
            :width="320"
            :native-scrollbar="false"
            bordered
            content-style="padding: 16px; height: 100%; overflow: auto;"
          >
            <CatalogPane />
          </n-layout-sider>
          <n-layout-content
            :native-scrollbar="false"
            content-style="padding: 16px 24px; height: 100%; overflow: auto;"
          >
            <EditorPane />
          </n-layout-content>
        </n-layout>
      </n-layout-content>
    </n-layout>
    <ConnectionDrawer />
    <BundleModal v-model:show="bundleShow" />
  </n-layout>
</template>
