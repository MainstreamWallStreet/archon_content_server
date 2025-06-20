import os
import subprocess
import time
import requests
import base64

API_KEY = os.environ.get("ZERGLING_API_KEY", "test-api-key")
OBJECT_NAME = "test_object.txt"
OBJECT_DATA = b"hello zergling"
UPDATED_DATA = b"updated zergling"
DOCKER_IMAGE = "zergling:latest"
CONTAINER_NAME = "zergling_test"
PORT = 8080

# 1. Build Docker image
def build_image():
    print("Building Docker image...")
    subprocess.run(["docker", "build", "-t", DOCKER_IMAGE, "."], check=True)

# 2. Run Docker container
def run_container():
    print("Starting Docker container...")
    subprocess.run([
        "docker", "run", "-d", "--rm",
        "-e", f"ZERGLING_API_KEY={API_KEY}",
        "-p", f"{PORT}:8080",
        "--name", CONTAINER_NAME,
        DOCKER_IMAGE
    ], check=True)

# 3. Wait for FastAPI to be ready
def wait_for_ready():
    print("Waiting for FastAPI to be ready...")
    url = f"http://localhost:{PORT}/health"
    for _ in range(30):
        try:
            r = requests.get(url)
            if r.status_code == 200:
                print("FastAPI is ready!")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("FastAPI did not become ready in time.")

# 4. Perform CRUD operations
def perform_crud():
    headers = {"X-API-Key": API_KEY}
    base_url = f"http://localhost:{PORT}/objects"
    print("\n--- CREATE ---")
    resp = requests.post(base_url, headers=headers, json={
        "object_name": OBJECT_NAME,
        "data": base64.b64encode(OBJECT_DATA).decode()
    })
    print(resp.status_code, resp.json())

    print("\n--- READ ---")
    resp = requests.get(f"{base_url}/{OBJECT_NAME}", headers=headers)
    print(resp.status_code, resp.json())

    print("\n--- UPDATE ---")
    resp = requests.put(f"{base_url}/{OBJECT_NAME}", headers=headers, json={
        "object_name": OBJECT_NAME,
        "data": base64.b64encode(UPDATED_DATA).decode()
    })
    print(resp.status_code, resp.json())

    print("\n--- DELETE ---")
    resp = requests.delete(f"{base_url}/{OBJECT_NAME}", headers=headers)
    print(resp.status_code, resp.json())

# 5. Cleanup Docker container
def cleanup():
    print("Stopping Docker container...")
    subprocess.run(["docker", "stop", CONTAINER_NAME], check=False)

if __name__ == "__main__":
    try:
        build_image()
        run_container()
        wait_for_ready()
        perform_crud()
    finally:
        cleanup() 