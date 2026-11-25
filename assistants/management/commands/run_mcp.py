import uvicorn
from django.core.management.base import BaseCommand

from assistants.server import build_app


class Command(BaseCommand):
    help = "Run the MCP server for AI assistants (streamable HTTP at /mcp)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8001)

    def handle(self, *args, host, port, **options):
        uvicorn.run(build_app(), host=host, port=port, log_level="info")
