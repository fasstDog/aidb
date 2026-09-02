<script setup>
import { computed, onMounted, ref } from "vue";
import { darkTheme, dateZhCN, zhCN } from "naive-ui";
import { state, setDark, loadEngines, refreshConnections } from "./store";
import DatasourcePane from "./components/DatasourcePane.vue";
import CatalogPane from "./components/CatalogPane.vue";
import EditorPane from "./components/EditorPane.vue";
import BundleModal from "./components/BundleModal.vue";

const theme = computed(() => (state.dark ? darkTheme : null));
const bundleShow = ref(false);
const bootError = ref("");

onMounted(async () => {
  try {
    await loadEngines();
    await refreshConnections();
  } catch (err) {
    bootError.value = err.message || String(err);
  }
});
</script>

<template>
  <n-config-provider :theme="theme" :locale="zhCN" :date-locale="dateZhCN">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <n-layout style="height: 100vh">
          <n-layout-header bordered>
            <div class="app-header">
              <div>
                <h1>AIDB 配置台<span class="sub">连接 · 目录补丁 · 导入导出</span></h1>
              </div>
              <n-space align="center">
                <n-button size="small" @click="bundleShow = true">导入 / 导出</n-button>
                <n-text depth="3" style="font-size: 12px">深色</n-text>
                <n-switch :value="state.dark" @update:value="setDark" size="small" />
              </n-space>
            </div>
          </n-layout-header>
          <n-alert v-if="bootError" type="error" style="margin: 8px 12px">{{ bootError }}</n-alert>
          <n-layout has-sider style="height: calc(100vh - 52px)">
            <n-layout-sider
              :width="320"
              :native-scrollbar="false"
              bordered
              content-style="padding: 12px; height: 100%; overflow: auto;"
            >
              <DatasourcePane />
            </n-layout-sider>
            <n-layout-content
              :native-scrollbar="false"
              content-style="padding: 12px; height: 100%; overflow: auto;"
            >
              <CatalogPane />
            </n-layout-content>
            <n-layout-sider
              :width="400"
              :native-scrollbar="false"
              bordered
              content-style="padding: 12px; height: 100%; overflow: auto;"
            >
              <EditorPane />
            </n-layout-sider>
          </n-layout>
        </n-layout>
        <BundleModal v-model:show="bundleShow" />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
