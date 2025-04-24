import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from utils.config import API_BASE_URL

def health_check():
    """Ping the API to make sure it’s up."""
    resp = requests.get(f"{API_BASE_URL}/health", verify=False)
    return resp.json()

def get_drawings():
    """Fetch the list of available drawings you can analyze."""
    resp = requests.get(f"{API_BASE_URL}/drawings", verify=False)
    data = resp.json()
    return data.get("drawings", [])

def upload_drawing(file_path):
    """Upload a PDF file for processing."""
    with open(file_path, "rb") as f:
        files = {"file": f}
        resp = requests.post(f"{API_BASE_URL}/upload", files=files, verify=False)
    return resp.json()

def start_analysis(query, drawings, use_cache=True):
    """Kick off a new analysis job; returns the job ID."""
    payload = {
        "query": query,
        "drawings": drawings,
        "use_cache": use_cache
    }
    resp = requests.post(f"{API_BASE_URL}/analyze", json=payload, verify=False)
    return resp.json()

def get_job_status(job_id):
    """Check on a running job’s status and progress."""
    resp = requests.get(f"{API_BASE_URL}/job-status/{job_id}", verify=False)
    return resp.json()
