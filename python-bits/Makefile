.PHONY: ensure_env deps clean

all: deps run

deps: env requirements.txt
	@env/bin/pip install -r requirements.txt

env:
	@virtualenv env

run:
	@./env/bin/python example.py

clean:
	@rm -rf env
