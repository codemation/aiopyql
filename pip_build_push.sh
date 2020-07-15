#!/bin/bash
sudo rm -rf build/
sed -i 's/0.1/'$1'/g' setup.py 
python setup.py bdist_wheel
python -m twine upload dist/aiopyql-$1-py3-none-any.whl
sed -i 's/0.1/'$1'/g' pip_build_push.sh