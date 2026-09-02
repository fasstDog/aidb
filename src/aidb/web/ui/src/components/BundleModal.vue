<script setup>
import { ref } from "vue";
import { useMessage } from "naive-ui";
import { exportBundle, importBundle } from "../store";

const show = defineModel("show", { type: Boolean, default: false });
const message = useMessage();
const includeHistory = ref(false);
const text = ref("");

async function onExport() {
  try {
    const data = await exportBundle(includeHistory.value);
    text.value = JSON.stringify(data, null, 2);
    message.success("已导出");
  } catch (err) {
    message.error(err.message || "导出失败");
  }
}

async function onImport() {
  try {
    const raw = (text.value || "").trim();
    if (!raw) {
      message.warning("请选择文件或粘贴导出 JSON");
      return;
    }
    const obj = JSON.parse(raw);
    await importBundle(obj);
    message.success("已导入");
    show.value = false;
  } catch (err) {
    message.error(err.message || "导入失败");
  }
}

async function onFile(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  text.value = await file.text();
}
</script>

<template>
  <n-modal v-model:show="show">
    <n-card style="width: 640px" title="导入 / 导出" :bordered="false">
      <n-space vertical>
        <n-checkbox v-model:checked="includeHistory">含历史版本</n-checkbox>
        <n-space>
          <n-button size="small" @click="onExport">导出</n-button>
          <n-button size="small" type="primary" @click="onImport">导入</n-button>
        </n-space>
        <input type="file" accept="application/json,.json" @change="onFile" />
        <n-input
          v-model:value="text"
          type="textarea"
          :rows="16"
          placeholder="导出结果会显示在这里；也可粘贴 JSON 后导入"
        />
      </n-space>
    </n-card>
  </n-modal>
</template>
