#!/bin/bash
# Convenience script to run dpai_sds_gen with Vertex AI environment

# Load virtual environment (adjust path as needed)
# source venv_1/bin/activate

# Set Vertex AI environment variables
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-dp-experimental}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
export GOOGLE_GENAI_USE_VERTEXAI=true

# Load .env file if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Run the CLI
python -m src.cli.main "$@"
