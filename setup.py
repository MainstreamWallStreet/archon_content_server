from setuptools import setup, find_packages

setup(
    name="raven",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-auth-oauthlib",
        "google-auth",
        "google-api-python-client",
        "google-cloud-storage",
        "requests",
        "beautifulsoup4",
        "sec-edgar-api",
    ],
    python_requires=">=3.11",
)
