<template>
  <div>
    <AppNav v-if="showNav" />
    <NuxtPage />
  </div>
</template>

<script setup>
const route   = useRoute()
const showNav = computed(() => !route.path.startsWith('/auth'))

const lang = useState('lang', () => 'fr')
onMounted(() => {
  lang.value = localStorage.getItem('lang') ?? 'fr'
})
</script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #060810;
  min-height: 100vh;
  font-family: 'Inter', system-ui, sans-serif;
  color: #f1f5f9;
}
</style>