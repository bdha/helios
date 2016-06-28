#!/usr/bin/ksh

set -e
SHA=`git rev-parse --short HEAD`

rm -rf dist
rm -rf scratch
platter build -p python3.5 .
FILE=`find dist -name Helios\*.tar.gz`
mkdir scratch
tar -C scratch -xf $FILE
INSTALL_SH=`find scratch -name install.sh`
INSTALL_DIR=`dirname $INSTALL_SH`
cd $INSTALL_DIR
PWD=`pwd`
INSTALL_ROOT=`dirname $PWD`
./install.sh $INSTALL_ROOT/helios-$SHA
cd $INSTALL_ROOT/helios-$SHA
echo $INSTALL_ROOT/helios-$SHA
REWRITE_PATH="$INSTALL_ROOT/helios-$SHA"
echo $REWRITE_PATH
## rewrite the scratch path in the files to the actual install path
find . -type f | xargs perl -p -i -e "s^$REWRITE_PATH^/opt/helium/helios/helios-$SHA^g"
cp -r ../../helios $REWRITE_PATH
cd ..
tar -cf ../helios-$SHA-sunos.tgz helios-$SHA

echo helios-$SHA-sunos.tgz
