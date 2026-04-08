"""FastAPI application for the banking chargeback operations environment."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import ChargebackAction, ChargebackObservation
    from .chargeback_environment import ChargebackOpsEnvironment
    from .web_ui import build_chargeback_gradio_app
except ImportError:
    from models import ChargebackAction, ChargebackObservation
    from server.chargeback_environment import ChargebackOpsEnvironment
    from server.web_ui import build_chargeback_gradio_app


app = create_app(
    ChargebackOpsEnvironment,
    ChargebackAction,
    ChargebackObservation,
    env_name="bankops-chargeback",
    max_concurrent_envs=4,
    gradio_builder=build_chargeback_gradio_app,
)


def main(host: str = "0.0.0.0", port: int = 8000):
    """Entry point for running the environment locally."""

    import os
    import uvicorn

    port = int(os.environ.get("PORT", port))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
