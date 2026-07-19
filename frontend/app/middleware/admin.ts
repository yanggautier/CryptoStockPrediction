export default defineNuxtRouteMiddleware(() => {
  const user = useState('user')

  // Pas connecté
  if (!user.value) {
    return navigateTo('/auth/login')
  }

  // Connecté mais pas admin
  if (!user.value.is_staff) {
    return navigateTo('/dashboard')
  }
})