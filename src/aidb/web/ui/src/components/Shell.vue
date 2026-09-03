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
  activateSourceOverlay,
  isSourceOverlayActive,
  engineIconPath,
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

const SPLIT_KEY = "aidb.catalogSplitPx";
const splitSize = ref(readSplitSize());

const selected = computed(() =>
  state.connections.find((c) => c.id === state.selectedId) || null
);

function readSplitSize() {
  try {
    const n = Number(localStorage.getItem(SPLIT_KEY));
    if (Number.isFinite(n) && n >= 220 && n <= 640) return `${Math.round(n)}px`;
  } catch {
    /* ignore */
  }
  return "320px";
}

function onSplitUpdate(v) {
  // NSplit: number = 0–1 比例；string（如 "320px"）= 固定像素
  splitSize.value = v;
  try {
    const px = typeof v === "string" ? Number.parseFloat(v) : Math.round(Number(v) * (window.innerWidth || 1));
    if (Number.isFinite(px) && px >= 220 && px <= 640) {
      localStorage.setItem(SPLIT_KEY, String(Math.round(px)));
    }
  } catch {
    /* ignore */
  }
}

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
  <div class="app-shell">
    <header class="app-header-bar">
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
    </header>
    <n-alert v-if="bootError" type="error" class="boot-alert">{{ bootError }}</n-alert>
    <main class="app-main">
      <n-scrollbar v-if="state.view === 'home'" class="home-scroll">
        <div style="padding: 24px">
          <ConnectionGrid />
        </div>
      </n-scrollbar>
      <div v-else class="detail-page">
        <div class="detail-bar">
          <n-button size="small" quaternary @click="goHome">
            <template #icon><n-icon :component="ArrowBackOutline" /></template>
            返回
          </n-button>
          <EngineIcon
            v-if="selected"
            :family="selected.family"
            :engine="selected.engine"
            :icon="engineIconPath(selected.engine)"
            :size="18"
          />
          <div
            class="detail-meta detail-meta-click"
            :class="{ active: isSourceOverlayActive() }"
            title="编辑数据源说明与查询规则"
            @click="activateSourceOverlay"
          >
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
        <div class="detail-split">
          <n-split
            direction="horizontal"
            :size="splitSize"
            default-size="320px"
            min="220px"
            max="640px"
            :resize-trigger-size="6"
            class="detail-split-inner"
            @update:size="onSplitUpdate"
          >
            <template #1>
              <div class="split-pane split-pane-left">
                <n-scrollbar class="split-scroll">
                  <div class="split-pane-inner">
                    <CatalogPane />
                  </div>
                </n-scrollbar>
              </div>
            </template>
            <template #2>
              <div class="split-pane split-pane-right">
                <n-scrollbar class="split-scroll">
                  <div class="split-pane-inner split-pane-inner-right">
                    <EditorPane />
                  </div>
                </n-scrollbar>
              </div>
            </template>
          </n-split>
        </div>
      </div>
    </main>
    <ConnectionDrawer />
    <BundleModal v-model:show="bundleShow" />
  </div>
</template>
