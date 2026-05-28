<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sidebar, Nav, Button, Toast } from '@/lib'
import type { NavItemDef } from '@/lib'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'AppLayout' })

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const sidebarOpen = ref(false)

const navItems = computed<NavItemDef[]>(() => {
  const isAdmin = auth.user?.role_name === 'admin'
  const items: NavItemDef[] = [{ key: 'dashboard', label: 'Dashboard', href: '/' }]
  if (isAdmin) {
    items.push({ key: 'recognize', label: 'Live Recognition', href: '/recognize' })
  }
  items.push({ key: 'faces', label: 'Face Management', href: '/faces' })
  if (isAdmin) {
    items.push({ key: 'access-logs', label: 'Access Logs', href: '/access-logs' })
    items.push({ key: 'doors', label: 'Doors', href: '/doors' })
    items.push({ key: 'user-management', label: 'User Management', href: '/user-management' })
  }
  items.push({ key: 'settings', label: 'Settings', href: '/settings' })
  return items
})

const activeKey = computed(() => {
  const name = String(route.name ?? '')
  if (name === 'faces-new') return 'faces'
  if (name === 'doors-new' || name === 'doors-edit') return 'doors'
  return name
})

function navigate(item: NavItemDef) {
  if (item.href) router.push(item.href)
  sidebarOpen.value = false
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}

watch(
  () => route.path,
  () => {
    sidebarOpen.value = false
  },
)
</script>

<template>
  <div class="flex min-h-screen bg-bg">
    <button
      type="button"
      class="fixed left-3 top-3 z-30 flex h-9 w-9 items-center justify-center rounded-[2px] border border-border bg-subtle font-mono text-base text-text-hi md:hidden"
      aria-label="Open menu"
      @click="sidebarOpen = true"
    >
      ☰
    </button>

    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-40 bg-black/50 md:hidden"
      aria-hidden="true"
      @click="sidebarOpen = false"
    />

    <div :class="['z-50', sidebarOpen ? 'fixed left-0 top-0 h-dvh' : 'hidden md:block']">
      <Sidebar brand="FaceGuard">
        <Nav :items="navItems" :model-value="activeKey" @click="navigate" />
        <template #footer>
          <div class="flex items-center justify-between gap-2">
            <span class="truncate font-mono text-[11px] text-text-lo">{{
              auth.user?.username
            }}</span>
            <Button variant="ghost" size="xs" @click="logout">Logout</Button>
          </div>
        </template>
      </Sidebar>
    </div>

    <main class="min-w-0 flex-1 p-4 pt-14 md:p-6">
      <RouterView />
    </main>
    <Toast />
  </div>
</template>
