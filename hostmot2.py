#!/usr/bin/env python3

from re import *
from migen import *

from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.build.generic_platform import *

func_lines = {
    'stepgen':
        '(StepGenTag, x"02", ClockLowTag, x"{:02x}", StepGenRateAddr&PadT, '
            + 'StepGenNumRegs, x"00", StepGenMPBitMask)',
    'pwm':
	'(PWMTag, x"00", ClockHighTag, x"{:02x}", PWMValAddr&PadT, '
            + 'PWMNumRegs, x"00", PWMMPBitMask)',
    # XXX render number of ports into here
    'gpio':
	'(IOPortTag, x"00", ClockLowTag, x"03", PortAddr&PadT, '
            + 'IOPortNumRegs, x"00", IOPortMPBitMask)',
    'led':
        '(LEDTag, x"00", ClockLowTag, x"{:02x}", LEDAddr&PadT, '
            + 'LEDNumRegs, x"00", LEDMPBitMask)',
    'qcount':
        '(QcountTag, x"02", ClockLowTag, x"{:02x}", QcounterAddr&PadT, '
            + 'QCounterNumRegs, x"00", QCounterMPBitMask)',
}

func_default_lines = [
    '(HM2DPLLTag, x"00", ClockLowTag, x"01", HM2DPLLBaseRateAddr&PadT, '
        + 'HM2DPLLNumRegs, x"00", HM2DPLLMPBitMask)',
    '(WatchDogTag, x"00", ClockLowTag, x"01", WatchDogTimeAddr&PadT, '
        + 'WatchDogNumRegs, x"00", WatchDogMPBitMask)',
]

func_null_tag = '(NullTag, x"00", NullTag, x"00", NullAddr&PadT, ' \
    + 'x"00", x"00", x"00000000")'

pin_subfuncs = {
    'stepgen': {
        'step': ['StepGenStepPin', 'out'],
        'pulse': ['StepGenStepPin', 'out'],
        'dir': ['StepGenDirPin', 'out'],
    },
    'pwm': {
        'out': ['PWMAOutPin', 'out'],
        'dir': ['PWMBDirPin', 'out'],
    },
    'gpio': {
        'in': ['', 'in'],
        'out': ['', 'out'],
    },
    'qcount': {
        'a': ['QCountQAPin', 'in'],
        'b': ['QCountQBPin', 'in'],
        'idx': ['QCountIDXPin', 'in'],
    },
}
pin_lines = {
    'stepgen': 'IOPortTag & x"{:02x}" & StepGenTag & {}',
    'pwm': 'IOPortTag & x"{:02x}" & PWMTag & {}',
    'gpio': 'IOPortTag & x"{:02x}" & NullTag & x"00"',
    'qcount': 'IOPortTag & x"{:02x}" & QCountTag & {}',
}

consts_header = """
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;

use work.IDROMConst.all;
package consts_gen is

constant BoardNameLHM2 : std_logic_vector(31 downto 0) := x"326d686c"; -- lhm2

constant ClockHigh: integer := {fast_clk};
constant ClockMed: integer := {sys_clk};
constant ClockLow: integer := {sys_clk};
constant BoardNameLow : std_Logic_Vector(31 downto 0) := BoardNameMESA;
constant BoardNameHigh : std_Logic_Vector(31 downto 0) := BoardNameLHM2;
constant FPGASize: integer := 16;
constant FPGAPins: integer := 144;
constant IOPorts: integer := 3;
constant IOWidth: integer := 72;
constant PortWidth: integer := 24;
constant LIOWidth: integer := 0;
constant LEDCount: integer := 1;
constant SepClocks: boolean := true;
constant OneWS: boolean := true;

constant ModuleID : ModuleIDType :=(
"""

consts_sep = """
);

constant PinDesc : PinDescType :=(
"""

consts_trailer = """
);

end package consts_gen;
"""

class HostMot2(Module, AutoCSR):
    def __init__(self, soc, sys_clk_freq, fast_clk_freq, with_leds=False,
            config='board.conf', builddir='build'):
        platform = soc.platform

        leds = 1
        if with_leds:
            # CPU owns the LEDs
            leds = 0

        #
        # read board config
        #
        aliases = {}
        apins = {}
        board = 'rv901t'
        driver_direction = 'input'
        cfg = open(config, 'r')
        for line in cfg:
            line = re.sub('#.*$', '', line)
            line = line.rstrip()
            line = line.lstrip()
            if (line == ''):
                continue
            toks = line.split()
            if toks[0] == 'alias':
                if len(toks) != 3:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                aliases[toks[1]] = toks[2]
            elif toks[0] == 'pin':
                if len(toks) not in [2, 3]:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                if len(toks) == 3:
                    apins[toks[1]] = toks[2]
                else:
                    apins[toks[1]] = 'gpio.0'
            elif toks[0] == 'board':
                if len(toks) != 2:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                if toks[1] != 'rv901t':
                    raise ValueError("unknown board {}".format(toks[1]))
                board = toks[1]
            elif toks[0] == 'driver_direction':
                if len(toks) != 2:
                    raise ValueError("parsing board config fails, line {}"
                        .format(line))
                if toks[1] not in ['input', 'output']:
                    raise ValueError("invalid driver direction, only 'input'" +
                        " and 'output are valid")
                driver_direction = toks[1]
            else:
                raise ValueError("parsing board config failed, unknown token {}"
                    .format(toks[0]))

        #
        # resolve aliases to board pins
        #
        bpins = {}
        for n, v in apins.items():
            # resolve alias (chain)
            while aliases.get(n):
                n = aliases[n]
            bpins[n] = v

        #
        # collect functions
        #
        funcs = {}
        for _, v in bpins.items():
            v = re.sub('^!', '', v)
            toks = v.split('.')
            if len(toks) < 2:
                raise ValueError("parsing board config fails, function {}"
                    .format(v))
            ix = funcs.setdefault(toks[0], 0)
            if int(toks[1]) > ix:
                funcs[toks[0]] = int(toks[1])

        #
        # build consts output
        #
        func_consts = func_default_lines
        for n, v in funcs.items():
            line = func_lines.get(n)
            if line is None:
                raise ValueError(
                    "parsing board config fails, unknown function {}"
                    .format(n))
            func_consts.append(line.format(v + 1))
        for _ in range(len(func_consts), 32):
            func_consts.append(func_null_tag)

        #
        # build pin assignments
        #
        pin_consts = []
        pins = []

        #
        # sort pins first, so that gpio come first. this way they have the
        # same names on the host as in our conf file
        #
        pin_order = []
        for i in range(0, funcs['gpio'] + 1):
            bn = None
            for n, v in bpins.items():
                toks = v.split('.')
                if toks[0] == 'gpio' and int(toks[1]) == i:
                    if bn is not None:
                        raise ValueError("parsing board config fails, duplicate"
                            + " gpio {}".format(toks[1]))
                    bn = n
            if bn is None:
                raise ValueError("parsing board config fails, gpio "
                    + "{} not found".format(i))
            pin_order.append(bn)
        for n, v in bpins.items():
            toks = v.split('.')
            if toks[0] != 'gpio':
                pin_order.append(n)

        for n in pin_order:
            v = bpins[n]
            negated = False
            if v[0] == '!':
                negated = True
                v = v[1:]
            toks = v.split('.')
            subfuncs = pin_subfuncs.get(toks[0])
            subfunc = None
            dir = 'out'
            if subfuncs is not None:
                if len(toks) != 3:
                    raise ValueError("parsing board config fails, function {}"
                        + " expects a sub-function".format(v))
                subfunc = subfuncs.get(toks[2])
                if subfunc is None:
                    raise ValueError("parsing board config fails, function {}"
                        + " has no sub-function {}".format(v, toks[2]))
                dir = subfunc[1]
                subfunc = subfunc[0]
            if negated and dir == 'in':
                    raise ValueError("parsing board config fails, cannot "
                        + "negate input")
            pin_consts.append(pin_lines[toks[0]].format(int(toks[1]), subfunc))
            pins.append([n, negated, dir])
        npins = len(pin_consts)
        for _ in range(npins, 144):
            pin_consts.append("emptypin")

        cout = open(builddir + '/consts_gen.vhd', 'w')
        cout.write(consts_header.format(
            fast_clk = int(fast_clk_freq),
            sys_clk = int(sys_clk_freq),
            npins = npins))

        for i in range(0, len(func_consts)):
            cout.write('\t' + func_consts[i])
            if i != len(func_consts) - 1:
                cout.write(',')
            cout.write('\n')
        cout.write(consts_sep)
        for i in range(0, len(pin_consts)):
            cout.write('\t' + pin_consts[i])
            if i != len(pin_consts) - 1:
                cout.write(',')
            cout.write('\n')
        cout.write(consts_trailer)

        hmio = []
        for n, p in enumerate(pins):
            #name = "io_" + p[0]
            #name = name.replace(':', '_')
            name = 'hmio'
            platform.add_extension([
                (name, n, Pins(p[0]), IOStandard("LVCMOS33")),
            ])
            hmio.append(platform.request(name, n))

        hm2_ibus = Signal(32)
        hm2_obus = Signal(32)
        hm2_addr = Signal(14)
        hm2_readstb = Signal()
        hm2_writestb = Signal()
        hm2_clklow = Signal()
        hm2_clkmed = Signal()
        hm2_clkhigh = Signal()
        hm2_int = Signal()
        hm2_dreq = Signal()
        hm2_demandmode = Signal()
        hm2_rates = Signal(5)
        hm2_wdlatchedbite = Signal()
        hm2_leds = None
        if not with_leds:
            hm2_leds = platform.request_all("user_led")

        hm2_iobits = []
        for n, p in enumerate(pins):
            if p[2] == 'in':
                hm2_iobits.append(hmio[n])
            else:
                if p[1]:
                    s = Signal()
                    self.comb += hmio[n].eq(~s)
                    hm2_iobits.append(s)
                else:
                    hm2_iobits.append(hmio[n])

        # set to input
        bufdir = platform.request("bufdir")
        if driver_direction == 'input':
            self.comb += bufdir.eq(1)
        else:
            self.comb += bufdir.eq(0)

        # on 7i92: clklow, clkmed: 100MHz (procclock)
        #          clkhigh: 200MHz (clk1fx -> BUFG -> hs2fastclock)
        self.specials += Instance("TopHostMot2",
            i_ibus          = hm2_ibus,
            o_obus          = hm2_obus,
            i_addr          = hm2_addr,
            i_readstb       = hm2_readstb,
            i_writestb      = hm2_writestb,
            i_clklow        = hm2_clklow,
            i_clkmed        = hm2_clkmed,
            i_clkhigh       = hm2_clkhigh,
            o_int           = hm2_int,              # not used
            o_dreq          = hm2_dreq,             # not used
            o_demandmode    = hm2_demandmode,       # not used
            io_iobits       = Cat(*hm2_iobits),
            o_rates         = hm2_rates,
            o_leds          = hm2_leds,
            o_wdlatchedbite = hm2_wdlatchedbite,
            # io_liobits not used
        )

        platform.add_source_dir(path="hostmot2/")
        platform.add_source(builddir + "/consts_gen.vhd")
        platform.add_source("hostmot2_top.vhd")

        hm2bus = wishbone.Interface(soc.bus.data_width)
        soc.bus.add_slave("hostmot2", hm2bus,
            SoCRegion(0x7000_0000, 0x10000, mode="rw"))
        self.comb += [
            hm2_ibus.eq(hm2bus.dat_w),
            hm2bus.dat_r.eq(hm2_obus),
            hm2_addr.eq(hm2bus.adr),
            hm2_clklow.eq(soc.crg.cd_sys.clk),
            hm2_clkmed.eq(soc.crg.cd_sys.clk),
            hm2_clkhigh.eq(soc.crg.cd_fast.clk),
        ]
        read_rq = Signal()
        read_rq_d = Signal()
        write_rq = Signal()
        write_rq_d = Signal()
        # TODO hmbus2.cti
        self.comb += [
            read_rq.eq(hm2bus.cyc & hm2bus.stb & ~hm2bus.we),
            hm2_readstb.eq(read_rq),
            write_rq.eq(hm2bus.cyc & hm2bus.stb & hm2bus.we),
            hm2_writestb.eq(write_rq),
        ]
        self.sync += [
            read_rq_d.eq(read_rq),
            write_rq_d.eq(write_rq),
            If ((read_rq & ~read_rq_d) | (write_rq & ~write_rq_d),
                hm2bus.ack.eq(1)
            ).Else(
                hm2bus.ack.eq(0)
            ),
        ]

        # USTimer
        prescale = int(sys_clk_freq / 1000000) - 1
        ustimer_prescale = Signal(max=prescale)
        ustimer = Signal(16)

        self.sync += [
            ustimer_prescale.eq(ustimer_prescale - 1),
            If (ustimer_prescale == 0,
                ustimer_prescale.eq(prescale),
                ustimer.eq(ustimer + 1)
            ),
        ]
        self.ustimer = CSRStatus(len(ustimer),
            description="HostMot2 USTimer")
        self.comb += self.ustimer.status.eq(ustimer)

        self.rates = CSRStatus(len(hm2_rates),
            description="HostMot2 htimer output")
        self.comb += self.rates.status.eq(hm2_rates)
