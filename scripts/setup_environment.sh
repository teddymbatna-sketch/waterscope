#!/usr/bin/env bash
# WaterScope - installation automatique de l'environnement (US1.1)
# Usage, depuis la racine du projet, sous Linux ou WSL :
#   bash scripts/setup_environment.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
ES_URL="http://localhost:9200"
MAX_WAIT_SECONDS=180

log()  { echo "[setup] $*"; }
fail() { echo "[setup] ERREUR : $*" >&2; exit 1; }
trap 'echo "[setup] ERREUR inattendue a la ligne $LINENO" >&2' ERR

is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

# T1.1.1 - Docker et Docker Compose
install_docker() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        log "Docker et Docker Compose deja installes"
        return
    fi
    if is_wsl; then
        fail "Docker introuvable dans WSL : ouvre Docker Desktop > Settings > Resources > WSL integration, active Ubuntu"
    fi
    log "Installation de Docker et Docker Compose (mot de passe sudo demande)..."
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose-v2
    sudo usermod -aG docker "$USER"
    log "Docker installe. En cas de 'permission denied', deconnecte-toi puis relance ce script."
}

# Dossiers et fichier .env
prepare_files() {
    mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs" "$PROJECT_DIR/config"
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        log ".env cree depuis .env.example : remplis tes identifiants Copernicus"
    else
        log ".env deja present"
    fi
}

# T1.1.2 - Elasticsearch et Kibana
start_stack() {
    docker info >/dev/null 2>&1 || fail "Docker ne repond pas : lance Docker Desktop, puis relance ce script"
    log "Demarrage d'Elasticsearch et Kibana..."
    docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d

    log "Attente d'Elasticsearch (jusqu'a ${MAX_WAIT_SECONDS} s)..."
    local waited=0
    until curl -s "$ES_URL" >/dev/null; do
        if [ "$waited" -ge "$MAX_WAIT_SECONDS" ]; then
            fail "Elasticsearch ne repond pas. Voir : docker compose logs elasticsearch"
        fi
        sleep 5
        waited=$((waited + 5))
    done

    local status
    status=$(curl -s "$ES_URL/_cluster/health" | grep -o '"status":"[a-z]*"' | cut -d'"' -f4 || true)
    log "Elasticsearch pret (statut : ${status:-inconnu})"
}

# T1.1.3 - Environnement Python
setup_python() {
    command -v python3 >/dev/null 2>&1 || fail "python3 introuvable : sudo apt-get install -y python3"
    if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
        log "Installation du module venv (mot de passe sudo demande)..."
        sudo apt-get update
        sudo apt-get install -y python3-venv
    fi
    if [ ! -d "$VENV_DIR" ]; then
        log "Creation de l'environnement virtuel .venv..."
        python3 -m venv "$VENV_DIR"
    fi
    log "Installation des dependances Python..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
    "$VENV_DIR/bin/pip" install --quiet -e "$PROJECT_DIR"
}

run_tests() {
    log "Lancement des tests..."
    (cd "$PROJECT_DIR" && "$VENV_DIR/bin/pytest" -q)
}

main() {
    log "Installation de l'environnement WaterScope"
    install_docker
    prepare_files
    start_stack
    setup_python
    run_tests
    log "Termine !"
    log "  Kibana         : http://localhost:5601"
    log "  Elasticsearch  : $ES_URL"
    log "  Activer Python : source .venv/bin/activate"
}

main "$@"