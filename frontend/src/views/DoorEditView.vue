<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Alert, Button, Input, Skeleton, Switch, useToast } from '@/lib'
import DoorEditLayout from '@/layouts/DoorEditLayout.vue'
import {
  createDeviceEndpointApiDevicesPost,
  deleteDeviceEndpointApiDevicesDeviceIdDelete,
  deleteDoorEndpointApiDoorsDoorIdDelete,
  getDoorEndpointApiDoorsDoorIdGet,
  listDevicesEndpointApiDevicesGet,
  rotateDeviceTokenEndpointApiDevicesDeviceIdRotateTokenPost,
  updateDeviceEndpointApiDevicesDeviceIdPut,
  updateDoorEndpointApiDoorsDoorIdPut,
} from '@/api/sdk.gen'
import type { DeviceResponse, DoorResponse } from '@/api/types.gen'

defineOptions({ name: 'DoorEditView' })

type DoorForm = {
  name: string
  mqtt_id: string
  location: string
  is_active: boolean
}
type DeviceForm = {
  name: string
  is_active: boolean
}
type FormErrors = Partial<
  Record<'name' | 'mqtt_id' | 'location' | 'device_name' | 'new_device_name', string>
>

const MQTT_ID_PATTERN = /^[a-z0-9][a-z0-9_-]*$/
const NAME_MAX = 128
const MQTT_ID_MAX = 64
const LOCATION_MAX = 256

const route = useRoute()
const router = useRouter()
const toast = useToast()

const doorId = computed(() => String(route.params.doorId))

const door = ref<DoorResponse | null>(null)
const device = ref<DeviceResponse | null>(null)
const doorForm = ref<DoorForm>({ name: '', mqtt_id: '', location: '', is_active: true })
const deviceForm = ref<DeviceForm>({ name: '', is_active: true })
const newDeviceName = ref('')
const errors = ref<FormErrors>({})

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const rotating = ref(false)
const addingDevice = ref(false)
const removingDevice = ref(false)

const loadError = ref<string | null>(null)
const generalError = ref<string | null>(null)
const newToken = ref<string | null>(null)

const busy = computed(
  () =>
    saving.value || deleting.value || rotating.value || addingDevice.value || removingDevice.value,
)

function applyDoor(d: DoorResponse) {
  door.value = d
  doorForm.value = {
    name: d.name,
    mqtt_id: d.mqtt_id ?? '',
    location: d.location ?? '',
    is_active: d.is_active,
  }
}

function applyDevice(d: DeviceResponse | null) {
  device.value = d
  deviceForm.value = d ? { name: d.name, is_active: d.is_active } : { name: '', is_active: true }
}

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

function validateForSave(): FormErrors {
  const e: FormErrors = {}
  const { name, mqtt_id, location } = doorForm.value
  if (!name.trim()) e.name = 'Required.'
  else if (name.length > NAME_MAX) e.name = `At most ${NAME_MAX} characters.`
  if (!mqtt_id.trim()) e.mqtt_id = 'Required.'
  else if (mqtt_id.length > MQTT_ID_MAX) e.mqtt_id = `At most ${MQTT_ID_MAX} characters.`
  else if (!MQTT_ID_PATTERN.test(mqtt_id))
    e.mqtt_id = 'Lowercase letters, digits, _ or -. Must start with a letter or digit.'
  if (location.length > LOCATION_MAX) e.location = `At most ${LOCATION_MAX} characters.`
  if (device.value) {
    if (!deviceForm.value.name.trim()) e.device_name = 'Required.'
    else if (deviceForm.value.name.length > NAME_MAX)
      e.device_name = `At most ${NAME_MAX} characters.`
  }
  return e
}

const doorDirty = computed(() => {
  if (!door.value) return false
  return (
    door.value.name !== doorForm.value.name ||
    (door.value.mqtt_id ?? '') !== doorForm.value.mqtt_id ||
    (door.value.location ?? '') !== doorForm.value.location ||
    door.value.is_active !== doorForm.value.is_active
  )
})

const deviceDirty = computed(() => {
  if (!device.value) return false
  return (
    device.value.name !== deviceForm.value.name ||
    device.value.is_active !== deviceForm.value.is_active
  )
})

const dirty = computed(() => doorDirty.value || deviceDirty.value)

async function load() {
  loading.value = true
  loadError.value = null
  try {
    const [doorRes, devicesRes] = await Promise.all([
      getDoorEndpointApiDoorsDoorIdGet({
        path: { door_id: doorId.value },
        throwOnError: true,
      }),
      listDevicesEndpointApiDevicesGet({ query: { limit: 100 }, throwOnError: true }),
    ])
    applyDoor(doorRes.data as DoorResponse)
    const match = devicesRes.data.devices.find((d) => d.door_id === doorId.value) ?? null
    applyDevice(match)
  } catch (err) {
    loadError.value = errorMessage(err, 'Could not load door.')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!door.value || !dirty.value) return
  generalError.value = null
  errors.value = validateForSave()
  if (Object.keys(errors.value).length) return

  saving.value = true
  try {
    if (doorDirty.value) {
      const res = await updateDoorEndpointApiDoorsDoorIdPut({
        path: { door_id: door.value.id },
        body: {
          name: doorForm.value.name.trim(),
          mqtt_id: doorForm.value.mqtt_id.trim(),
          location: doorForm.value.location.trim() || null,
          is_active: doorForm.value.is_active,
        },
        throwOnError: true,
      })
      applyDoor(res.data as DoorResponse)
    }
    if (deviceDirty.value && device.value) {
      const res = await updateDeviceEndpointApiDevicesDeviceIdPut({
        path: { device_id: device.value.id },
        body: {
          name: deviceForm.value.name.trim(),
          is_active: deviceForm.value.is_active,
        },
        throwOnError: true,
      })
      applyDevice(res.data as DeviceResponse)
    }
    toast.show({ title: 'Saved' })
  } catch (err) {
    generalError.value = errorMessage(err, 'Save failed.')
  } finally {
    saving.value = false
  }
}

async function rotateToken() {
  if (!device.value) return
  if (
    !window.confirm(
      `Rotate token for "${device.value.name}"? The current token will stop working immediately.`,
    )
  )
    return

  rotating.value = true
  generalError.value = null
  try {
    const res = await rotateDeviceTokenEndpointApiDevicesDeviceIdRotateTokenPost({
      path: { device_id: device.value.id },
      throwOnError: true,
    })
    newToken.value = res.data.token
    applyDevice(res.data as DeviceResponse)
  } catch (err) {
    generalError.value = errorMessage(err, 'Could not rotate token.')
  } finally {
    rotating.value = false
  }
}

async function removeDevice() {
  if (!device.value) return
  if (!window.confirm(`Remove device "${device.value.name}" from this door?`)) return

  removingDevice.value = true
  generalError.value = null
  try {
    await deleteDeviceEndpointApiDevicesDeviceIdDelete({
      path: { device_id: device.value.id },
      throwOnError: true,
    })
    applyDevice(null)
    newToken.value = null
    toast.show({ title: 'Device removed' })
  } catch (err) {
    generalError.value = errorMessage(err, 'Could not remove device.')
  } finally {
    removingDevice.value = false
  }
}

async function addDevice() {
  if (!door.value) return
  errors.value = {}
  const name = newDeviceName.value.trim()
  if (!name) {
    errors.value = { new_device_name: 'Required.' }
    return
  }
  if (name.length > NAME_MAX) {
    errors.value = { new_device_name: `At most ${NAME_MAX} characters.` }
    return
  }

  addingDevice.value = true
  generalError.value = null
  try {
    const res = await createDeviceEndpointApiDevicesPost({
      body: { name, door_id: door.value.id, is_active: true },
      throwOnError: true,
    })
    applyDevice(res.data as DeviceResponse)
    newToken.value = res.data.token
    newDeviceName.value = ''
  } catch (err) {
    generalError.value = errorMessage(err, 'Could not add device.')
  } finally {
    addingDevice.value = false
  }
}

async function remove() {
  if (!door.value) return
  const message = device.value
    ? `Delete door "${door.value.name}" and its device? This cannot be undone.`
    : `Delete door "${door.value.name}"? This cannot be undone.`
  if (!window.confirm(message)) return

  deleting.value = true
  generalError.value = null
  try {
    if (device.value) {
      await deleteDeviceEndpointApiDevicesDeviceIdDelete({
        path: { device_id: device.value.id },
        throwOnError: true,
      })
    }
    await deleteDoorEndpointApiDoorsDoorIdDelete({
      path: { door_id: door.value.id },
      throwOnError: true,
    })
    toast.show({ title: 'Door deleted' })
    void router.push({ name: 'doors' })
  } catch (err) {
    generalError.value = errorMessage(err, 'Could not delete door.')
    deleting.value = false
  }
}

async function copyToken() {
  if (!newToken.value) return
  try {
    await navigator.clipboard.writeText(newToken.value)
    toast.show({ title: 'Token copied' })
  } catch {
    toast.show({ title: 'Copy failed; select and copy manually.' })
  }
}

function dismissToken() {
  newToken.value = null
}

onMounted(load)
</script>

<template>
  <DoorEditLayout>
    <template #title>{{ door?.name ?? '—' }}</template>
    <template v-if="door" #actions>
      <Button variant="err" size="sm" :loading="deleting" :disabled="busy" @click="remove">
        Delete
      </Button>
      <Button
        variant="primary"
        size="sm"
        :loading="saving"
        :disabled="!dirty || busy"
        @click="save"
      >
        Save
      </Button>
    </template>

    <Alert v-if="loadError" variant="err" class="mb-3">{{ loadError }}</Alert>
    <Alert v-if="generalError" variant="err" class="mb-3">{{ generalError }}</Alert>

    <div v-if="newToken" class="mb-3 grid gap-3 rounded-[2px] border border-border bg-bg p-3">
      <Alert variant="warn">
        New device token issued. Copy now — it will not be shown again. Paste into the Jetson
        <code class="font-mono text-text-hi">.env</code> as
        <code class="font-mono text-text-hi">DEVICE_TOKEN</code>.
      </Alert>
      <div class="flex items-center gap-2">
        <code
          class="grow break-all rounded-[2px] border border-border bg-element px-3 py-2 font-mono text-sm text-text-hi"
        >
          {{ newToken }}
        </code>
        <Button variant="ghost" size="sm" @click="copyToken">Copy</Button>
      </div>
      <div class="flex justify-end">
        <Button variant="primary" size="sm" @click="dismissToken">Dismiss</Button>
      </div>
    </div>

    <div v-if="loading" class="grid gap-3">
      <Skeleton :height="40" />
      <Skeleton :height="40" />
      <Skeleton :height="40" />
      <Skeleton :height="40" />
    </div>

    <div v-else-if="door" class="grid gap-5">
      <section class="grid gap-3">
        <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">Door</h2>
        <Input
          v-model="doorForm.name"
          placeholder="Name"
          :maxlength="NAME_MAX"
          :invalid="!!errors.name"
          :error="errors.name"
          :disabled="busy"
        />
        <Input
          v-model="doorForm.mqtt_id"
          placeholder="MQTT ID"
          :maxlength="MQTT_ID_MAX"
          :invalid="!!errors.mqtt_id"
          :error="errors.mqtt_id"
          hint="Lowercase, digits, _ or -."
          :disabled="busy"
        />
        <Input
          v-model="doorForm.location"
          placeholder="Location (optional)"
          :maxlength="LOCATION_MAX"
          :invalid="!!errors.location"
          :error="errors.location"
          :disabled="busy"
        />
        <Switch
          v-model="doorForm.is_active"
          label="Active"
          description="Allow recognition and unlock"
          :disabled="busy"
        />
      </section>

      <section class="grid gap-3 border-t border-border-soft pt-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
            Device
          </h2>
          <div v-if="device" class="flex items-center gap-2">
            <Button
              variant="ghost"
              size="xs"
              :loading="rotating"
              :disabled="busy"
              @click="rotateToken"
            >
              Rotate token
            </Button>
            <Button
              variant="ghost"
              size="xs"
              :loading="removingDevice"
              :disabled="busy"
              @click="removeDevice"
            >
              Remove
            </Button>
          </div>
        </div>

        <template v-if="device">
          <Input
            v-model="deviceForm.name"
            placeholder="Device name"
            :maxlength="NAME_MAX"
            :invalid="!!errors.device_name"
            :error="errors.device_name"
            :disabled="busy"
          />
          <Switch
            v-model="deviceForm.is_active"
            label="Active"
            description="Allow this device to connect"
            :disabled="busy"
          />
        </template>

        <div v-else class="grid gap-3">
          <Alert variant="warn">No device attached. Add one to issue a token.</Alert>
          <div class="flex items-end gap-2">
            <div class="grow">
              <Input
                v-model="newDeviceName"
                placeholder="Device name"
                :maxlength="NAME_MAX"
                :invalid="!!errors.new_device_name"
                :error="errors.new_device_name"
                :disabled="busy"
              />
            </div>
            <Button
              variant="primary"
              size="sm"
              :loading="addingDevice"
              :disabled="busy"
              @click="addDevice"
            >
              Add device
            </Button>
          </div>
        </div>
      </section>
    </div>
  </DoorEditLayout>
</template>
