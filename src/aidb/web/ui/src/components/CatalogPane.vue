<script setup>
import { DocumentTextOutline } from "@vicons/ionicons5";
import {
  state,
  loadCatalogRoot,
  loadMoreRoot,
  activateSourceOverlay,
  isSourceOverlayActive,
} from "../store";
import TreeNode from "./TreeNode.vue";
</script>

<template>
  <div class="catalog-pane">
    <h2 class="pane-title">目录</h2>
    <n-input
      v-if="state.selectedId"
      v-model:value="state.catalogQ"
      size="small"
      clearable
      placeholder="筛选后回车"
      style="margin-bottom: 12px"
      @keyup.enter="loadCatalogRoot"
    />
    <div
      v-if="state.selectedId"
      class="tree-row source-entry"
      :class="{ active: isSourceOverlayActive() }"
      @click="activateSourceOverlay"
    >
      <span class="tree-spacer" />
      <n-icon :component="DocumentTextOutline" :size="16" class="tree-icon" />
      <span class="tree-name">数据源说明</span>
      <div class="tree-meta">
        <n-tag v-if="state.sourcePatched[state.selectedId]" size="tiny" type="success" :bordered="false">
          已修
        </n-tag>
      </div>
    </div>
    <p v-if="state.treeMsg" class="muted">{{ state.treeMsg }}</p>
    <TreeNode v-for="node in state.treeNodes" :key="node.key" :node="node" />
    <n-button
      v-if="state.treeCursor"
      size="tiny"
      quaternary
      style="margin-top: 4px"
      @click="loadMoreRoot"
    >
      加载更多
    </n-button>
  </div>
</template>
