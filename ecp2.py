from __future__ import annotations
from dataclasses import dataclass, Field
from typing import Final
import aiohttp
import asyncio
import base64
import hashlib
import json
import socket
import websockets
# Note: https://docs.python.org/3/library/xml.html#xml-security
# Only use this on devices you trust.
import xml.etree.ElementTree as ET

SSDP_BROADCAST_ADDR: tuple[str, int] = ("239.255.255.250", 1900)
SSDP_BROADCAST: str = f"""M-SEARCH * HTTP/1.1\r
Host: {SSDP_BROADCAST_ADDR[0]}:{SSDP_BROADCAST_ADDR[1]}\r
MAN: "ssdp:discover"\r
ST: roku:ecp\r
\r\n"""

class ECPError(Exception):
    pass

# Some buttons are missing from this still
class Button:
    VOLUME_UP: Final = "VolumeUp"
    VOLUME_DOWN: Final = "VolumeDown"
    VOLUME_MUTE: Final = "VolumeMute"
    HOME: Final = "Home"
    REV: Final = "Rev"
    FWD: Final = "Fwd"
    PLAY: Final = "Play"
    SELECT: Final = "Select"
    LEFT: Final = "Left"
    RIGHT: Final = "Right"
    DOWN: Final = "Down"
    UP: Final = "Up"
    BACK: Final = "Back"
    INSTANT_REPLAY: Final = "InstantReplay"
    REPLAY: Final = "InstantReplay"
    INFO: Final = "Info"
    BACKSPACE: Final = "Backspace"
    SEARCH: Final = "Search"
    ENTER: Final = "Enter"
    FIND_REMOTE: Final = "FindRemote"
    POWER_OFF: Final = "PowerOff"
    POWER_ON: Final = "PowerOn"
    POWER: Final = "Power"
    CHANNEL_UP: Final = "ChannelUp"
    CHANNEL_DOWN: Final = "ChannelDown"
    INPUT_TUNER: Final = "InputTuner"
    INPUT_HDMI1: Final = "InputHDMI1"
    INPUT_HDMI2: Final = "InputHDMI2"
    INPUT_HDMI3: Final = "InputHDMI3"
    INPUT_HDMI4: Final = "InputHDMI4"
    INPUT_AV1: Final = "InputAV1"
    TUNER: Final = "InputTuner"
    HDMI1: Final = "InputHDMI1"
    HDMI2: Final = "InputHDMI2"
    HDMI3: Final = "InputHDMI3"
    HDMI4: Final = "InputHDMI4"
    AV1: Final = "InputAV1"

class ECPEvent[T]:
    def __init__(self, name: str, ecp: ECP2) -> None:
        self._name: str = name
        self._instance: ECP2 = ecp
        self._listeners: dict[int, Callable[[T], Awaitable[None]]] = {}
    async def emit(self, id: int, event_name: str, params: T) -> None:
        tasks: list[asyncio.Task] = []
        for listener in self._listeners.values():
            tasks.append(asyncio.create_task(listener(self._instance, event_name, params)))
        await asyncio.gather(*tasks)
        self._instance._event_responders.pop(id)
    def add_listener(self, listener: Callable[[T], Awaitable[None]]) -> None:
        ref: int = id(listener)
        if ref not in self._listeners:
            self._listeners[ref] = listener
        else:
            raise ValueError(f"Callable '{listener}' already listening to '{self._name}'.")
    def remove_listener(self, listener: Callable[[T], Awaitable[None]]) -> None:
        ref: int = id(listener)
        if ref in self._listeners:
            del self._listeners[ref]
        else:
            raise ValueError(f"Callable '{listener}' not listening to '{name}'.")

@dataclass(frozen=True)
class Asset:
    data: bytes
    mime: str
@dataclass(frozen=True)
class DeviceManufacturer:
    name: str
    url: str
@dataclass(frozen=True)
class DeviceModel:
    name: str
    description: str
    number: str
    url: str
@dataclass(frozen=True)
class DeviceScan:
    device_type: str
    friendly_name: str
    manufacturer: DeviceManufacturer
    model: DeviceModel
    serial: str
    udn: str
    icons: list[Asset]

def _xml_remove_namespace(ele: ET):
    if '}' in ele.tag:
        ele.tag = ele.tag.split('}', 1)[1]
    for child in ele:
        _xml_remove_namespace(child)

async def scan_host(host: str, port: int) -> DeviceScan:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{host}:{port}/") as response:
            if response.status != 200:
                raise ECPError(f"Metadata scan HTTP request failed: {response.status}")
            xml: str = await response.text()
            tree: ET = ET.fromstring(xml)
            _xml_remove_namespace(tree)
            tree = tree.find("device")
            icons: list[Asset] = []
            for xml_icon in tree.find("iconList"):
                path: str = xml_icon.find("url").text
                url: str = f"http://{host}:{port}/{path}"
                async with session.get(url) as icon_response:
                    if icon_response.status != 200:
                        raise ECPError(f"HTTP request for icon at '{url}' failed: {response.status}")
                    icon_data: bytes = await icon_response.read()
                icons.append(Asset(
                    data = icon_data,
                    mime = xml_icon.find("mimetype").text
                ))
            return DeviceScan(
                device_type = tree.find("deviceType").text,
            	friendly_name = tree.find("friendlyName").text,
            	manufacturer = DeviceManufacturer(
                    name = tree.find("manufacturer").text,
                    url = tree.find("manufacturerURL").text
            	),
            	model = DeviceModel(
            	    name = tree.find("modelName").text,
            	    description = tree.find("modelDescription").text,
                    number = tree.find("modelNumber").text,
                    url = tree.find("modelURL").text
            	),
            	serial = tree.find("serialNumber").text,
            	udn = tree.find("UDN").text,
            	icons = icons
            )

@dataclass(frozen=True)
class DeviceInfo:
    udn: str
    virtual_device_id: str
    serial_number: str
    device_id: str
    advertising_id: str
    user_profile_type: str
    vendor_name: str
    model_name: str
    model_number: str
    model_region: str
    is_tv: bool
    is_stick: bool
    screen_size: str
    mobile_remote_style: str
    mobile_has_live_tv: bool
    ui_resolution: str
    tuner_type: str
    supports_ethernet: str
    wifi_mac: str
    wifi_driver: str
    ethernet_mac: str
    network_type: str
    network_name: str
    friendly_device_name: str
    friendly_model_name: str
    default_device_name: str
    user_device_name: str
    user_device_location: str
    build_number: str
    software_version: str
    software_build: int
    ui_build_number: str
    ui_software_version: str
    ui_software_build: int
    secure_device: bool
    ecp_setting_mode: str
    language: str
    country: str
    locale: str
    closed_caption_mode: str
    time_zone_auto: str
    time_zone: str
    time_zone_name: str
    time_zone_tz: str
    time_zone_offset: int
    clock_format: str
    uptime: int
    power_mode: str
    supports_suspend: bool
    supports_find_remote: bool
    find_remote_is_possible: bool
    supports_audio_guide: bool
    supports_rva: bool
    has_hands_free_voice_remote: bool
    developer_enabled: bool
    device_automation_bridge_enabled: bool
    search_enabled: bool
    search_channels_enabled: bool
    voice_search_enabled: bool
    supports_private_listening: bool
    private_listening_blocked: bool
    supports_warm_standby: bool
    headphones_connected: bool
    supports_audio_settings: bool
    expert_pq_enabled: str
    supports_ecs_textedit: bool
    supports_ecs_microphone: bool
    supports_wake_on_wlan: bool
    supports_airplay: bool
    has_play_on_roku: bool
    has_mobile_screensaver: bool
    support_url: str
    grandcentral_version: str
    supports_trc: bool
    av_sync_calibration_enabled: str

def str_to_bool(string: str) -> bool:
    string = string.strip().lower()
    if string == "false":
        return False
    elif string == "true":
        return True
    else:
        raise ValueError(f"Boolean must be 'true' or 'false', not '{string}'.")
def flat_tree_to_dataclass[T](tree: ET, clazz: type[T]) -> T:
    args: dict[str, object] = {}
    for field in clazz.__dataclass_fields__.values():
        node: ET = tree.find(field.name)
        if node is None:
            node = tree.find(field.name.replace("_", "-"))
        if node is None:
            raise NameError(f"Field name '{field.name}' could not be found in tree.")
        raw_data: str = node.text.strip()
        value: object
        if field.type == int or field.type == "int":
            value = int(raw_data)
        elif field.type == float or field.type == "float":
            value = float(raw_data)
        elif field.type == bool or field.type == "bool":
            value = str_to_bool(raw_data)
        elif field.type == str or field.type == "str":
            value = raw_data
        else:
            raise TypeError(f"Unsupported type in dataclass: '{field.type}'.")
        args[field.name] = value
    return clazz(**args)

@dataclass(frozen=True)
class AudioDeviceState:
    muted: bool
    volume: int
    destinations: list[str]
@dataclass(frozen=True)
class AudioInfo:
    capabilities: list[str]
    global_audio: AudioDeviceState
    destinations: dict[str, AudioDeviceState]

@dataclass(frozen=True)
class App:
    id: str
    type: str
    subtype: str | None
    version: str
    name: str
    instance: ECP2 | None

    async def launch(self) -> None:
        if instance is None:
            raise ValueError("No attached ECP instance.")
        await self.instance.launch_app(self.id)

@dataclass(frozen=True)
class ECPResponse:
    status: int
    message: str
    opcode: str
    request_id: str
    response: dict[str, object]
    request: ECPRequest

    @property
    def params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        for key in self.response:
            if key.startswith("param-"):
                params[key[6:]] = self.response[key]
        return params
    @property
    def content(self) -> bytes:
        if "content-data" not in self.response:
            raise ValueError("No content in response.")
        return base64.b64decode(self.response["content-data"])
    @property
    def content_type(self) -> str:
        if "content-data" not in self.response:
            raise ValueError("No content in response.")
        return self.response["content-type"]

class ECPRequest:
    def __init__(self, opcode: str, request_id: str, request: dict[str, object]):
        self._opcode: str = opcode
        self._request_id: str = request_id
        self._request: dict[str, object] = request
        self._response: asyncio.Future[ECPResponse] = asyncio.Future()

    def is_complete(self) -> bool:
        return self._response.done()
    @property
    def response(self) -> asyncio.Future[ECPResponse]:
        return self._response
    @property
    def request(self) -> dict[str, object]:
        return self._request
    @property
    def opcode(self) -> str:
        return self._opcode
    @property
    def request_id(self):
        return self._request_id

class ECP2:
    # Credit to @attain-squiggly-zeppelin from https://github.com/home-assistant/core/issues/83819
    # I don't have much experience with APK decompilation so I couldn't have done this without you
    # Interestingly since building this I've also found https://scottdriggers.com/blog/how-i-built-roam/,
    # which references code that stores a different UUID and transforms it, so the technique may be more
    # well-known than previously thought
    # This blog post actually follows a similar process to how I created this library, so check it out
    # if you're interested.
    CHALLENGE_KEY: str = "F3A278B8-1C6F-44A9-9D89-F1979CA4C6F1"
    KNOWN_EVENTS: list[str] = [
        # 'all' listens for all events
        "all",
        "audio-output-property-changed",
        "language-changed",
        "language-changing",
        "leftnav-items-changed",
        "media-player-state-changed",
        "plugin-ui-run",
        "plugin-ui-run-script",
        "plugin-ui-suspended",
        "plugin-ui-exit",
        "screensaver-run",
        "screensaver-exit",
        "plugins-changed",
        "sync-all-completed",
        "sync-all-started",
        "sync-completed",
        "power-mode-changed",
        "volume-changed",
        "tvinput-ui-run",
        "tvinput-ui-exit",
        "tv-channel-changed",
        "textedit-opened",
        "textedit-changed",
        "textedit-closed",
        "ecs-microphone-start",
        "ecs-microphone-stop",
        "device-name-changed",
        "device-location-changed",
        "unified-device-config-updated",
        "user-profile-changed",
        "tv-power-volume-control-changed",
        "audio-setting-changed",
        "audio-settings-invalidated"
    ]

    def __init__(self, host: str, port: int, friendly_name: str = "ECPlib", scan: DeviceScan | None = None) -> None:
        self._friendly_name: str = friendly_name
        self._host: str = host
        self._port: int = port
        self._scan: DeviceScan | None = scan
        self._ws: websockets.ClientConnection | None = None
        self._counter: int = 1
        self._request_queue: dict[str, ECPRequest] = {}
        self._recv_task: asyncio.Task | None = None
        self._events: dict[str, ECPEvent] = {}
        # This lets us know what to immediately listen for
        self._decorated_listeners: set[str] = set()
        self._event_responders: dict[int, asyncio.Task] = {}
        self._event_number: int = 0
        #for name in ECP2.KNOWN_EVENTS:
        #    self._events[name] = ECPEvent(name)

    # Close connection down and reset
    # Theoretically allows the instance
    # to work again
    async def close(self):
        await self._ws.close()
        self._ws = None
        self._recv_task.cancel()
        for event in self._event_responders.values():
            event.cancel()
        self._event_responders.clear()
        self._event_number = 0
        self._counter = 1
        for request in self._request_queue.values():
            request.response.cancel()
        self._request_queue.clear()

    async def _recv(self) -> dict[str, object]:
        return json.loads(await self._ws.recv())
    async def _send(self, data: dict[str, object]) -> None:
        if self._ws is None:
            raise ECPError("Not connected.")
        await self._ws.send(json.dumps(data))

    def register_event(self, event_name: str):
        def decorator(func):
            if event_name not in self._events:
                self._events[event_name] = ECPEvent(event_name, self)
            self._events[event_name].add_listener(func)
            self._decorated_listeners.add(event_name)
            return func
        return decorator

    # Connect and handshake
    async def connect(self) -> None:
        if self._scan is None:
            self._scan = await scan_host(self._host, self._port)
        self._ws = await websockets.connect(
            f"ws://{self._host}/ecp-session",
            port=self._port,
            additional_headers={
                # I tested on an iOS device, so this traffic
                # will match iOS best if anything
                "Origin": "iOS"
            },
            user_agent_header=None,
            extensions=None,
            compression=None,
            subprotocols=["ecp-2"]
        )
        challenge: dict[str, str] = await self._recv()
        if challenge["notify"] != "authenticate" or "param-challenge" not in challenge:
            raise ValueError("Expected an authentication challenge.")
        completed: str = challenge["param-challenge"] + ECP2.CHALLENGE_KEY
        hashed: bytes = hashlib.sha1(completed.encode()).digest()
        encoded: str = base64.b64encode(hashed).decode()
        response: dict[str, str | int] = {
            "microphone-sample-rates": "1600",
            "response": encoded,
            "client-friendly-name": self._friendly_name,
            "has-microphone": "true"
        }
        # Start the receive loop so requests work
        self._recv_task = asyncio.create_task(self._recv_loop())
        try:
            await self.build_request("authenticate", response)
        except ECPError as e:
            raise ECPError(f"Authentication challenge failed: {e}")
        self._device_info: DeviceInfo
        await self.query_device_info()
        if self._decorated_listeners:
            await self.subscribe_events(self._decorated_listeners)

    async def build_request(self, opcode: str, parameters: dict[str | object]) -> ECPResponse:
        if "request-id" in parameters:
            raise ValueError("Please do not add a request ID to your requests.")
        if "request" in parameters:
            raise ValueError("Please do not add an opcode to your requests.")
        request: dict[str, object] = {}
        for param in parameters:
            value: object = parameters[param]
            value_string: str
            if isinstance(value, dict) or isinstance(value, list):
                value_string = json.dumps(value)
            else:
                value_string = str(value)
            if not param.startswith("param-"):
                request["param-" + param] = value_string
            else:
                request[param] = value_string
        request["request"] = opcode
        rid: str = str(self._counter)
        self._counter += 1
        request["request-id"] = rid
        ecpr: ECPRequest = ECPRequest(opcode, rid, request)
        self._request_queue[rid] = ecpr
        await self._send(ecpr.request)
        return await ecpr.response

    async def _recv_loop(self):
        while True:
            data = await self._recv()
            # This is a response to a request
            if "response" in data:
                rid: str = data["response-id"]
                request: ECPRequest = self._request_queue[rid]
                opcode: str = data["response"]
                if request.opcode != opcode:
                    raise ECPError(f"Mismatching opcodes for request '{rid}': sent '{request.opcode}', got '{opcode}'.")
                status: int = int(data["status"])
                message: str = data["status-msg"]
                if 200 <= status <= 299:
                    request.response.set_result(ECPResponse(
                        status = status,
                        message = message,
                        opcode = opcode,
                        request_id = rid,
                        response = data,
                        request = request
                    ))
                else:
                    request.response.set_exception(ECPError(f"{status}: {message}"))
            elif "notify" in data:
                event_name: str = data["notify"]
                params: dict[str, str] = {}
                for param in data:
                    if param.startswith("param-"):
                        params[param[6:]] = data[param]
                if "all" in self._events:
                    event_task: asyncio.Task = asyncio.create_task(self._events["all"].emit(self._event_number, event_name, params))
                    self._event_responders[self._event_number] = event_task
                    self._event_number += 1
                if event_name not in self._events:
                    # No listener for this event
                    continue
                event_task: asyncio.Task = asyncio.create_task(self._events[event_name].emit(self._event_number, event_name, params))
                self._event_responders[self._event_number] = event_task
                self._event_number += 1

    async def press_button(self, button: str) -> None:
        return await self.build_request("key-press", {"key": button})
    # This can't always launch YouTube to a specific video for some reason, but does work
    async def launch_app(self, app_id: str, params: dict[str, str] = {}) -> None:
        return await self.build_request("launch", {
            "channel-id": app_id,
            "params": params,
            #"mode": "async"
        })
    # Because this sometimes has different behaviour:
    async def launch_app_ecp1(self, app_id: str, params: dict[str, str] = {}) -> None:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"http://{self._host}:{self._port}/launch/{app_id}",
                params=params
            )
    async def subscribe_events(self, events: list[str]) -> None:
        param: str = ",".join("+" + event for event in events)
        return await self.build_request("request-events", {
            "events": param
        })
    async def unsubscribe_events(self, events: list[str]) -> None:
        for event in events:
            if event in self._decorated_listeners:
                raise ValueError("Cannot stop listening to event with listener registered via decorator.")
        param: str = ",".join("-" + event for event in events)
        return await self.build_request("request-events", {
            "events": param
        })
    async def install_app(self, app_id: str, force: bool = False) -> None:
        # Install throws an error if the app exists already
        installed: dict[str, App] = await self.query_apps()
        if str(app_id) in installed:
            raise ECPError(f"'{app_id}' installed already.")
        await self.build_request("install", {
            "channel-id": app_id
        })
        if force:
            # Allow some time for the app to start
            await asyncio.sleep(4)
            await self.press_button("Select")
    async def query_apps(self) -> dict[str, App]:
        apps: dict[str, App] = {}
        response: ECPResponse = await self.build_request("query-apps", {})
        tree: ET = ET.fromstring(response.content.decode())
        for app in tree:
            apps[app.attrib["id"]] = App(
                id = app.attrib["id"],
                type = app.attrib["type"],
                subtype = app.attrib.get("subtype"),
                version = app.attrib["version"],
                name = app.text,
                instance = self
            )
        return apps
    async def query_device_info(self) -> DeviceInfo:
        response: ECPResponse = await self.build_request("query-device-info", {})
        tree: ET = ET.fromstring(response.content.decode())
        info: DeviceInfo = flat_tree_to_dataclass(tree, DeviceInfo)
        self._device_info = info
        return info
    async def query_audio_devices(self) -> AudioInfo:
        response: ECPResponse = await self.build_request("query-audio-device", {})
        tree: ET = ET.fromstring(response.content.decode())
        capabilities: list[str] = tree.find("capabilities").find("all-destinations").text.split(",")
        xml_ga: ET = tree.find("global")
        global_audio: AudioDeviceState = AudioDeviceState(
            volume = int(xml_ga.find("volume").text),
            muted = str_to_bool(xml_ga.find("muted").text),
            destinations = xml_ga.find("destination-list").text.split(",")
        )
        destinations: dict[str, AudioDeviceState] = {}
        for xml_dest in tree.find("destinations"):
            name: str = xml_dest.attrib["name"]
            destinations[name] = AudioDeviceState(
                volume = int(xml_dest.find("volume").text),
                muted = str_to_bool(xml_dest.find("muted").text),
                destinations = [name]
            )
        return AudioInfo(
            capabilities = capabilities,
            global_audio = global_audio,
            destinations = destinations
        )
    async def query_active_app(self) -> App:
        response: ECPResponse = await self.build_request("query-active-app", {})
        tree: ET = ET.fromstring(response.content.decode())
        node: ET = tree.find("app")
        return App(
            name = node.text,
            id = node.attrib["id"],
            type = node.attrib["type"],
            subtype = node.attrib["subtype"],
            version = node.attrib["version"],
            instance = self
        )

    def __repr__(self) -> str:
        if self._scan is None:
            return f"<{self.__class__.__name__} at {self._host}:{self._port}>"
        elif self._ws is None:
            return f"<{self.__class__.__name__} '{self.scan.friendly_name}' ({self.scan.serial}) at {self._host}:{self._port} [DISCONNECTED]>"
        else:
            return f"<{self.__class__.__name__} '{self.scan.friendly_name}' ({self.scan.serial}) at {self._host}:{self._port} [CONNECTED]>"

    @property
    def device_info(self):
        if self._device_info is None:
            raise ECPError("Device is not authenticated yet.")
        return self._device_info
    @property
    def scan(self):
        if self._scan is None:
            raise ECPError("Device has not yet been scanned.")
        return self._scan


class _SSDPListener(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue):
        self._seen: set[str] = set()
        self._queue: asyncio.Queue = queue

    def datagram_received(self, data, addr):
        host: str = addr[0]
        if host in self._seen:
            return
        self._seen.add(host)
        response: dict[str, str] = {}
        try:
            # Skip the 'HTTP/1.1 200 OK' line
            for line in data.decode().split("\n")[1:]:
                header = line.split(":", 1)
                if len(header) == 1:
                    continue # Likely blank line
                response[header[0].strip().lower()] = header[1].strip().lower()
            if response.get("st") != "roku:ecp":
                # This isn't a Roku device
                return
            # This is a Roku, parse address
            if "location" not in response:
                # Missing location header
                return
            location: str = response["location"]
            if not location.startswith("http://"):
                # Malformed location header
                return
            # http://host:port/
            host: str
            port: int
            host, str_port = location[7:].strip("/").split(":", 1)
            port = int(str_port)
            self._queue.put_nowait((host, port))
        except Exception as e:
            raise e

# Used for no timeout
async def _long_wait():
    while True:
        await asyncio.sleep(2**32)

# Send out an SSDP query and return Roku devices as we get them
async def find_devices(timeout: float = 0.0, scan: bool = True):
    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 0))

    result_queue: asyncio.Queue[ECP2] = asyncio.Queue()
    loop: asyncio.EventLoop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _SSDPListener(result_queue),
        sock=sock
    )

    # UDP, so accunt for failure
    for _ in range(3):
        sock.sendto(SSDP_BROADCAST.encode(), SSDP_BROADCAST_ADDR)

    timeout_task: asyncio.Task
    if timeout > 0.0:
        timeout_task = asyncio.create_task(asyncio.sleep(timeout))
    else:
        # Infinite task if no timeout
        timeout_task = asyncio.create_task(_long_wait())
    queue_task: asyncio.Task = asyncio.create_task(result_queue.get())
    # This will run forever with no timeout as time_to_stop will not
    # become True.
    time_to_stop: bool = False
    while not time_to_stop:
        try:
            # Get finished and unfinished tasks
            finished, unfinished = await asyncio.wait(
                (timeout_task, queue_task),
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in finished:
                # Instead of breaking, finish looping over finished
                # tasks in case we have an unprocessed result.
                if task == timeout_task:
                    time_to_stop = True
                else:
                    # Return an ECP instance
                    host: str
                    port: int
                    host, port = task.result()
                    if scan:
                        scan_result: DeviceScan = await scan_host(host, port)
                        yield ECP2(host, port, scan=scan_result)
                    else:
                        yield ECP2(host, port)

            # If the task to grab from the queue is unfinished,
            # break out of the loop. This prevents the else clause
            # from running, which creates a new task to get the next
            # queue item and leaves the last queue item in the void.
            for task in unfinished:
                if task == queue_task:
                    break
            else:
                queue_task = asyncio.create_task(result_queue.get())
        except asyncio.exceptions.CancelledError:
            return




# Rickroll all devices on the network using most of the library's features
if __name__ == "__main__":
    check = input("WARNING! You are about to use all Roku devices on the local network to force play Never Gonna Give You Up by Rick Astley. Users will not be able to stop the video or turn down the volume. Type 'yes' to proceed. ")
    if check.lower().strip() != "yes":
        print("Exitting...")
        exit()

    VIDEO_ID: str = "dQw4w9WgXcQ"
    VOLUME_LEVEL: int = 12
    YOUTUBE_ID: str = "837"

    # This version does not need to care about permissions
    # It pretends to be the mobile app, which can do everything

    async def rickroll_device(ecp: ECP2) -> None:
        # When this is true, we bring back the video if
        # it stops
        video_playing: bool = False

        # Let's register some handlers before we start
        # Can't have the volume going down
        @ecp.register_event("volume-changed")
        async def handle_volume_change(ecp: ECP2, event_name: str, params: dict[str, str]):
            if int(params["volume"]) < VOLUME_LEVEL:
                # This will keep firing events until the volume
                # is at the right level
                print(f"[{ecp.scan.friendly_name}] Volume was at {params['volume']}, increasing.")
                await ecp.press_button(Button.VOLUME_UP)
            if str_to_bool(params["mute"]):
                # Unmute if muted
                print(f"[{ecp.scan.friendly_name}] Muted, unmuting.")
                await ecp.press_button(Button.VOLUME_MUTE)

        @ecp.register_event("power-mode-changed")
        async def power_on(ecp: ECP2, event_name: str, params: dict[str, str]):
            nonlocal video_playing
            if video_playing:
                if params["power-mode"] == "ready":
                    # Give some time to power off
                    await asyncio.sleep(6)
                    await ecp.launch_app_ecp1(YOUTUBE_ID, {
                        "contentId": VIDEO_ID
                    })

        @ecp.register_event("media-player-state-changed")
        async def press_play(ecp: ECP2, event_name: str, params: dict[str, str]):
            nonlocal video_playing
            if video_playing:
                state: str = params["media-player-state"]
                if state == "pause":
                    await asyncio.sleep(0.5)
                    await ecp.press_button(Button.PLAY)
                elif (state == "stop" or state == "close") and "media-player-position" in params:
                    # 'media-player-position' means the video was playing
                    # Without this it just reloads itself at the start of
                    # the video constantly
                    await asyncio.sleep(3)
                    await ecp.launch_app_ecp1(YOUTUBE_ID, {
                        "contentId": VIDEO_ID
                    })

        # Connect and authenticate
        print(f"[{ecp.scan.friendly_name}] Connecting...")
        await ecp.connect()

        # Check apps to see if YouTube is installed
        print(f"[{ecp.scan.friendly_name}] Checking for YouTube...")
        apps: dict[str, App] = await ecp.query_apps()
        if YOUTUBE_ID not in apps:
            print(f"[{ecp.scan.friendly_name}] YouTube not installed, installing...")
            await ecp.install_app(YOUTUBE_ID, force = True)
            print(f"[{ecp.scan.friendly_name}] Waiting for installation to complete...")
            while True:
                if YOUTUBE_ID in await ecp.query_apps():
                    break
            # The installed message still took a moment to pop up even after
            # it was showing up in apps, so out of caution:
            await asyncio.sleep(1)
        print(f"[{ecp.scan.friendly_name}] YouTube installed, we are READY!")
        # So we can restore it
        await ecp.launch_app_ecp1(YOUTUBE_ID, {
            "contentId": VIDEO_ID
        })
        print(f"[{ecp.scan.friendly_name}] Rickroll is imminent.")
        await asyncio.sleep(4)
        video_playing = True
        # Sometimes there's a race condtion where you can mute the TV
        # Let's fix that
        # (about 4min)
        print(f"[{ecp.scan.friendly_name}] Monitoring audio...")
        for i in range(240):
            # Fix the volume if incorrect (VOLUME_LEVEL, unmuted)
            audio_state: AudioInfo = await ecp.query_audio_devices()
            # Either of these trigger the volume change event, which
            # will fully correct the audio
            if audio_state.global_audio.volume < VOLUME_LEVEL:
                await ecp.press_button(Button.VOLUME_UP)
            elif audio_state.global_audio.muted:
                await ecp.press_button(Button.VOLUME_MUTE)
            await asyncio.sleep(1)

    async def main() -> None:
        rickroll_tasks: list[asyncio.Event] = []

        try:
            # This uses an SSDP search to find all compatible devices
            # on the network
            print(f"[controller] Conducting search for compatible devices...")
            async for ecp in find_devices(scan=True):
                # Start a rickroll task asynchronously
                # This will run in the background until we stop
                # the script
                print(f"[controller] Found device: '{ecp.scan.friendly_name}'")
                rickroll_tasks.append(
                    asyncio.create_task(rickroll_device(ecp))
                )
        except KeyboardInterrupt:
            # Stop gathering devices when Ctrl+C is pressed
            # Wait for all rickrolls to finish
            await asyncio.gather(rickroll_tasks)
        print("[controller] Done!")

    asyncio.run(main())
