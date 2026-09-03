<script setup>
import { computed } from "vue";
import { useMessage } from "naive-ui";
import { schemaFields, isSecretField } from "../api";
import { api } from "../api";
import {
  state,
  engineById,
  engineLabel,
  readEngineConfig,
  pickGalleryEngine,
  closeDrawer,
  refreshConnections,
  openDetail,
  pingConnection,
} from "../store";
import EngineIcon from "./EngineIcon.vue";

const message = useMessage();

const currentEngine = computed(() => engineById(state.connForm.engine));
const fields = computed(() => schemaFields(currentEngine.value));
const title = computed(() => (state.drawerMode === "edit" ? "编辑数据源" : "新增数据源"));
const isGallery = computed(
  () => state.drawerMode === "create" && state.drawerStep === "gallery"
);
const drawerWidth = computed(() => (isGallery.value ? 760 : 520));

const gallerySorted = computed(() => {
  const rows = Array.isArray(state.gallery) ? state.gallery.slice() : [];
  rows.sort((a, b) => {
    const av = a.visible === false ? 1 : 0;
    const bv = b.visible === false ? 1 : 0;
    if (av !== bv) return av - bv;
    return String(a.label || a.id).localeCompare(String(b.label || b.id), "zh");
  });
  return rows;
});

const enabledCount = computed(() => gallerySorted.value.filter((e) => e.visible !== false).length);
const soonCount = computed(() => gallerySorted.value.length - enabledCount.value);

function onSelectEngine(item) {
  if (!item || item.visible === false) {
    message.info("该引擎即将支持，当前版本尚未启用");
    return;
  }
  pickGalleryEngine(item);
}

function backToGallery() {
  state.connForm.engine = null;
  state.connForm.config = {};
  state.drawerStep = "gallery";
}

function fieldRequired(field) {
  return !!field.required && !isSecretField(field);
}

async function onSave() {
  try {
    const payload = {
      name: (state.connForm.name || "").trim(),
      engine: state.connForm.engine,
      config: readEngineConfig(),
    };
    if (!payload.name) {
      message.error("请填写名称");
      return;
    }
    if (!payload.engine) {
      message.error("请选择引擎");
      return;
    }
    const id = state.connForm.id;
    let saved;
    if (id) {
      saved = await api("/api/connections/" + encodeURIComponent(id), {
        method: "PUT",
        body: payload,
      });
    } else {
      saved = await api("/api/connections", { method: "POST", body: payload });
    }
    message.success("已保存");
    closeDrawer();
    await refreshConnections();
    await openDetail(saved.id);
  } catch (err) {
    message.error(err.message || "保存失败");
  }
}

async function onPing() {
  const id = state.connForm.id;
  if (!id) {
    message.warning("请先保存连接");
    return;
  }
  try {
    await pingConnection(id);
    message.success("连通正常");
  } catch (err) {
    message.error(err.message || "连通失败");
  }
}
</script>

<template>
  <n-drawer v-model:show="state.drawerShow" :width="drawerWidth" :trap-focus="false">
    <n-drawer-content :title="title" closable :body-content-style="isGallery ? { paddingTop: '12px' } : undefined">
      <div v-if="isGallery" class="engine-wall">
        <div class="engine-wall-head">
          <div>
            <div class="engine-wall-title">选择数据库引擎</div>
            <p class="muted engine-wall-sub">
              已启用 {{ enabledCount }} 种，另有 {{ soonCount }} 种即将支持。
            </p>
          </div>
        </div>
        <div class="engine-wall-grid">
          <button
            v-for="item in gallerySorted"
            :key="item.id"
            type="button"
            class="engine-tile"
            :class="{ disabled: item.visible === false }"
            :title="item.visible === false ? '即将支持' : item.label || item.id"
            @click="onSelectEngine(item)"
          >
            <span v-if="item.visible === false" class="engine-tile-soon">即将支持</span>
            <EngineIcon
              class="engine-tile-logo"
              :family="item.family"
              :engine="item.id"
              :icon="item.icon"
              :size="40"
              :muted="item.visible === false"
              round
            />
            <div class="engine-tile-name">{{ item.label || item.id }}</div>
            <div class="engine-tile-desc">
              {{ item.description || item.family || item.id }}
            </div>
          </button>
        </div>
        <n-empty v-if="!gallerySorted.length" description="引擎画廊为空" />
      </div>
      <div v-else>
        <n-space v-if="state.drawerMode === 'create'" style="margin-bottom: 12px">
          <n-button size="small" quaternary @click="backToGallery">返回引擎墙</n-button>
        </n-space>
        <n-form label-placement="top" size="medium">
          <n-form-item label="引擎">
            <n-space align="center">
              <EngineIcon
                :family="currentEngine && currentEngine.family"
                :engine="state.connForm.engine"
                :icon="currentEngine && ((currentEngine.ui && currentEngine.ui.icon) || currentEngine.icon)"
                :size="22"
              />
              <n-input :value="engineLabel(state.connForm.engine)" disabled style="min-width: 200px" />
            </n-space>
          </n-form-item>
          <n-form-item label="名称" required>
            <n-input v-model:value="state.connForm.name" placeholder="订单库" />
          </n-form-item>
          <n-form-item
            v-for="field in fields"
            :key="field.key"
            :label="field.label || field.key"
            :required="fieldRequired(field)"
          >
            <n-input-number
              v-if="field.type === 'int'"
              v-model:value="state.connForm.config[field.key]"
              style="width: 100%"
            />
            <n-input
              v-else-if="field.type === 'text'"
              v-model:value="state.connForm.config[field.key]"
              type="textarea"
              :rows="3"
            />
            <n-input
              v-else-if="isSecretField(field)"
              v-model:value="state.connForm.config[field.key]"
              type="password"
              show-password-on="click"
              placeholder="留空则保持不变"
              autocomplete="new-password"
            />
            <n-input v-else v-model:value="state.connForm.config[field.key]" />
          </n-form-item>
          <n-space>
            <n-button type="primary" @click="onSave">保存</n-button>
            <n-button v-if="state.connForm.id" @click="onPing">测连通</n-button>
            <n-button quaternary @click="closeDrawer">取消</n-button>
          </n-space>
        </n-form>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>
