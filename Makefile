all: litehm2 bitstreams/initial.bin

litehm2: scripts
	dd if=/dev/zero of=firmware/firmware.bin bs=32k count=1
	dd if=/dev/zero of=firmware/loader.bin bs=4k count=1
	./litehm2.py
	(cd firmware; make)
	./litehm2.py
	(cd build/gateware; \
	 sed -i -e 's/eth_tx_clk/eth_rx_clk/g' litehm2.ucf; \
	 sh build_litehm2.sh )
	cp build/gateware/litehm2.bit bitstreams/
	cp build/gateware/litehm2.bin bitstreams/

scripts:
	mkdir scripts

bitstreams/initial.bin: bitstreams/litehm2.bin
	dd if=/dev/zero of=bitstreams/initial.bin bs=4M count=1
	dd if=bitstreams/litehm2.bin of=bitstreams/initial.bin conv=notrunc
