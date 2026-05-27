#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "pico/time.h"
#include "lwip/dns.h"
#include "lwip/apps/mqtt.h"
#include "lwip/altcp_tls.h"
#include "mbedtls/ssl.h"

// ── Logging ───────────────────────────────────────────────────────────────────
#define OK(fmt, ...)   do { printf("[+] " fmt "\n", ##__VA_ARGS__); stdio_flush(); } while(0)
#define INFO(fmt, ...) do { printf("[*] " fmt "\n", ##__VA_ARGS__); stdio_flush(); } while(0)
#define WARN(fmt, ...) do { printf("[!] " fmt "\n", ##__VA_ARGS__); stdio_flush(); } while(0)
#define DBG(fmt, ...)  do { printf("[v] " fmt "\n", ##__VA_ARGS__); stdio_flush(); } while(0)

// ── Credentials (gitignored) ──────────────────────────────────────────────────
#include "secrets.h"

// ── Door actuator pin ─────────────────────────────────────────────────────────
#define DOOR_PIN         15

// ── Runtime status cadence ────────────────────────────────────────────────────
#define LED_HEARTBEAT_MS       1000
#define STATUS_LOG_MS          5000
#define STATUS_PUBLISH_MS      10000
#define DOOR_PULSE_MS          1000

static mqtt_client_t *client;
static ip_addr_t broker_ip;
static volatile bool door_trigger    = false;
static volatile bool mqtt_do_connect = false;
static volatile bool mqtt_connected  = false;
static struct altcp_tls_config *tls_config;
static struct altcp_tls_config *active_sni_tls_config;
static const char *active_sni_hostname;

struct altcp_pcb *__real_altcp_tls_new(struct altcp_tls_config *config, u8_t ip_type);

struct altcp_pcb *__wrap_altcp_tls_new(struct altcp_tls_config *config, u8_t ip_type) {
    struct altcp_pcb *pcb = __real_altcp_tls_new(config, ip_type);
    if (pcb && config == active_sni_tls_config && active_sni_hostname) {
        mbedtls_ssl_context *ssl = (mbedtls_ssl_context *)altcp_tls_context(pcb);
        if (ssl) {
            int sni_err = mbedtls_ssl_set_hostname(ssl, active_sni_hostname);
            if (sni_err == 0) {
                DBG("TLS SNI hostname set: %s", active_sni_hostname);
            } else {
                WARN("mbedtls_ssl_set_hostname failed: %d", sni_err);
            }
        } else {
            WARN("TLS context not available for SNI");
        }
    }
    return pcb;
}

static void pub_cb(void *arg, err_t err) {
    if (err != ERR_OK) WARN("publish error: %d", err);
}

static void incoming_pub_cb(void *arg, const char *topic, u32_t tot_len) {
    INFO("incoming topic: %s (%lu bytes)", topic, (unsigned long)tot_len);
}

// Runs in lwIP IRQ context — only set a flag, never block here
static void incoming_data_cb(void *arg, const u8_t *data, u16_t len, u8_t flags) {
    DBG("data len=%d first_byte=0x%02X", len, len > 0 ? data[0] : 0);
    if (len > 0 && data[0] == '1') {
        door_trigger = true;
        OK("DOOR trigger received");
    }
}

static void sub_cb(void *arg, err_t err) {
    if (err == ERR_OK) OK("subscribed to %s", MQTT_SUB_TOPIC);
    else               WARN("subscribe failed: %d", err);
}

static void connection_cb(mqtt_client_t *c, void *arg, mqtt_connection_status_t status) {
    DBG("connection_cb status=%d", status);
    if (status == MQTT_CONNECT_ACCEPTED) {
        mqtt_connected = true;
        OK("MQTT connected");
        mqtt_set_inpub_callback(c, incoming_pub_cb, incoming_data_cb, NULL);
        DBG("subscribing to %s", MQTT_SUB_TOPIC);
        mqtt_subscribe(c, MQTT_SUB_TOPIC, 0, sub_cb, NULL);
        const char *hello = "Pico2W online";
        DBG("publishing hello");
        mqtt_publish(c, MQTT_PUB_TOPIC, hello, strlen(hello), 0, 0, pub_cb, NULL);
    } else {
        mqtt_connected = false;
        WARN("MQTT disconnected status=%d", status);
    }
}

// DNS callback: just save the IP and signal main loop — do NOT init TLS here
static void dns_cb(const char *name, const ip_addr_t *addr, void *arg) {
    if (!addr) { WARN("DNS failed for %s", name); return; }
    broker_ip = *addr;
    OK("resolved %s -> %s", name, ipaddr_ntoa(addr));
    mqtt_do_connect = true;
}

// Called from main loop (not IRQ) — safe to init TLS and connect
static void do_mqtt_connect(void) {
    DBG("do_mqtt_connect start");

    if (!tls_config) {
        tls_config = altcp_tls_create_config_client(NULL, 0);
        DBG("altcp_tls_create_config_client -> %p", tls_config);
        if (!tls_config) { WARN("TLS config alloc failed"); return; }
    }

    struct mqtt_connect_client_info_t ci = {
        .client_id   = MQTT_CLIENT_ID,
        .client_user = MQTT_USER,
        .client_pass = MQTT_PASS,
        .keep_alive  = 60,
        .tls_config  = tls_config,
    };

    DBG("connecting to %s:%d", ipaddr_ntoa(&broker_ip), MQTT_PORT);
    cyw43_arch_lwip_begin();
    active_sni_tls_config = tls_config;
    active_sni_hostname = MQTT_HOST;
    err_t err = mqtt_client_connect(client, &broker_ip, MQTT_PORT,
                                    connection_cb, NULL, &ci);
    active_sni_hostname = NULL;
    active_sni_tls_config = NULL;
    cyw43_arch_lwip_end();
    DBG("mqtt_client_connect -> err=%d", err);

    if (err != ERR_OK) WARN("mqtt_client_connect error: %d", err);
}

static void publish_status(bool door_active, bool led_on) {
    if (!client || !mqtt_connected) return;

    char payload[128];
    uint32_t uptime_ms = to_ms_since_boot(get_absolute_time());
    int len = snprintf(payload, sizeof(payload),
                       "{\"uptime_ms\":%lu,\"mqtt\":\"connected\",\"door\":\"%s\",\"led\":\"%s\"}",
                       (unsigned long)uptime_ms,
                       door_active ? "active" : "idle",
                       led_on ? "on" : "off");
    if (len < 0 || (size_t)len >= sizeof(payload)) {
        WARN("status payload truncated");
        return;
    }

    cyw43_arch_lwip_begin();
    err_t err = mqtt_publish(client, MQTT_PUB_TOPIC, payload, (size_t)len, 0, 0, pub_cb, NULL);
    cyw43_arch_lwip_end();

    if (err == ERR_OK) {
        DBG("status published: %s", payload);
    } else {
        WARN("status publish start failed: %d", err);
    }
}

int main() {
    stdio_init_all();
    sleep_ms(2000);
    INFO("Pico2W MQTT/TLS demo");

    gpio_init(DOOR_PIN);
    gpio_set_dir(DOOR_PIN, GPIO_OUT);
    gpio_put(DOOR_PIN, 0);

    if (cyw43_arch_init()) {
        WARN("cyw43_arch_init failed");
        return 1;
    }
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);
    cyw43_arch_enable_sta_mode();

    INFO("connecting to WiFi '%s'", WIFI_SSID);
    while (cyw43_arch_wifi_connect_timeout_ms(WIFI_SSID, WIFI_PASSWORD,
                                           CYW43_AUTH_WPA3_WPA2_AES_PSK, 30000)) {
        WARN("WiFi connection failed");
    }
    OK("WiFi connected");

    client = mqtt_client_new();
    if (!client) { WARN("mqtt_client_new failed"); return 1; }

    cyw43_arch_lwip_begin();
    err_t err = dns_gethostbyname(MQTT_HOST, &broker_ip, dns_cb, NULL);
    cyw43_arch_lwip_end();

    if (err == ERR_OK) {
        INFO("DNS cached: %s", ipaddr_ntoa(&broker_ip));
        mqtt_do_connect = true;
    } else if (err != ERR_INPROGRESS) {
        WARN("dns_gethostbyname error: %d", err);
        return 1;
    }

    absolute_time_t door_off_time = nil_time;
    bool door_active = false;
    bool led_on = false;
    absolute_time_t led_heartbeat_time = make_timeout_time_ms(LED_HEARTBEAT_MS);
    absolute_time_t status_log_time = make_timeout_time_ms(STATUS_LOG_MS);
    absolute_time_t status_publish_time = make_timeout_time_ms(STATUS_PUBLISH_MS);

    while (true) {
        cyw43_arch_poll();

        if (time_reached(led_heartbeat_time)) {
            led_on = !led_on;
            cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_on);
            led_heartbeat_time = make_timeout_time_ms(LED_HEARTBEAT_MS);
        }

        if (time_reached(status_log_time)) {
            INFO("heartbeat uptime=%lu ms mqtt=%s door=%s led=%s",
                 (unsigned long)to_ms_since_boot(get_absolute_time()),
                 mqtt_connected ? "connected" : "disconnected",
                 door_active ? "active" : "idle",
                 led_on ? "on" : "off");
            status_log_time = make_timeout_time_ms(STATUS_LOG_MS);
        }

        if (time_reached(status_publish_time)) {
            publish_status(door_active, led_on);
            status_publish_time = make_timeout_time_ms(STATUS_PUBLISH_MS);
        }

        if (mqtt_do_connect) {
            mqtt_do_connect = false;
            do_mqtt_connect();
        }

        if (door_trigger) {
            door_trigger = false;
            gpio_put(DOOR_PIN, 1);
            door_off_time = make_timeout_time_ms(DOOR_PULSE_MS);
            door_active = true;
            OK("GP15 HIGH");
        }

        if (door_active && time_reached(door_off_time)) {
            gpio_put(DOOR_PIN, 0);
            door_active = false;
            OK("GP15 LOW");
        }

        sleep_ms(10);
    }
}
