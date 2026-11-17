<script setup lang="ts">
// Тимчасовий знак: зливок металу з відблиском. Коли буде логотип — замінити вміст цього файлу.
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 28" :height="size ?? 28" viewBox="0 0 48 48" aria-hidden="true" class="brand-logo">
    <defs>
      <linearGradient id="bt-ingot" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#F3B26B" />
        <stop offset="0.55" stop-color="var(--mg-primary)" />
        <stop offset="1" stop-color="#7A3E12" />
      </linearGradient>
    </defs>
    <path d="M10 30 L16 18 H38 L44 30 Z" fill="url(#bt-ingot)" />
    <path d="M4 42 L10 30 H44 L38 42 Z" fill="url(#bt-ingot)" opacity="0.85" />
    <path d="M17 20 H30 L28.5 23 H15.5 Z" fill="#fff" opacity="0.35" />
    <path d="M24 6 l1.6 4.4 4.4 1.6 -4.4 1.6 -1.6 4.4 -1.6 -4.4 -4.4 -1.6 4.4 -1.6 Z" fill="#FFD9A8" />
  </svg>
</template>
