<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Button, Input, Switch, useToast } from '@/lib'
import DoorCreateLayout from '@/layouts/DoorCreateLayout.vue'
import { createDeviceEndpointApiDevicesPost, createDoorEndpointApiDoorsPost } from '@/api/sdk.gen'
import type { DeviceCreateResponse } from '@/api/types.gen'

defineOptions({ name: 'DoorCreateView' })

type FormState = {
  name: string
  mqtt_id: string
  location: string
  is_active: boolean
  device_name: string
}
type FormErrors = Partial<Record<'name' | 'mqtt_id' | 'location' | 'device_name', string>>

const MQTT_ID_PATTERN = /^[a-z0-9][a-z0-9_-]*$/
const NAME_MAX = 128
const MQTT_ID_MAX = 64
const LOCATION_MAX = 256

const router = useRouter()
const toast = useToast()

const form = ref<FormState>({
  name: '',
  mqtt_id: '',
  location: '',
  is_active: true,
  device_name: '',
})
const errors = ref<FormErrors>({})
const submitting = ref(false)
const generalError = ref<string | null>(null)

const createdDoorId = ref<string | null>(null)
const created = ref<DeviceCreateResponse | null>(null)

function validate(): FormErrors {
  const e: FormErrors = {}
  const { name, mqtt_id, location, device_name } = form.value
  if (!name.trim()) e.name = 'Required.'
  else if (name.length > NAME_MAX) e.name = `At most ${NAME_MAX} characters.`
  if (!mqtt_id.trim()) e.mqtt_id = 'Required.'
  else if (mqtt_id.length > MQTT_ID_MAX) e.mqtt_id = `At most ${MQTT_ID_MAX} characters.`
  else if (!MQTT_ID_PATTERN.test(mqtt_id))
    e.mqtt_id = 'Lowercase letters, digits, _ or -. Must start with a letter or digit.'
  if (location.length > LOCATION_MAX) e.location = `At most ${LOCATION_MAX} characters.`
  if (!device_name.trim()) e.device_name = 'Required.'
  else if (device_name.length > NAME_MAX) e.device_name = `At most ${NAME_MAX} characters.`
  return e
}

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

async function submit() {
  generalError.value = null
  errors.value = validate()
  if (Object.keys(errors.value).length) return

  submitting.value = true
  try {
    let doorId = createdDoorId.value
    if (!doorId) {
      const doorRes = await createDoorEndpointApiDoorsPost({
        body: {
          name: form.value.name.trim(),
          mqtt_id: form.value.mqtt_id.trim(),
          location: form.value.location.trim() || null,
          is_active: form.value.is_active,
        },
        throwOnError: true,
      })
      doorId = doorRes.data.id
      createdDoorId.value = doorId
    }
    const deviceRes = await createDeviceEndpointApiDevicesPost({
      body: {
        name: form.value.device_name.trim(),
        door_id: doorId,
        is_active: true,
      },
      throwOnError: true,
    })
    created.value = deviceRes.data as DeviceCreateResponse
  } catch (err) {
    generalError.value = errorMessage(
      err,
      createdDoorId.value
        ? 'Door created but device setup failed. Adjust the device name and retry.'
        : 'Could not create door.',
    )
  } finally {
    submitting.value = false
  }
}

async function copyToken() {
  if (!created.value) return
  try {
    await navigator.clipboard.writeText(created.value.token)
    toast.show({ title: 'Token copied' })
  } catch {
    toast.show({ title: 'Copy failed; select and copy manually.' })
  }
}

async function copyDoorId() {
  if (!created.value) return
  try {
    await navigator.clipboard.writeText(created.value.door_id)
    toast.show({ title: 'Door ID copied' })
  } catch {
    toast.show({ title: 'Copy failed; select and copy manually.' })
  }
}

function done() {
  void router.push({ name: 'doors' })
}

function cancel() {
  void router.push({ name: 'doors' })
}
</script>

<template>
  <DoorCreateLayout>
    <div v-if="created" class="grid gap-3">
      <Alert variant="warn">
        Copy the device token now — it will not be shown again. Paste both values into the Jetson
        <code class="font-mono text-text-hi">.env</code> as
        <code class="font-mono text-text-hi">DOOR_ID</code> and
        <code class="font-mono text-text-hi">DEVICE_TOKEN</code>.
      </Alert>
      <div class="grid gap-2">
        <span class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
          Door <span class="text-text-lo">{{ form.name }}</span> · Device
          <span class="text-text-lo">{{ created.name }}</span>
        </span>
        <label class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
          DOOR_ID
        </label>
        <div class="flex items-center gap-2">
          <code
            class="grow break-all rounded-[2px] border border-border bg-element px-3 py-2 font-mono text-sm text-text-hi"
          >
            {{ created.door_id }}
          </code>
          <Button variant="ghost" size="sm" @click="copyDoorId">Copy</Button>
        </div>
        <label class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
          DEVICE_TOKEN
        </label>
        <div class="flex items-center gap-2">
          <code
            class="grow break-all rounded-[2px] border border-border bg-element px-3 py-2 font-mono text-sm text-text-hi"
          >
            {{ created.token }}
          </code>
          <Button variant="ghost" size="sm" @click="copyToken">Copy</Button>
        </div>
      </div>
      <div class="flex justify-end pt-2">
        <Button variant="primary" size="sm" @click="done">Done</Button>
      </div>
    </div>

    <div v-else class="grid gap-3">
      <Alert v-if="generalError" variant="err">{{ generalError }}</Alert>
      <Alert v-if="createdDoorId && !generalError" variant="warn">
        Door created. Finish device setup to issue the token.
      </Alert>

      <form class="grid gap-3" @submit.prevent="submit">
        <Input
          v-model="form.name"
          placeholder="Door name"
          :maxlength="NAME_MAX"
          :invalid="!!errors.name"
          :error="errors.name"
          :disabled="submitting || !!createdDoorId"
        />
        <Input
          v-model="form.mqtt_id"
          placeholder="MQTT ID"
          :maxlength="MQTT_ID_MAX"
          :invalid="!!errors.mqtt_id"
          :error="errors.mqtt_id"
          hint="Lowercase, digits, _ or -."
          :disabled="submitting || !!createdDoorId"
        />
        <Input
          v-model="form.location"
          placeholder="Location (optional)"
          :maxlength="LOCATION_MAX"
          :invalid="!!errors.location"
          :error="errors.location"
          :disabled="submitting || !!createdDoorId"
        />
        <Switch
          v-model="form.is_active"
          label="Active"
          description="Allow recognition and unlock"
          :disabled="submitting || !!createdDoorId"
        />
        <Input
          v-model="form.device_name"
          placeholder="Device name"
          :maxlength="NAME_MAX"
          :invalid="!!errors.device_name"
          :error="errors.device_name"
          hint="Unique camera identifier."
          :disabled="submitting"
        />
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" :disabled="submitting" @click="cancel">Cancel</Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            :loading="submitting"
            :disabled="submitting"
          >
            {{ createdDoorId ? 'Retry device' : 'Create' }}
          </Button>
        </div>
      </form>
    </div>
  </DoorCreateLayout>
</template>
