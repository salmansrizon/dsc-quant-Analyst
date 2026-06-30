from unittest.mock import MagicMock, patch

# Patch bigquery.Client before any test modules import backend code.
# This prevents "DefaultCredentialsError" when the module-level
# `bq = bigquery.Client(project=PROJECT)` lines execute at import time.
# Tests that need real BigQuery behaviour must mock bq_service functions directly.
_bq_client_patcher = patch("google.cloud.bigquery.Client", return_value=MagicMock())
_bq_client_patcher.start()
