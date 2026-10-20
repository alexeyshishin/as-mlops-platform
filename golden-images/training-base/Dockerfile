FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1
ENV MAKEFLAGS="-j1"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir --no-deps \
    "gigaevo @ git+https://github.com/AIRI-Institute/gigaevo-core.git@9b8687ebaf1708962370ea82b4cf2480d74874e5"

RUN python3 -c "import gigaevo, os; p = os.path.join(os.path.dirname(gigaevo.__file__), 'evolution', 'mutation', 'context.py'); c = open(p).read(); marker = 'MUTATION_CONTEXT_METADATA_KEY = \"mutation_context\"' + chr(10) * 3; assert marker in c, 'gigaevo context.py layout changed, patch needs update'; c = c.replace(marker, '', 1); open(p, 'w').write('MUTATION_CONTEXT_METADATA_KEY = \"mutation_context\"' + chr(10) * 2 + c)"
RUN python3 -c "from gigaevo.evolution.engine.core import EvolutionEngine"
