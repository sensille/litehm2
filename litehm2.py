#!/usr/bin/env python3

import os
import argparse
import sys

from migen import *
from hostmot2 import *

from litex.gen import *

from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.interconnect import wishbone

from litex.build.generic_platform import *
from litedram.phy import GENSDRPHY
from litex.soc.cores.led import LedChaser
from litespi.modules import W25Q32
from litespi.opcodes import SpiNorFlashOpCodes as Codes
from litescope import LiteScopeAnalyzer
from litespi import LiteSPI
from litespi.phy.generic import LiteSPIPHY
from litespi.opcodes import SpiNorFlashOpCodes

# CRG -------------------------------------------------------------------------

class _CRG_rv901t(Module):
    def __init__(self, platform, sys_clk_freq, fast_clk_freq):
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_fast   = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        clk25 = platform.request("clk25")
        platform.add_period_constraint(clk25, 1e9/25e6)

        self.submodules.pll = pll = S6PLL(speedgrade=-2)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_fast, fast_clk_freq)
        platform.add_false_path_constraint(self.cd_sys.clk, self.cd_fast.clk)
        platform.add_false_path_constraint(self.cd_sys.clk, clk25)
        platform.add_false_path_constraint(self.cd_fast.clk, clk25)

class _CRG_5a75(Module):
    def __init__(self, platform, sys_clk_freq, fast_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_fast   = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        use_internal_osc = False

        # Clk / Rst
        if not use_internal_osc:
            clk = platform.request("clk25")
            clk_freq = 25e6
        else:
            clk = Signal()
            div = 5
            self.specials += Instance("OSCG",
                                p_DIV = div,
                                o_OSC = clk)
            clk_freq = 310e6/div

        platform.add_period_constraint(clk, 1e9/clk_freq)
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(clk, clk_freq)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_fast, fast_clk_freq)
        platform.add_false_path_constraint(self.cd_sys.clk, self.cd_fast.clk)
        platform.add_false_path_constraint(self.cd_sys.clk, clk)
        platform.add_false_path_constraint(self.cd_fast.clk, clk)

class LiteHM2(SoCCore):
    def __init__(self, sys_clk_freq=int(40e6), with_etherbone=True,
            ip_address=None, mac_address=None, with_bios=False,
            builddir="build", config="board.conf", with_init=True):

        fast_clk_freq = 200e6
        with_bios = False
        with_ethernet = True
        with_etherbone = False
        with_flash = True
        with_hostmot2 = True
        with_litescope = False
        with_uartbone = False
        with_leds = True
        with_uart = True
        with_led7219 = False
        tx_cdc_buffered = False
        cpu_type = "vexriscv"
        with_converter = False

        # check config file if we have to omit the serial port
        cfg = open(config, 'r').readlines()

        board = 'rv901t'
        driver_direction = 'input'
        serial = 'yes'
        cfg_pass_on = []
        for line in cfg:
            line = re.sub('#.*$', '', line)
            line = line.rstrip()
            line = line.lstrip()
            if (line == ''):
                continue
            toks = line.split()
            if toks[0] == 'board':
                if len(toks) != 2:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                if toks[1] != 'rv901t' and toks[1] != '5a75b' and toks[1] != '5a75e':
                    raise ValueError("unknown board {}".format(toks[1]))
                board = toks[1]
            elif toks[0] == 'driver_direction':
                if len(toks) != 2:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                if toks[1] not in ['input', 'output']:
                    raise ValueError("invalid driver direction, only 'input'" +
                        " and 'output' are valid")
                driver_direction = toks[1]
            elif toks[0] == 'serial':
                if len(toks) != 2:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                if toks[1] not in ['no', 'yes']:
                    raise ValueError("invalid serial directive, only 'no'" +
                        " and 'yes' are valid")
                serial = toks[1]
            else:
                cfg_pass_on.append(line)

        if board == 'rv901t':
            from litex_boards.platforms import linsn_rv901t
            from liteeth.phy.s6rgmii import LiteEthPHYRGMII

            sys_clk_freq = 100e6

            platform = linsn_rv901t.Platform()
            self.submodules.crg = _CRG_rv901t(platform, sys_clk_freq, fast_clk_freq)

            #
            # add JP4 header
            #
            if serial == 'no':
                platform.add_connector(("J4", {
                    3: "H5",
                    4: "G5",
                    5: "G6",
                    6: "F5",
                    7: "F12",
                    8: "F6",
                }))
                with_uart = False
            else:
                platform.add_connector(("J4", {
                    7: "F12",
                    8: "F6",
                }))

            # set to input
            bufdir = platform.request("bufdir")
            if driver_direction == 'input':
                self.comb += bufdir.eq(1)
            else:
                self.comb += bufdir.eq(0)

            #
            # set spi flash /wp and /hold to input with weak pullup
            # there might be a better way to do it
            #
            platform.add_extension([
                ("unused_spi", 0,
                    Subsignal("wp", Pins("N12"), Misc("PULLUP")),
                    Subsignal("hold", Pins("P12"), Misc("PULLUP")),
                    IOStandard("LVCMOS33"),
                ),
            ])
            unused = platform.request("unused_spi", 0)

            led_name = 'user_led'

        elif board == '5a75b':
            from litex_boards.platforms import colorlight_5a_75b
            from litex.build.lattice import LatticePlatform
            from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII

            sys_clk_freq = 40e6

            # XXX configurable revision
            platform = colorlight_5a_75b.Platform(revision='7.0', toolchain="trellis")
            self.submodules.crg = _CRG_5a75(platform, sys_clk_freq, fast_clk_freq)

            with_uart = False
            led_name = 'user_led_n'
            tx_cdc_buffered = True
            with_converter = True

        elif board == '5a75e':
            from litex_boards.platforms import colorlight_5a_75e
            #from litex.build.lattice import LatticePlatform
            from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII

            sys_clk_freq = 40e6

            # XXX configurable revision
            platform = colorlight_5a_75e.Platform(revision='6.0', toolchain="trellis")
            self.submodules.crg = _CRG_5a75(platform, sys_clk_freq, fast_clk_freq)

            with_uart = False
            led_name = 'user_led_n'
            tx_cdc_buffered = True
            with_converter = True

        if with_bios:
            SoCCore.__init__(self, platform,
                clk_freq = sys_clk_freq,
                cpu_variant = "minimal",
                integrated_rom_size = 0x8000,
                integrated_sram_size = 0x1000,
                integrated_main_ram_size = 0x2000,
            #    with_uart = False,
            )
        else:
            main_ram_init = get_mem_data(builddir + "/firmware/firmware.bin",
                endianness = "little", # FIXME: Depends on CPU.
                data_width = 32,       # FIXME: Depends on CPU.
            )
            SoCCore.__init__(self, platform,
                clk_freq = sys_clk_freq,
                #cpu_variant = "lite",
                cpu_variant = "minimal",
                #cpu_variant = "standard",
                cpu_type = cpu_type,
                integrated_rom_size = 0x1000,
                integrated_rom_init = builddir + "/firmware/loader.bin",
                integrated_sram_size = 0x1000,
                integrated_main_ram_size = 0x4000,
                integrated_main_ram_init = main_ram_init,
                with_uart = with_uart,
#                bus_interconnect = "crossbar",
            )

        if with_litescope:
            count = Signal(8)
            self.sync += count.eq(count + 1)
            analyzer_signals = [
                self.cpu.ibus.dat_r,
                self.cpu.ibus.dat_w,
                self.cpu.ibus.adr,
                self.cpu.ibus.sel,
                self.cpu.ibus.cyc,
                self.cpu.ibus.stb,
                self.cpu.ibus.ack,
                self.cpu.ibus.we,
                self.cpu.ibus.cti,
                self.cpu.reset,
                count,
            ]
            if cpu_type == "vexriscv":
                analyzer_signals.extend([
                    self.cpu.dbus.dat_r,
                    self.cpu.dbus.dat_w,
                    self.cpu.dbus.adr,
                    self.cpu.dbus.sel,
                    self.cpu.dbus.cyc,
                    self.cpu.dbus.stb,
                    self.cpu.dbus.ack,
                ])
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
                depth        = 1024,
                clock_domain = "sys",
                samplerate   = self.sys_clk_freq,
                csr_csv      = "analyzer.csv")
            self.add_csr("analyzer")

        if with_leds:
            leds =platform.request_all(led_name)
            self.submodules.leds = LedChaser(
                pads         = leds,
                sys_clk_freq = sys_clk_freq)
            leds = None

        if with_ethernet or with_etherbone:
            clock_pads = self.platform.request("eth_clocks", 0)
            pads = self.platform.request("eth", 0)
            if board == '5a75e':
                # remove pin rst_n from pads and hardwire it to 1
                self.comb += pads.rst_n.eq(1)
                for f in range(0, len(pads.layout)):
                    if pads.layout[f][0] == 'rst_n':
                        del pads.layout[f]
                        break
                delattr(pads, 'rst_n')

            self.submodules.ethphy = LiteEthPHYRGMII(
                clock_pads = clock_pads,
                pads       = pads,
                tx_delay   = 0e-9)

        if with_ethernet:
            self.add_ethernet(
                phy         = self.ethphy,
                data_width  = 32,
                ntxslots    = 1,
                nrxslots    = 8,
                txslots_write_only = True,
                with_timestamp = True,
                #tx_cdc_buffered = tx_cdc_buffered,
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
                sys_clk_freq, fast_clk_freq, leds, builddir=builddir,
                config=cfg_pass_on, with_converter=with_converter)

        #
        # don't add anything after this point, design gets
        # partially finalized to access debug signals
        #
        if not with_etherbone and not with_ethernet:
            phy =platform.request("eth", 0)
            self.comb += [
                phy.rst_n.eq(1),
            ]

        #
        # led7219 used for debugging only
        #
        if with_led7219:
            platform.add_extension([
                ("leds_clk", 0, Pins("j8:12"), IOStandard("LVCMOS33")),
                ("leds_cs", 0, Pins("j8:13"), IOStandard("LVCMOS33")),
                ("leds_out", 0, Pins("j8:14"), IOStandard("LVCMOS33")),
            ])
            leds_clk = platform.request("leds_clk", 0)
            leds_cs = platform.request("leds_cs", 0)
            leds_out = platform.request("leds_out", 0)
            debug_data = Signal(256)
            debug_signals_1 = [
                self.cpu.ibus.dat_r,
                self.cpu.ibus.dat_w,
                self.cpu.ibus.adr,
                Signal(2),
                self.cpu.ibus.sel,
                self.cpu.ibus.cyc,
                self.cpu.ibus.stb,
                self.cpu.ibus.ack,
                self.cpu.ibus.we,
                self.cpu.ibus.cti,
                self.cpu.ibus.bte,
                self.cpu.ibus.err,
                Signal(18),
            ]
            debug_signal_2 = Signal(128)
            if cpu_type == "vexriscv":
                debug_signals_2 = [
                    self.cpu.dbus.dat_w,
                    self.cpu.dbus.adr,
                    Signal(2),
                    self.cpu.dbus.sel,
                    self.cpu.dbus.cyc,
                    self.cpu.dbus.stb,
                    self.cpu.dbus.ack,
                    self.cpu.dbus.we,
                    self.cpu.dbus.cti,
                    self.cpu.dbus.bte,
                    self.cpu.dbus.err,
                ]
            self.comb += [ debug_data.eq(Cat(*debug_signals_1, *debug_signals_2)) ]
            self.specials += Instance("led7219",
                i_clk         = self.crg.cd_sys.clk,
                i_data        = debug_data,
                o_leds_out    = leds_out,
                o_leds_clk    = leds_clk,
                o_leds_cs     = leds_cs
            )

            platform.add_source("led7219.v")

# Build ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=
        "Take control of your ColorLight FPGA board with LiteX/LiteEth :)")
    parser.add_argument("--ip-address", default="10.10.10.10",
        help="Ethernet IP address of the board (default: 10.10.10.10).")
    parser.add_argument("--mac-address", default="0x726b895bc2e2",
        help="Ethernet MAC address of the board (default: 0x726b895bc2e2).")
    parser.add_argument("--builddir", default="build",
        help="Build directory (default: build).")
    parser.add_argument("--config", default="board.conf",
        help="Board config file (default: board.conf).")

    args = parser.parse_args()
    builddir = args.builddir;

    soc = LiteHM2(ip_address=args.ip_address,
        mac_address=int(args.mac_address, 0), builddir=builddir,
        config=args.config)
    builder = Builder(soc, output_dir=builddir, csr_csv=builddir + "/csr.csv")
    builder.build(build_name="litehm2", run=False)

if __name__ == "__main__":
    main()
