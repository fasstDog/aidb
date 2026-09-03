<script setup>
import {
  CubeOutline,
  FolderOutline,
  GridOutline,
  LayersOutline,
} from "@vicons/ionicons5";
import {
  expandNode,
  loadMore,
  activateNode,
  isNodeActive,
} from "../store";

defineProps({
  node: { type: Object, required: true },
});

const KIND_ICON = {
  namespace: FolderOutline,
  collection: GridOutline,
  field: CubeOutline,
};
</script>

<template>
  <div>
    <div
      class="tree-row"
      :class="[node.kind, { active: isNodeActive(node) }]"
      @click="activateNode(node)"
    >
      <n-button
        v-if="node.expandable"
        text
        size="tiny"
        class="tree-toggle"
        @click.stop="expandNode(node)"
      >
        {{ node.open ? "▾" : "▸" }}
      </n-button>
      <span v-else class="tree-spacer" />
      <n-icon
        :component="KIND_ICON[node.kind] || LayersOutline"
        :size="node.kind === 'field' ? 14 : 16"
        class="tree-icon"
      />
      <span class="tree-name" :title="node.name || node.label">{{ node.name || node.label }}</span>
      <div class="tree-meta">
        <n-tag
          v-if="node.kindLabel"
          size="tiny"
          :bordered="false"
          class="tree-kind-tag"
        >
          {{ node.kindLabel }}
        </n-tag>
        <n-tag
          v-if="node.kind === 'field' && node.type"
          size="tiny"
          :bordered="false"
          class="type-tag"
          :title="node.type"
        >
          {{ node.type }}
        </n-tag>
        <n-tag v-if="node.patched" size="tiny" type="success" :bordered="false">已修</n-tag>
        <n-spin v-if="node.loading" :size="14" />
      </div>
    </div>
    <div v-if="node.open" class="tree-children">
      <TreeNode v-for="child in node.children" :key="child.key" :node="child" />
      <p
        v-if="node.loaded && !node.loading && !node.children.length && !node.cursor"
        class="muted tree-empty"
      >
        暂无{{ node.kind === "namespace" ? "表" : "字段" }}
      </p>
      <n-button
        v-if="node.cursor"
        size="tiny"
        quaternary
        @click.stop="loadMore(node)"
      >
        加载更多
      </n-button>
    </div>
  </div>
</template>
