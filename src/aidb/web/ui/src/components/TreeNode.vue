<script setup>
import {
  expandNode,
  loadMore,
  activateNode,
  isNodeActive,
} from "../store";

defineProps({
  node: { type: Object, required: true },
});
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
        @click.stop="expandNode(node)"
      >
        {{ node.open ? "▾" : "▸" }}
      </n-button>
      <span>{{ node.label }}</span>
      <n-tag v-if="node.patched" size="tiny" type="success" :bordered="false">已修</n-tag>
      <n-spin v-if="node.loading" :size="14" />
    </div>
    <div v-if="node.open" class="tree-children">
      <TreeNode v-for="child in node.children" :key="child.key" :node="child" />
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
