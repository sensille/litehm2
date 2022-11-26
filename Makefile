all: litehm2

litehm2:
	./litehm2.py
	(cd firmware; make)
	./litehm2.py
	(cd build/gateware; \
	 sed -i -e 's/eth_tx_clk/eth_rx_clk/g' litehm2.ucf; \
	 sh build_litehm2.sh )
	cp build/gateware/litehm2.bit bitstreams/
	cp build/gateware/litehm2.bin bitstreams/
