<script setup>
import { computed, ref } from "vue";
import { useMessage } from "naive-ui";
import {
  state,
  saveOverlay,
  viewVersion,
  diffVersion,
  restoreVersion,
  nameVersion,
} from "../store";

const message = useMessage();
const tab = ref("patch");
const nameOpen = ref(false);
const nameLabel = ref("");
const naming = ref(null);

const title = computed(() => {
  if (state.overlayKind === "collection") {
    return (state.labels.collection || "集合") + " " + (state.overlayColl || "");
  }
  return "数据源";
});

const fieldEntries = computed(() => {
  const fields = state.collectionOverlay.fields || {};
  const cols = state.columns || [];
  return Object.keys(fields).map((name) => {
    const col = cols.find((c) => c.name === name) || {};
    return { name, type: col.type || "" };
  });
});

async function onSave() {
  try {
    await saveOverlay();
    message.success("补丁已保存");
  } catch (err) {
    message.error(err.message || "保存失败");
  }
}

async function onView(v) {
  try {
    await viewVersion(v);
    tab.value = "history";
  } catch (err) {
    message.error(err.message || "查看失败");
  }
}

async function onDiff(v) {
  try {
    await diffVersion(v);
  } catch (err) {
    message.error(err.message || "diff 失败");
  }
}

async function onRestore(v) {
  try {
    await restoreVersion(v);
    message.success("已恢复");
  } catch (err) {
    message.error(err.message || "恢复失败");
  }
}

function askName(v) {
  naming.value = v;
  nameLabel.value = v.label || "";
  nameOpen.value = true;
}

async function confirmName() {
  if (!naming.value || !nameLabel.value.trim()) return;
  try {
    await nameVersion(naming.value, nameLabel.value.trim());
    message.success("已命名");
  } catch (err) {
    message.error(err.message || "命名失败");
  } finally {
    nameOpen.value = false;
  }
}
</script>

<template>
  <n-card :bordered="false" content-style="padding: 0" class="editor-card">
    <h2 class="pane-title">补丁 / 历史</h2>
    <p v-if="!state.selectedId" class="muted">选择数据源或集合后编辑说明</p>
    <n-tabs v-else v-model:value="tab" type="line" size="small">
      <n-tab-pane name="patch" tab="补丁">
        <n-space vertical :size="16">
          <n-space align="center">
            <span>{{ title }}</span>
            <n-tag v-if="state.overlayPatched" size="small" type="success">已修</n-tag>
          </n-space>
          <n-form label-placement="top" size="medium">
            <template v-if="state.overlayKind === 'source'">
              <n-form-item label="数据源说明">
                <n-input v-model:value="state.sourceOverlay.description" type="textarea" :rows="3" />
              </n-form-item>
              <n-form-item label="查询规则">
                <n-input v-model:value="state.sourceOverlay.query_rules" type="textarea" :rows="4" />
              </n-form-item>
            </template>
            <template v-else>
              <n-form-item :label="(state.labels.collection || '集合') + '说明'">
                <n-input v-model:value="state.collectionOverlay.description" type="textarea" :rows="3" />
              </n-form-item>
              <n-form-item :label="(state.labels.field || '字段') + '说明'">
                <div
                  v-for="row in fieldEntries"
                  :key="row.name"
                  class="field-row"
                  :class="{ focus: state.focusField === row.name }"
                >
                  <span class="field-name">{{ row.name }}</span>
                  <n-tag v-if="row.type" size="tiny" type="info" :bordered="false">{{ row.type }}</n-tag>
                  <n-input v-model:value="state.collectionOverlay.fields[row.name]" size="small" />
                </div>
              </n-form-item>
            </template>
            <n-button type="primary" @click="onSave">保存补丁</n-button>
          </n-form>
        </n-space>
      </n-tab-pane>
      <n-tab-pane name="history" tab="历史">
        <n-empty v-if="!state.versions.length" description="暂无版本" size="small" />
        <div
          v-for="v in state.versions"
          :key="v.id"
          class="ver"
          :class="{ named: v.kind === 'named', current: v.current }"
        >
          <div>
            <strong :class="{ named: v.kind === 'named' }">{{ v.label || v.id }}</strong>
            <n-tag v-if="v.kind === 'named'" size="small" type="success" style="margin-left: 6px">命名</n-tag>
            <n-tag v-if="v.current" size="small" type="info" style="margin-left: 6px">HEAD</n-tag>
            <div class="muted">{{ v.created_at }}</div>
          </div>
          <n-space size="small">
            <n-button size="tiny" @click="onView(v)">查看</n-button>
            <n-button size="tiny" @click="onDiff(v)">diff</n-button>
            <n-button size="tiny" @click="onRestore(v)">恢复</n-button>
            <n-button v-if="v.kind !== 'named'" size="tiny" @click="askName(v)">命名</n-button>
          </n-space>
        </div>
        <pre v-if="state.histView" class="diff">{{ state.histView }}</pre>
        <n-modal v-model:show="nameOpen">
          <n-card style="width: 360px" title="命名版本">
            <n-input v-model:value="nameLabel" />
            <n-space style="margin-top: 12px" justify="end">
              <n-button size="small" @click="nameOpen = false">取消</n-button>
              <n-button size="small" type="primary" @click="confirmName">确定</n-button>
            </n-space>
          </n-card>
        </n-modal>
      </n-tab-pane>
    </n-tabs>
  </n-card>
</template>
