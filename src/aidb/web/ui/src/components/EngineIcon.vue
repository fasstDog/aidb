<script setup>
import { computed } from "vue";
import {
  CubeOutline,
  DocumentTextOutline,
  GridOutline,
  KeyOutline,
  LayersOutline,
  SearchOutline,
  ServerOutline,
} from "@vicons/ionicons5";

const props = defineProps({
  family: { type: String, default: "" },
  engine: { type: String, default: "" },
  size: { type: Number, default: 28 },
});

const ICONS = {
  postgres: LayersOutline,
  mysql: CubeOutline,
  oracle_like: GridOutline,
  document: DocumentTextOutline,
  kv: KeyOutline,
  search: SearchOutline,
};

const COLORS = {
  postgres: "#336791",
  mysql: "#4479A1",
  oracle_like: "#C74634",
  document: "#43A047",
  kv: "#FB8C00",
  search: "#7E57C2",
};

const lookup = computed(() => String(props.family || props.engine || "").toLowerCase());
const iconComp = computed(() => ICONS[lookup.value] || ServerOutline);
const color = computed(() => COLORS[lookup.value] || "#2080f0");
const box = computed(() => Math.max(32, props.size + 16));
</script>

<template>
  <div
    class="engine-icon"
    :style="{
      width: box + 'px',
      height: box + 'px',
      background: color,
    }"
  >
    <n-icon :component="iconComp" :size="size" color="#fff" />
  </div>
</template>
