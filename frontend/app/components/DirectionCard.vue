<template>
  <div :style="cardStyle">
    <div style="display:flex;justify-content:space-between">
      <div>
        <p style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0">{{ name }}</p>
        <p style="color:#f1f5f9;font-size:20px;font-weight:700;margin:6px 0 2px">{{ fmt(lastPrice) }}</p>
        <p style="color:#6b7280;font-size:11px;margin:0">Prix actuel</p>
      </div>
      <div :style="badgeStyle">
        <div style="font-size:20px">{{ isUp ? '↑' : '↓' }}</div>
        <p :style="{color: isUp ? '#10b981' : '#ef4444', fontSize:'13px', fontWeight:700, margin:'4px 0 0'}">{{ isUp ? '+' : '' }}{{ pct }}%</p>
        <p style="color:#6b7280;font-size:10px;margin:0">J+1</p>
      </div>
    </div>
    <div style="margin-top:10px;display:flex;align-items:center;gap:5px">
      <span :style="{color: isUp ? '#10b981' : '#ef4444', fontSize:'12px'}">
        {{ isUp ? '▲' : '▼' }} LSTM : <strong>{{ fmt(nextPred) }}</strong>
      </span>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ name: String, lastPrice: Number, nextPred: Number })
const fmt   = v => v > 999 ? `$${Number(v).toLocaleString()}` : `$${v}`
const isUp  = computed(() => props.nextPred >= props.lastPrice)
const pct   = computed(() => props.lastPrice ? (((props.nextPred - props.lastPrice) / props.lastPrice) * 100).toFixed(2) : '0.00')
const cardStyle  = computed(() => ({ background:'linear-gradient(135deg,#0d1117,#111827)', border:`1px solid ${isUp.value ? '#064e3b' : '#4c0519'}`, borderRadius:'12px', padding:'16px 20px' }))
const badgeStyle = computed(() => ({ background: isUp.value ? 'rgba(16,185,129,.15)' : 'rgba(239,68,68,.15)', borderRadius:'10px', padding:'10px 14px', textAlign:'center' }))
</script>