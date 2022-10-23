.PHONY: help

help:
	@echo targets: version, clean, clean_pyc, clean_tmp

clean: clean_pyc clean_tmp
	@#@find -regex ".*\.\(pyc\|swp\|un\~\)" | xargs rm -rf

clean_pyc:
	@find `pwd` -name '*.pyc' -type f -delete

clean_tmp:
	@find `pwd` \( -name '*.swp' -o -name '*.un~' \) -type f -delete

requirements:
	pip install -r ./requirements.txt
