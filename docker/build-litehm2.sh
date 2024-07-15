#!/bin/bash

set -e

docker build --no-cache -t litehm2 -f litehm2.docker .
docker run -it --mount type=bind,source=$(pwd)/..,target=/home/me/litehm2 litehm2
