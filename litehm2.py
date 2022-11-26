#!/usr/bin/env python3

import os
import argparse
import sys

from migen import *
from hostmot2 import *

from litex_boards.platforms import linsn_rv901t

from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.interconnect import wishbone

from liteeth.phy.s6rgmii import LiteEthPHYRGMII
from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litedram.modules import M12L64322A
from litedram.phy import GENSDRPHY
from litex.soc.cores.led import LedChaser
from litespi.modules import W25Q32
from litespi.opcodes import SpiNorFlashOpCodes as Codes
from litescope import LiteScopeAnalyzer
from litespi import LiteSPI
from litespi.phy.generic import LiteSPIPHY
from litespi.opcodes import SpiNorFlashOpCodes

# CRG -------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, fast_clk_freq):
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_fast   = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        # # #

        clk25 = platform.request("clk25")
        platform.add_period_constraint(clk25, 1e9/25e6)

        self.submodules.pll = pll = S6PLL(speedgrade=-2)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_fast, fast_clk_freq)

class LiteHM2(SoCCore):
    def __init__(self, sys_clk_freq=int(40e6), with_etherbone=True,
            ip_address=None, mac_address=None, with_bios=False):

        sys_clk_freq = 100e6
        fast_clk_freq = 200e6
        with_bios = False
        with_ethernet = True
        with_etherbone = False
        with_flash = True
        with_hostmot2 = True
        with_litescope = False
        with_uartbone = False
        with_leds = True

        platform = linsn_rv901t.Platform()

        self.submodules.crg = _CRG(platform, sys_clk_freq, fast_clk_freq)

        if with_bios:
            SoCCore.__init__(self, platform,
                clk_freq = sys_clk_freq,
                #cpu_variant = "lite",
                cpu_variant = "minimal",
                integrated_rom_size = 0x8000,
                integrated_sram_size = 0x1000,
                integrated_main_ram_size = 0x3000,
            )
        else:
            main_ram_init = get_mem_data("firmware/firmware.bin",
                endianness = "little", # FIXME: Depends on CPU.
                data_width = 32,       # FIXME: Depends on CPU.
            )
            SoCCore.__init__(self, platform,
                clk_freq = sys_clk_freq,
                #cpu_variant = "lite",
                cpu_variant = "minimal",
                integrated_rom_size = 0x1000,
                integrated_rom_init = "firmware/loader.bin",
                integrated_sram_size = 0x1000,
                integrated_main_ram_size = 0x4000,
                integrated_main_ram_init = main_ram_init,
            )

        if with_litescope:
            count = Signal(8)
            self.sync += count.eq(count + 1)
            analyzer_signals = [
                self.main_ram.bus,
                count,
            ]
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
                depth        = 1024,
                clock_domain = "sys",
                samplerate   = self.sys_clk_freq,
                csr_csv      = "analyzer.csv")
            self.add_csr("analyzer")

        if with_leds:
            self.submodules.leds = LedChaser(
                pads         = platform.request_all("user_led"),
                sys_clk_freq = sys_clk_freq)

        if with_ethernet or with_etherbone:
            self.submodules.ethphy = LiteEthPHYRGMII(
                clock_pads = self.platform.request("eth_clocks", 0),
                pads       = self.platform.request("eth", 0),
                tx_delay   = 0e-9)

        if with_ethernet:
            self.add_ethernet(
                phy         = self.ethphy,
                data_width  = 32,
                ntxslots    = 2,
                nrxslots    = 8,
                with_timestamp = True,
            )
        if with_etherbone:
            self.add_etherbone(
                 phy         = self.ethphy,
                 ip_address  = ip_address,
                 mac_address = mac_address,
                 data_width  = 32,
            )

        if with_flash:
            self.add_spi_flash(mode="1x", module=W25Q32(Codes.READ_1_1_1),
                clk_freq=50e6)

        if with_uartbone:
            self.add_uartbone(name = "serial", baudrate=115200)

        if with_hostmot2:
            self.submodules.hostmot2 = hostmot2 = HostMot2(self,
                sys_clk_freq, fast_clk_freq, with_leds)

# Build ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=
        "Take control of your ColorLight FPGA board with LiteX/LiteEth :)")
    parser.add_argument("--build", action="store_true", help="Build bitstream")
    parser.add_argument("--load", action="store_true", help="Load bitstream")
    parser.add_argument("--flash",action="store_true", help="Flash bitstream")
    parser.add_argument("--ip-address", default="10.10.10.10",
        help="Ethernet IP address of the board (default: 10.10.10.10).")
    parser.add_argument("--mac-address", default="0x726b895bc2e2",
        help="Ethernet MAC address of the board (defaullt: 0x726b895bc2e2).")
    args = parser.parse_args()

    soc = LiteHM2(ip_address=args.ip_address,
        mac_address=int(args.mac_address, 0))
    builder = Builder(soc, output_dir="build", csr_csv="scripts/csr.csv")
    builder.build(build_name="litehm2", run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir,
            soc.build_name + ".svf"))

    if args.flash:
        prog = soc.platform.create_programmer()
        os.system("cp bit_to_flash.py build/gateware/")
        os.system("cd build/gateware && ./bit_to_flash.py litehm2.bit " +
            "litehm2.svf.flash")
        prog.load_bitstream(os.path.join(builder.gateware_dir,
            soc.build_name + ".svf.flash"))

if __name__ == "__main__":
    main()
