import requests

URL = "https://raven-api-gl7hc5q6rq-uc.a.run.app/health"


def test_health() -> bool:
    """Ping the deployed API health endpoint."""

    try:
        response = requests.get(URL, timeout=5)
        response.raise_for_status()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return True
    except requests.exceptions.RequestException as exc:
        print(f"Error: {exc}")
        return False


if __name__ == "__main__":
    print("Testing Raven API health endpoint...")
    success = test_health()
    print(f"\nTest {'passed' if success else 'failed'}")
