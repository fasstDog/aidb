<script setup>
import { state, loadCatalogRoot } from "../store";
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
    <p v-if="state.treeMsg" class="muted">{{ state.treeMsg }}</p>
    <TreeNode v-if="state.treeRoot" :node="state.treeRoot" />
  </div>
</template>
