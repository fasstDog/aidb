<script setup>
import { computed, ref, watch } from "vue";
import {
  CubeOutline,
  DocumentTextOutline,
  GridOutline,
  KeyOutline,
  LayersOutline,
  SearchOutline,
  ServerOutline,
} from "@vicons/ionicons5";
import { state } from "../store";

const props = defineProps({
  family: { type: String, default: "" },
  engine: { type: String, default: "" },
  icon: { type: String, default: "" },
  size: { type: Number, default: 28 },
  round: { type: Boolean, default: false },
  muted: { type: Boolean, default: false },
});

const ICONS = {
  postgres: LayersOutline,
  mysql: CubeOutline,
  oracle_like: GridOutline,
  document: DocumentTextOutline,
  kv: KeyOutline,
  search: SearchOutline,
  graph: ServerOutline,
};

const COLORS = {
  postgres: "#336791",
  mysql: "#4479A1",
  oracle_like: "#C74634",
  document: "#43A047",
  kv: "#FB8C00",
  search: "#7E57C2",
  graph: "#018BFF",
};

function resolveIconUrl(icon) {
  if (!icon) return "";
  const raw = String(icon).trim();
  if (!raw) return "";
  if (raw.startsWith("http://") || raw.startsWith("https://") || raw.startsWith("data:")) {
    return raw;
  }
  if (raw.startsWith("/static/")) return raw;
  if (raw.startsWith("/")) return "/static" + raw;
  return "/static/" + raw.replace(/^\.?\//, "");
}

const imgFailed = ref(false);
watch(
  () => [props.icon, props.engine],
  () => {
    imgFailed.value = false;
  }
);

const lookup = computed(() => String(props.family || props.engine || "").toLowerCase());

const iconSrc = computed(() => {
  if (props.icon) return resolveIconUrl(props.icon);
  const id = props.engine;
  if (id) {
    const g = state.gallery.find((e) => e.id === id);
    if (g && g.icon) return resolveIconUrl(g.icon);
    const eng = state.engines.find((e) => e.id === id);
    if (eng && eng.ui && eng.ui.icon) return resolveIconUrl(eng.ui.icon);
  }
  return "";
});

const iconComp = computed(() => ICONS[lookup.value] || ServerOutline);
const color = computed(() => COLORS[lookup.value] || "#2080f0");
const box = computed(() => Math.max(36, props.size + 12));

function onImgError() {
  imgFailed.value = true;
}
</script>

<template>
  <div
    class="engine-icon"
    :class="{ round, muted }"
    :style="{
      width: box + 'px',
      height: box + 'px',
      background: iconSrc && !imgFailed ? undefined : color,
    }"
  >
    <img
      v-if="iconSrc && !imgFailed"
      class="engine-icon-img"
      :src="iconSrc"
      :width="box"
      :height="box"
      alt=""
      draggable="false"
      @error="onImgError"
    />
    <n-icon v-else :component="iconComp" :size="size" color="#fff" />
  </div>
</template>
