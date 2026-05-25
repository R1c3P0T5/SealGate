import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const PUBLIC_PATH_PREFIXES = ['/login', '/register']

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      component: () => import('@/layouts/AuthLayout.vue'),
      children: [
        {
          path: '',
          name: 'login',
          component: () => import('@/views/LoginView.vue'),
        },
      ],
    },
    {
      path: '/register',
      component: () => import('@/layouts/AuthLayout.vue'),
      children: [
        {
          path: '',
          name: 'register',
          component: () => import('@/views/RegisterView.vue'),
        },
      ],
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        {
          path: 'recognize',
          name: 'recognize',
          component: () => import('@/views/LiveRecognitionView.vue'),
          meta: { adminOnly: true },
        },
        { path: 'faces', name: 'faces', component: () => import('@/views/FacesView.vue') },
        {
          path: 'faces/new',
          name: 'faces-new',
          component: () => import('@/views/AddFaceView.vue'),
        },
        {
          path: 'access-logs',
          name: 'access-logs',
          component: () => import('@/views/AccessLogsView.vue'),
          meta: { adminOnly: true },
        },
        {
          path: 'doors',
          name: 'doors',
          component: () => import('@/views/DoorsView.vue'),
          meta: { adminOnly: true },
        },
        {
          path: 'doors/new',
          name: 'doors-new',
          component: () => import('@/views/DoorCreateView.vue'),
          meta: { adminOnly: true },
        },
        {
          path: 'user-management',
          name: 'user-management',
          component: () => import('@/views/UserManagementView.vue'),
          meta: { adminOnly: true },
        },
        {
          path: 'user-management/:userId',
          name: 'user-management-edit',
          component: () => import('@/views/UserEditView.vue'),
          meta: { adminOnly: true },
        },
        { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const isPublic = PUBLIC_PATH_PREFIXES.some((prefix) => to.path.startsWith(prefix))

  if (!auth.isAuthenticated && !isPublic) return { name: 'login' }
  if (auth.isAuthenticated && isPublic) return { name: 'dashboard' }
  if (to.meta.adminOnly && auth.user?.role_name !== 'admin') return { name: 'dashboard' }
})

export default router
