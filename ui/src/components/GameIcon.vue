<script setup lang="ts">
import { computed } from "vue";

import { type GameIconName, gameIconUrls } from "../icons/gameIconPack";

const props = withDefaults(
  defineProps<{
    name: GameIconName;
    label?: string;
    size?: number;
  }>(),
  {
    label: "",
    size: 20,
  },
);

const iconUrl = computed(() => gameIconUrls[props.name]);
const sizeStyle = computed(() => `${props.size}px`);
</script>

<template>
  <img
    class="game-icon"
    :src="iconUrl"
    :alt="label"
    :aria-hidden="label ? undefined : 'true'"
    :style="{ width: sizeStyle, height: sizeStyle }"
  />
</template>

<style scoped>
.game-icon {
  display: inline-block;
  object-fit: contain;
  vertical-align: middle;
}
</style>
