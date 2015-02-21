build:
	pip install virtualenv
	virtualenv venv
	venv/bin/pip install -r requirements.txt
	venv/bin/pip install -e .

test:
	venv/bin/python setup.py test

coverage:
	venv/bin/python setup.py test --cov
	
package:
	

clean:
	@rm -rf .Python MANIFEST build dist venv* *.egg-info *.egg
	@find . -type f -name "*.py[co]" -delete
	@find . -type d -name "__pycache__" -delete

.PHONY: build clean coverage test