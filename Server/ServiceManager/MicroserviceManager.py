import json
import os
import uuid
from enum import Enum
import subprocess
from Define import server_config_path, root_path, settings_dir
from pydantic import BaseModel, Field


class Microservice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    status: str  # "start" or "stop"


class SERVICE_STATUS(Enum):
    RUNNING = "running"
    STOPPED = "stopped"


class MicroserviceController:
    def __init__(self, host, name):
        self.host = host
        self.model = Microservice(name=name, status=SERVICE_STATUS.STOPPED.value)

    def get_model(self):
        return self.model

    def ping(self):
        raise NotImplementedError("gRPC microservice is no longer supported.")

    def start(self):
        raise NotImplementedError("gRPC microservice is no longer supported.")

    def stop(self):
        raise NotImplementedError("gRPC microservice is no longer supported.")


# Common constants for mounts (host paths; Docker on Windows accepts forward slashes)
def _host_path(*parts):
    return os.path.join(root_path, *parts).replace("\\", "/")


HOST_LOGS = _host_path("logs")
HOST_SETTINGS = os.path.abspath(settings_dir).replace("\\", "/")
IN_CONTAINER_LOGS_NEW = "/home/ubuntu/fr_bot/logs"
IN_CONTAINER_LOGS_OLD = "/app/logs"
IN_CONTAINER_SETTINGS_NEW = "/home/ubuntu/fr_bot/code/_settings"


class ADLDockerController(MicroserviceController):
    def ping(self):
        try:
            result = subprocess.run([
                "docker", "inspect", "-f", "{{.State.Running}}", "adlcontrol_container"
            ], capture_output=True, text=True)
            running = result.stdout.strip() == "true"
            self.model.status = SERVICE_STATUS.RUNNING.value if running else SERVICE_STATUS.STOPPED.value
            return {"running": running}
        except Exception as e:
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"error": str(e)}

    def start(self):
        try:
            result = subprocess.run([
                "docker", "inspect", "adlcontrol_container"
            ], capture_output=True, text=True)
            need_create = False
            if result.returncode == 0:
                mounts = subprocess.run([
                    "docker", "inspect", "-f", "{{range .Mounts}}{{println .Destination}}{{end}}", "adlcontrol_container"
                ], capture_output=True, text=True)
                destinations = mounts.stdout.strip().splitlines()
                has_logs = (IN_CONTAINER_LOGS_OLD in destinations) or (IN_CONTAINER_LOGS_NEW in destinations)
                has_settings = (IN_CONTAINER_SETTINGS_NEW in destinations)
                if not (has_logs and has_settings):
                    subprocess.run(["docker", "stop", "adlcontrol_container"], check=False)
                    subprocess.run(["docker", "rm", "adlcontrol_container"], check=True)
                    need_create = True
            else:
                need_create = True

            if need_create:
                subprocess.run([
                    "docker", "create",
                    "--name", "adlcontrol_container",
                    "-v", f"{HOST_LOGS}:{IN_CONTAINER_LOGS_NEW}",
                    "-v", f"{HOST_LOGS}:{IN_CONTAINER_LOGS_OLD}",
                    "-v", f"{HOST_SETTINGS}:{IN_CONTAINER_SETTINGS_NEW}",
                    "adlprocess"
                ], check=True)
            subprocess.run(["docker", "start", "adlcontrol_container"], check=True)
            self.model.status = SERVICE_STATUS.RUNNING.value
            return {"success": True}
        except Exception as e:
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"error": str(e)}

    def stop(self):
        try:
            subprocess.run(["docker", "stop", "adlcontrol_container"], check=True)
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}


class AssetDockerController(MicroserviceController):
    def ping(self):
        try:
            result = subprocess.run([
                "docker", "inspect", "-f", "{{.State.Running}}", "assetcontrol_container"
            ], capture_output=True, text=True)
            running = result.stdout.strip() == "true"
            self.model.status = SERVICE_STATUS.RUNNING.value if running else SERVICE_STATUS.STOPPED.value
            return {"running": running}
        except Exception as e:
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"error": str(e)}

    def start(self):
        try:
            result = subprocess.run([
                "docker", "inspect", "assetcontrol_container"
            ], capture_output=True, text=True)
            need_create = False
            if result.returncode == 0:
                mounts = subprocess.run([
                    "docker", "inspect", "-f", "{{range .Mounts}}{{println .Destination}}{{end}}", "assetcontrol_container"
                ], capture_output=True, text=True)
                destinations = mounts.stdout.strip().splitlines()
                has_logs = (IN_CONTAINER_LOGS_OLD in destinations) or (IN_CONTAINER_LOGS_NEW in destinations)
                has_settings = (IN_CONTAINER_SETTINGS_NEW in destinations)
                if not (has_logs and has_settings):
                    subprocess.run(["docker", "stop", "assetcontrol_container"], check=False)
                    subprocess.run(["docker", "rm", "assetcontrol_container"], check=True)
                    need_create = True
            else:
                need_create = True

            if need_create:
                subprocess.run([
                    "docker", "create",
                    "--name", "assetcontrol_container",
                    "-v", f"{HOST_LOGS}:{IN_CONTAINER_LOGS_NEW}",
                    "-v", f"{HOST_LOGS}:{IN_CONTAINER_LOGS_OLD}",
                    "-v", f"{HOST_SETTINGS}:{IN_CONTAINER_SETTINGS_NEW}",
                    "assetprocess"
                ], check=True)
            subprocess.run(["docker", "start", "assetcontrol_container"], check=True)
            self.model.status = SERVICE_STATUS.RUNNING.value
            return {"success": True}
        except Exception as e:
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"error": str(e)}

    def stop(self):
        try:
            subprocess.run(["docker", "stop", "assetcontrol_container"], check=True)
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}


class DiscordDockerController(MicroserviceController):
    def ping(self):
        try:
            result = subprocess.run([
                "docker", "inspect", "-f", "{{.State.Running}}", "discord_shared_container"
            ], capture_output=True, text=True)
            running = result.stdout.strip() == "true"
            self.model.status = SERVICE_STATUS.RUNNING.value if running else SERVICE_STATUS.STOPPED.value
            return {"running": running}
        except Exception as e:
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"error": str(e)}

    def start(self):
        try:
            result = subprocess.run([
                "docker", "inspect", "discord_shared_container"
            ], capture_output=True, text=True)
            need_create = False
            if result.returncode == 0:
                mounts = subprocess.run([
                    "docker", "inspect", "-f", "{{range .Mounts}}{{println .Destination}}{{end}}", "discord_shared_container"
                ], capture_output=True, text=True)
                destinations = mounts.stdout.strip().splitlines()
                has_logs = (IN_CONTAINER_LOGS_OLD in destinations) or (IN_CONTAINER_LOGS_NEW in destinations)
                has_settings = (IN_CONTAINER_SETTINGS_NEW in destinations)
                if not (has_logs and has_settings):
                    subprocess.run(["docker", "stop", "discord_shared_container"], check=False)
                    subprocess.run(["docker", "rm", "discord_shared_container"], check=True)
                    need_create = True
            else:
                need_create = True

            if need_create:
                img = subprocess.run(["docker", "images", "-q", "discord_shared_image"], capture_output=True, text=True)
                if img.returncode != 0 or not img.stdout.strip():
                    build = subprocess.run(["docker", "build", "-f", "Notification/Dockerfile", "-t", "discord_shared_image", "."], capture_output=True, text=True)
                    if build.returncode != 0:
                        return {"error": f"Failed to build discord image: {build.stderr}"}
                create = subprocess.run([
                    "docker", "create",
                    "--name", "discord_shared_container",
                    "-v", f"{HOST_LOGS}:{IN_CONTAINER_LOGS_NEW}",
                    "-v", f"{HOST_LOGS}:{IN_CONTAINER_LOGS_OLD}",
                    "-v", f"{HOST_SETTINGS}:{IN_CONTAINER_SETTINGS_NEW}",
                    "discord_shared_image"
                ], capture_output=True, text=True)
                if create.returncode != 0:
                    return {"error": f"Failed to create container: {create.stderr}"}

            subprocess.run(["docker", "start", "discord_shared_container"], check=True)
            self.model.status = SERVICE_STATUS.RUNNING.value
            return {"success": True}
        except Exception as e:
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"error": str(e)}

    def stop(self):
        try:
            subprocess.run(["docker", "stop", "discord_shared_container"], check=True)
            self.model.status = SERVICE_STATUS.STOPPED.value
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}


class MicroserviceManager:
    def __init__(self):
        self.microservices = []
        self.init_microservice()

    def init_microservice(self):
        with open(server_config_path, "r") as f:
            config = json.load(f)
        for ms in config.get("microservices", []):
            name = ms["name"].lower()
            if name == "adlcontrol":
                self.microservices.append(ADLDockerController(host=ms["host"], name=ms["name"]))
            elif name == "assetcontrol":
                self.microservices.append(AssetDockerController(host=ms["host"], name=ms["name"]))
            elif name == "discord":
                self.microservices.append(DiscordDockerController(host=ms["host"], name=ms["name"]))
            else:
                raise ValueError(f"Unknown microservice name: {name}")

    def get_microservices(self):
        return self.microservices

    def start_microservice(self, service_id):
        for ms in self.microservices:
            if ms.get_model().id == service_id:
                ms.start()
                return True
        return False

    def stop_microservice(self, service_id):
        for ms in self.microservices:
            if ms.get_model().id == service_id:
                ms.stop()
                return True
        return False
