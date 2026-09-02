<script setup>
import { ref } from "vue";
import { useDialog, useMessage } from "naive-ui";
import { CreateOutline, TrashOutline, PulseOutline } from "@vicons/ionicons5";
import { api } from "../api";
import {
  state,
  connectionSummary,
  engineLabel,
  openDetail,
  openCreateDrawer,
  openEditDrawer,
  pingConnection,
  pingOf,
  refreshConnections,
  goHome,
} from "../store";
import EngineIcon from "./EngineIcon.vue";

const message = useMessage();
const dialog = useDialog();
const pinging = ref({});

function statusMeta(id) {
  const s = pingOf(id);
  if (s === "ok") return { type: "success", text: "通" };
  if (s === "fail") return { type: "error", text: "失败" };
  return { type: "warning", text: "未测" };
}

async function onPing(ev, conn) {
  ev.stopPropagation();
  pinging.value = { ...pinging.value, [conn.id]: true };
  try {
    await pingConnection(conn.id);
    message.success("连通正常");
  } catch (err) {
    message.error(err.message || "连通失败");
  } finally {
    pinging.value = { ...pinging.value, [conn.id]: false };
  }
}

function onEdit(ev, conn) {
  ev.stopPropagation();
  openEditDrawer(conn);
}

function onDelete(ev, conn) {
  ev.stopPropagation();
  dialog.warning({
    title: "删除连接",
    content: "删除「" + (conn.name || conn.id) + "」？",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await api("/api/connections/" + encodeURIComponent(conn.id), { method: "DELETE" });
        if (state.selectedId === conn.id) goHome();
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
  <div class="home-page">
    <div class="home-toolbar">
      <div>
        <h2 class="pane-title" style="margin: 0">数据源</h2>
        <p class="muted" style="margin: 4px 0 0">已保存的连接。点卡片进入目录与补丁。</p>
      </div>
      <n-button type="primary" @click="openCreateDrawer">新增数据源</n-button>
    </div>
    <n-empty v-if="!state.connections.length" description="暂无数据源">
      <template #extra>
        <n-button type="primary" size="small" @click="openCreateDrawer">新增数据源</n-button>
      </template>
    </n-empty>
    <div v-else class="conn-grid">
      <n-card
        v-for="conn in state.connections"
        :key="conn.id"
        hoverable
        class="conn-card"
        @click="openDetail(conn.id)"
      >
        <n-tag
          v-if="state.sourcePatched[conn.id]"
          class="conn-patched"
          size="small"
          type="success"
          :bordered="false"
        >
          已修
        </n-tag>
        <div class="conn-card-body">
          <EngineIcon :family="conn.family" :engine="conn.engine" :size="26" />
          <div class="conn-card-main">
            <div class="conn-card-title">{{ conn.name || conn.id }}</div>
            <div class="conn-card-engine">{{ engineLabel(conn.engine) }}</div>
            <div class="conn-card-sum">{{ connectionSummary(conn.config) || "—" }}</div>
          </div>
        </div>
        <div class="conn-card-foot">
          <n-space align="center" size="small">
            <n-badge :type="statusMeta(conn.id).type" dot />
            <span class="muted">{{ statusMeta(conn.id).text }}</span>
          </n-space>
          <n-space size="small">
            <n-button
              size="tiny"
              :loading="!!pinging[conn.id]"
              @click="onPing($event, conn)"
            >
              <template #icon><n-icon :component="PulseOutline" /></template>
              测通
            </n-button>
            <n-button size="tiny" quaternary @click="onEdit($event, conn)">
              <template #icon><n-icon :component="CreateOutline" /></template>
            </n-button>
            <n-button size="tiny" quaternary type="error" @click="onDelete($event, conn)">
              <template #icon><n-icon :component="TrashOutline" /></template>
            </n-button>
          </n-space>
        </div>
      </n-card>
    </div>
  </div>
</template>
