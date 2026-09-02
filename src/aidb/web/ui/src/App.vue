<script setup>
import { computed } from "vue";
import { darkTheme, dateZhCN, zhCN } from "naive-ui";
import { state } from "./store";
import Shell from "./components/Shell.vue";

const theme = computed(() => (state.dark ? darkTheme : null));
</script>

<template>
  <n-config-provider :theme="theme" :locale="zhCN" :date-locale="dateZhCN">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <Shell />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
