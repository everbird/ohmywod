PYTHON_VERSION ?= 3.9.13

# Determine python executable to use for venv creation
# If pyenv is available, use the specified PYTHON_VERSION
PYENV_ROOT = $(shell pyenv root 2>/dev/null || echo "$$HOME/.pyenv")
PYENV_PYTHON = $(PYENV_ROOT)/versions/$(PYTHON_VERSION)/bin/python
PYTHON = $(shell if [ -x $(PYENV_PYTHON) ]; then echo $(PYENV_PYTHON); else echo "python3"; fi)

SUPERVISOR_CONF = supervisord.conf
SUPERVISORD = .venv/bin/supervisord
SUPERVISORCTL = .venv/bin/supervisorctl

.PHONY: all help clean clean_pyc clean_tmp requirements generate init_db start stop restart status log-web log-store log-cache install-deps ensure-pyenv-python .venv

all: install-deps ensure-pyenv-python init_db start

help:
	@echo "Available targets:"
	@echo "  all              - Install system dependencies, setup pyenv/venv, init DB, and start all services"
	@echo "  install-deps     - Install system dependencies (redis-server, etc.)"
	@echo "  generate         - Generate local configuration files"
	@echo "  init_db          - Initialize sqlite database"
	@echo "  start            - Start supervisord (app + redis dependency services)"
	@echo "  stop             - Stop supervisord and all controlled services"
	@echo "  restart          - Restart the Flask web application"
	@echo "  status           - View status of services"
	@echo "  log-web          - Tail Flask web application logs"
	@echo "  log-store        - Tail redis-store logs"
	@echo "  log-cache        - Tail redis-cache logs"
	@echo "  clean            - Clean python bytecodes and swap files"

clean: clean_pyc clean_tmp
	@#@find -regex ".*\.\(pyc\|swp\|un\~\)" | xargs rm -rf

clean_pyc:
	@find `pwd` -name '*.pyc' -type f -delete

clean_tmp:
	@find `pwd` \( -name '*.swp' -o -name '*.un~' \) -type f -delete

requirements:
	.venv/bin/pip install -r ./requirements.txt

install-deps:
	@echo "Checking system dependencies..."
	@if ! which redis-server >/dev/null; then \
		echo "Installing redis-server..."; \
		sudo apt-get update && sudo apt-get install -y redis-server; \
	fi
	@if ! which python3 >/dev/null; then \
		echo "Installing python3..."; \
		sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-dev build-essential curl git; \
	fi

ensure-pyenv-python:
	@if [ -x $(PYENV_PYTHON) ]; then \
		echo "Python $(PYTHON_VERSION) is already installed via pyenv."; \
	else \
		if which pyenv >/dev/null; then \
			echo "Installing Python $(PYTHON_VERSION) via pyenv..."; \
			pyenv install -s $(PYTHON_VERSION); \
		else \
			echo "pyenv is not installed. Falling back to system python3."; \
		fi \
	fi

.venv:
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment using $(PYTHON)..."; \
		$(PYTHON) -m venv .venv; \
		.venv/bin/pip install --upgrade pip; \
		.venv/bin/pip install -r requirements.txt; \
		.venv/bin/pip install supervisor Flask-Admin "werkzeug<3.0.0"; \
	fi

generate: .venv
	@mkdir -p .data/report .data/upload
	@mkdir -p /tmp/var/ohmywod/run /tmp/var/ohmywod/log
	@mkdir -p /tmp/data/ohmywod/redis/cache /tmp/data/ohmywod/redis/store
	.venv/bin/python gen.py devel

init_db: generate
	.venv/bin/flask --app deploy.py init_db

start: generate
	@if [ -f /tmp/var/ohmywod/run/supervisord.pid ]; then \
		echo "supervisord is already running (PID: `cat /tmp/var/ohmywod/run/supervisord.pid`)"; \
	else \
		$(SUPERVISORD) -c $(SUPERVISOR_CONF); \
		echo "supervisord started."; \
	fi

stop:
	@if [ -f /tmp/var/ohmywod/run/supervisord.pid ]; then \
		$(SUPERVISORCTL) -c $(SUPERVISOR_CONF) shutdown || true; \
		echo "supervisord stopped."; \
	else \
		echo "supervisord is not running."; \
	fi

restart:
	$(SUPERVISORCTL) -c $(SUPERVISOR_CONF) restart web || true

status:
	$(SUPERVISORCTL) -c $(SUPERVISOR_CONF) status || true

log-web:
	tail -n 100 -f /tmp/var/ohmywod/log/supervisord-web-out.log

log-store:
	tail -n 100 -f /tmp/var/ohmywod/log/redis-store-6379.log

log-cache:
	tail -n 100 -f /tmp/var/ohmywod/log/redis-cache-7379.log
