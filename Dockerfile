FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

ENV HERO_API_KEY=""
ENV MCP_TRANSPORT=sse
ENV MCP_API_KEY=""
ENV PORT=8000

EXPOSE 8000

CMD ["hero-mcp-server"]
