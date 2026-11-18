<script setup lang="ts">
// Легкий графік «після кожної звірки»: стовпчик угору — плюс, униз — мінус. Без важких бібліотек.
import { computed } from 'vue'
import type { TimelinePoint } from '@/api'
import { dateUa, devKg, devMoney } from '@/format'
import { t } from '@/i18n'

const props = defineProps<{ points: TimelinePoint[] }>()
const emit = defineEmits<{ pick: [id: number] }>()
const shown = computed(() => props.points.slice(-24))
const max = computed(() => Math.max(1, ...shown.value.map((p) => Math.abs(p.deviation_amount))))
</script>

<template>
  <div class="bars" role="img">
    <div class="mid" />
    <button v-for="p in shown" :key="p.shipment_id" type="button" class="col" @click="emit('pick', p.shipment_id)">
      <span class="bar" :class="p.deviation_amount >= 0 ? 'up' : 'down'"
        :style="{ height: `${Math.max(3, (Math.abs(p.deviation_amount) / max) * 100) / 2}%` }" />
      <q-tooltip>{{ dateUa(p.ship_date) }} · {{ p.receiver_name }}<br>{{ devKg(p.deviation_kg) }} {{ t('common.kg') }} · {{ devMoney(p.deviation_amount) }}</q-tooltip>
    </button>
  </div>
</template>

<style scoped>
.bars { position: relative; display: flex; align-items: stretch; justify-content: space-evenly; gap: 4px; height: 96px; }
.mid { position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: var(--mg-border-strong); }
.col { position: relative; flex: 1; min-width: 6px; max-width: 40px; border: 0; padding: 0; background: transparent; cursor: pointer; }
.bar { position: absolute; left: 15%; right: 15%; border-radius: 6px; transition: opacity 0.2s; }
.bar.up { bottom: 50%; background: var(--mg-positive); border-radius: 6px 6px 2px 2px; }
.bar.down { top: 50%; background: var(--mg-negative); border-radius: 2px 2px 6px 6px; }
.col:hover .bar { opacity: 0.75; }
</style>
