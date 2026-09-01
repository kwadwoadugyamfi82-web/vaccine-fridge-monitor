import streamlit as st
import paho.mqtt.client as mqtt
import json
import threading
import time

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "ghana-vaccine-fridge-AduGyamfiKwadwo-2026/status"

if "latest_data" not in st.session_state:
    st.session_state["latest_data"] = {
        "temperature": None, "compressor": None, "alertLevel": None, "alertText": None,
        "gasAlert": None, "gasReading": None, "warmMinutesToday": None, "door": None,
        "deviceTime": None, "last_update": None,
    }

if "connection_status" not in st.session_state:
    st.session_state["connection_status"] = {"connected": False, "error": None}

if "data_lock" not in st.session_state:
    st.session_state["data_lock"] = threading.Lock()

latest_data = st.session_state["latest_data"]
connection_status = st.session_state["connection_status"]
data_lock = st.session_state["data_lock"]

def on_connect(client, userdata, flags, reason_code, properties):
    connection_status["connected"] = True
    connection_status["error"] = None
    client.subscribe(MQTT_TOPIC)

def on_disconnect(client, userdata, flags, reason_code, properties):
    connection_status["connected"] = False

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        with data_lock:
            latest_data.update(payload)
            latest_data["last_update"] = time.strftime("%H:%M:%S")
    except Exception as e:
        print("Error parsing message:", e)

def start_mqtt_client():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        connection_status["error"] = f"{type(e).__name__}: {e}"

if "mqtt_started" not in st.session_state:
    thread = threading.Thread(target=start_mqtt_client, daemon=True)
    thread.start()
    st.session_state["mqtt_started"] = True

# -----------------------------
# STREAMLIT UI
# -----------------------------

st.set_page_config(page_title="Smart Vaccine Fridge Monitor", layout="centered")
st.title("🧊 Smart Vaccine Fridge Monitor")
st.caption("Live data from ESP32-S3 via MQTT — Ghana rural clinic prototype")

if connection_status["error"]:
    st.error(f"MQTT connection failed: {connection_status['error']}")
elif not connection_status["connected"]:
    st.warning("Connecting to MQTT broker...")
else:
    st.caption("✅ MQTT connected")

with data_lock:
    data = dict(latest_data)

if data["last_update"] is None:
    st.info("Waiting for data from the device... make sure the Wokwi simulation is running.")
else:
    col1, col2 = st.columns(2)
    col1.metric("Temperature", f"{data['temperature']} °C")
    col2.metric("Compressor", data["compressor"])

    alert_colors = {0: "🟢", 1: "🟡", 2: "🔴"}
    st.subheader(f"{alert_colors.get(data['alertLevel'], '⚪')} Fridge Health: {data['alertText']}")

    col3, col4 = st.columns(2)
    col3.metric("Door", data["door"])
    col4.metric("Cumulative Warm-Time Today", f"{data['warmMinutesToday']} min")

    st.divider()
    st.subheader("Sensor Details")

    col5, col6 = st.columns(2)
    col5.metric("Gas / Misuse Sensor (raw reading)", data["gasReading"])
    col6.metric("Device Time (from RTC)", data["deviceTime"])

    if data["gasAlert"]:
        st.error("⚠️ Possible non-vaccine item detected (gas reading above threshold)")
    else:
        st.success("Gas/misuse sensor: no unusual reading")

    st.caption(f"Last update: {data['last_update']}")

time.sleep(3)
st.rerun()
