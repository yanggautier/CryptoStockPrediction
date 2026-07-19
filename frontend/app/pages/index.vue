<script setup>
const token = process.client ? localStorage.getItem('access_token') : null
navigateTo(token ? '/dashboard' : '/auth/login')
</script>