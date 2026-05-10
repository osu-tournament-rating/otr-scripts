from pathlib import Path

import google.auth as gcp_auth
import google.cloud.storage as gcs

def ensure_auth():
    key_path = Path('./gcp_secrets')
    gcp_auth.