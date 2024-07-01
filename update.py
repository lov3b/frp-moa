#!/usr/bin/env python3
import os
import shutil
import re
import requests
import tarfile
import logging
from typing import Optional, TypedDict, List
from packaging import version

GITHUB_REPO = "fatedier/frp"
LOCAL_VERSION_FILE = "local_version.txt"
DOWNLOAD_DIR = "temp"
EXTRACT_DIR = "frp"
ARCHIVE_NAME_PATTERN = r"frp_(\d+\.\d+\.\d+)_linux_amd64\.tar\.gz"


logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger()


os.makedirs(EXTRACT_DIR, exist_ok=True)


class Asset(TypedDict):
    name: str
    browser_download_url: str


class ReleaseInfo(TypedDict):
    tag_name: str
    assets: List[Asset]


def get_latest_release_info(repo: str) -> ReleaseInfo:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def read_local_version(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r") as f:
        return f.read().strip()


def write_local_version(file_path: str, version: str) -> None:
    with open(file_path, "w") as f:
        f.write(version)


def download_file(url: str, local_path: str) -> None:
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def extract_tar_gz(file_path: str, extract_to: str) -> None:
    with tarfile.open(file_path, "r:gz") as tar:
        temp_extract_dir = os.path.join(extract_to, "temp")
        os.makedirs(temp_extract_dir, exist_ok=True)
        tar.extractall(path=temp_extract_dir, filter=lambda tarinfo, *_: tarinfo)

        for member in os.listdir(temp_extract_dir):
            member_path = os.path.join(temp_extract_dir, member)
            if os.path.isdir(member_path):
                for item in os.listdir(member_path):
                    os.rename(
                        os.path.join(member_path, item), os.path.join(extract_to, item)
                    )
                os.rmdir(member_path)

        os.rmdir(temp_extract_dir)


def find_asset_url(assets: List[Asset]) -> Optional[str]:
    for asset in assets:
        if re.match(ARCHIVE_NAME_PATTERN, asset["name"]):
            return asset["browser_download_url"]
    return None


def main() -> None:
    latest_release_info = get_latest_release_info(GITHUB_REPO)
    latest_version = latest_release_info["tag_name"]
    asset_url = find_asset_url(latest_release_info["assets"])

    if asset_url is None:
        logging.error("No matching asset found.")
        return

    local_version = read_local_version(LOCAL_VERSION_FILE)

    if local_version is not None and version.parse(local_version) > version.parse(
        latest_version
    ):
        logging.info("No new version available")
        return
    logging.info(f"New version available: {latest_version}")
    download_path = os.path.join(DOWNLOAD_DIR, os.path.basename(asset_url))

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    logging.info(f"Downloading {asset_url} to {download_path}")
    download_file(asset_url, download_path)

    logging.info(f"Extracting {download_path} to {EXTRACT_DIR}")
    extract_tar_gz(download_path, EXTRACT_DIR)

    temp_extract_dir = f"{EXTRACT_DIR}-temp"
    os.makedirs(temp_extract_dir, exist_ok=True)
    extract_tar_gz(download_path, temp_extract_dir)

    if os.path.exists(EXTRACT_DIR):
        logging.info(f"Removing existing directory {EXTRACT_DIR}")
        shutil.rmtree(EXTRACT_DIR)

    logging.info(f"Renaming {temp_extract_dir} to {EXTRACT_DIR}")
    os.rename(temp_extract_dir, EXTRACT_DIR)

    logging.info(f"Updating local version to {latest_version}")
    write_local_version(LOCAL_VERSION_FILE, latest_version)

    shutil.rmtree(DOWNLOAD_DIR)
    logging.info("Update complete.")


if __name__ == "__main__":
    main()
