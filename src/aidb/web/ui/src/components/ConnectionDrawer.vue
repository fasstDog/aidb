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

function onSelectEngine(item) {
  if (!item || item.visible === false) {
    message.info("该引擎尚未启用");
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
  <n-drawer v-model:show="state.drawerShow" :width="560" :trap-focus="false">
    <n-drawer-content :title="title" closable>
      <div v-if="state.drawerMode === 'create' && state.drawerStep === 'gallery'">
        <p class="muted" style="margin: 0 0 16px">从注册表选择引擎。未启用的显示为即将支持。</p>
        <n-grid :cols="2" :x-gap="12" :y-gap="12" responsive="screen">
          <n-grid-item v-for="item in state.gallery" :key="item.id">
            <n-card
              hoverable
              class="gallery-card"
              :class="{ disabled: item.visible === false }"
              @click="onSelectEngine(item)"
            >
              <n-tag
                v-if="item.visible === false"
                class="gallery-soon"
                size="small"
                type="warning"
                :bordered="false"
              >
                即将支持
              </n-tag>
              <div class="gallery-body">
                <EngineIcon :family="item.family" :engine="item.id" :size="22" />
                <div>
                  <div class="gallery-title">{{ item.label || item.id }}</div>
                  <div class="muted">{{ item.family }}</div>
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
        <n-empty v-if="!state.gallery.length" description="引擎画廊为空" />
      </div>
      <div v-else>
        <n-space v-if="state.drawerMode === 'create'" style="margin-bottom: 12px">
          <n-button size="small" quaternary @click="backToGallery">返回引擎墙</n-button>
        </n-space>
        <n-form label-placement="top" size="medium">
          <n-form-item label="引擎">
            <n-input :value="engineLabel(state.connForm.engine)" disabled />
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
