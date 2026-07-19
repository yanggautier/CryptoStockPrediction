<!-- Voir TrainButton.vue généré séparément -->
<template>
  <button @click="handleClick" :disabled="state === 'loading'" :style="btnStyle">
    <span v-if="state === 'loading'" style="display:inline-block;animation:spin 1s linear infinite">⟳</span>
    <span v-else>{{ state === 'success' ? '✓' : '🧠' }}</span>
    {{ label }}
  </button>
</template>
<script setup>
import { ref, computed } from 'vue'
const emit = defineEmits(['train'])
const state = ref('idle')
const labels = { idle: "Lancer l'entraînement", loading: 'Entraînement...', success: 'Modèle mis à jour ✓' }
const colors = { idle: '#7c3aed', loading: '#f59e0b', success: '#10b981' }
const bgs    = { idle: 'rgba(124,58,237,.15)', loading: 'rgba(245,158,11,.15)', success: 'rgba(16,185,129,.15)' }
const label    = computed(() => labels[state.value])
const btnStyle = computed(() => ({ display:'flex', alignItems:'center', gap:'8px', background: bgs[state.value], border:`1px solid ${colors[state.value]}`, color: colors[state.value], borderRadius:'8px', padding:'9px 18px', fontSize:'13px', fontWeight:600, cursor: state.value==='loading' ? 'wait' : 'pointer' }))
async function handleClick() {
  state.value = 'loading'
  await new Promise(r => setTimeout(r, 2500))
  state.value = 'success'
  emit('train')
  setTimeout(() => { state.value = 'idle' }, 3500)
}
</script>