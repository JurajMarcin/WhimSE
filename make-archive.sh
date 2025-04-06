#!/bin/bash

VERSION=`python -c 'import whimse; print(whimse.__version__);'`
ARCHIVE="whimse-$VERSION.tar.gz"

echo "Checking submodules..."

git submodule init
git submodule update

echo "Creating archive $ARCHIVE"

tar czf "$ARCHIVE" --transform "s,^,whimse-$VERSION/," `git ls-files --recurse-submodules`
