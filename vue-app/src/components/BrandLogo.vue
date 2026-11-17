<script setup lang="ts">
// Логотип «Брухтарня» (public/logo*.webp — фон прибрано, внутрішні чорні деталі збережено,
// тож виглядає однаково на темній і світлій темі).
const props = defineProps<{ size?: number; large?: boolean }>()
const src = props.large ? '/app/logo.webp' : '/app/logo-sm.webp'
</script>

<template>
  <img :src="src" :height="size ?? 32" :style="{ height: `${size ?? 32}px` }" alt="Брухтарня" class="brand-logo" draggable="false" />
</template>

<style scoped>
.brand-logo { width: auto; display: block; user-select: none; }
</style>
