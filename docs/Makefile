# Documentation Root Makefile
# Delegates all commands to src/Makefile

.PHONY: help lint lint-fast format format-check eslint install

# Default target
help:
	@$(MAKE) -C src help

# Delegate all targets to src/Makefile
lint:
	@$(MAKE) -C src lint

lint-fast:
	@$(MAKE) -C src lint-fast

format:
	@$(MAKE) -C src format

format-check:
	@$(MAKE) -C src format-check

eslint:
	@$(MAKE) -C src eslint

install:
	@$(MAKE) -C src install

