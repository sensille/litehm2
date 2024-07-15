#!/bin/bash

docker build -t ise-base -f ise-base.docker .
docker kill ise-installer
docker remove ise-installer
docker run -d --name ise-installer ise-base
IP=`docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ise-installer`
while : ; do
	sleep 1
	ssh -tY -o UserKnownHostsFile=/dev/null -o PubkeyAuthentication=no root@$IP \
		"./Xilinx_ISE_DS_Lin_14.7_1015_1/xsetup && rm -rf Xilinx_ISE_DS_Lin_14.7_1015_1" \
		 && break
done
echo "committing docker image"
docker commit ise-installer ise-installed
docker kill ise-installer
docker remove ise-installer
