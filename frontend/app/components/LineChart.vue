<template>
  <div style="width:100%;height:300px;position:relative">
    <canvas ref="canvasEl" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  data:      { type: Array, default: () => [] },
  splitDate: { type: String, default: '' },
})

const canvasEl = ref(null)
let chart = null

onMounted(async () => {
  await nextTick()
  if (props.data.length) draw()
})

watch(() => props.data, async () => {
  await nextTick()
  chart?.destroy()
  chart = null
  if (canvasEl.value) draw()
}, { deep: true })

onUnmounted(() => {
  chart?.destroy()
  chart = null
})

async function draw() {
  if (!canvasEl.value) return        // ← null check
  if (!props.data.length) return     // ← pas de données

  const { Chart, registerables } = await import('chart.js')
  Chart.register(...registerables)

  // Détruire le chart précédent si existe
  if (chart) { chart.destroy(); chart = null }
  if (!canvasEl.value) return        // ← vérifier encore après l'import async

  const labels   = props.data.map(d => d.date?.slice(5))
  const real     = props.data.map(d => d.price    ?? null)
  const forecast = props.data.map(d => d.forecast ?? null)

  chart = new Chart(canvasEl.value, {
    type: 'line',
    data: { labels, datasets: [
      { label:'Réel',  data: real,     borderColor:'#3b82f6', borderWidth:2, pointRadius:0, tension:0.3, spanGaps:false },
      { label:'LSTM',  data: forecast, borderColor:'#a78bfa', borderWidth:2, borderDash:[6,3], pointRadius:3, pointBackgroundColor:'#a78bfa', tension:0.3, spanGaps:false },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode:'index', intersect:false },
      plugins: {
        legend: { display:false },
        tooltip: { backgroundColor:'#0f1117', borderColor:'#1e2535', borderWidth:1, titleColor:'#8b95a8', bodyColor:'#f1f5f9',
          callbacks: { label: ctx => `${ctx.dataset.label} : ${Number(ctx.raw).toLocaleString('fr-FR',{maximumFractionDigits:2})} $` }
        },
      },
      scales: {
        x: { grid:{color:'#1e2535'}, ticks:{color:'#4b5563',font:{size:11},maxTicksLimit:8} },
        y: { grid:{color:'#1e2535'}, ticks:{color:'#4b5563',font:{size:11},
          callback: v => v > 999 ? `${(v/1000).toFixed(0)}k $` : `${v} $`
        }},
      },
    },
  })
}
</script>