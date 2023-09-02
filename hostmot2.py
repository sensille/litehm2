#!/usr/bin/env python3

from re import *
from migen import *

from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.build.generic_platform import *
from litex.build.vhd2v_converter import *

func_lines = {
    'stepgen':
        '(StepGenTag, x"02", ClockLowTag, x"{:02x}", StepGenRateAddr&PadT, '
            + 'StepGenNumRegs, x"00", StepGenMPBitMask)',
    'pwm':
	'(PWMTag, x"00", ClockHighTag, x"{:02x}", PWMValAddr&PadT, '
            + 'PWMNumRegs, x"00", PWMMPBitMask)',
    'gpio':
	'(IOPortTag, x"00", ClockLowTag, x"{:02x}", PortAddr&PadT, '
            + 'IOPortNumRegs, x"00", IOPortMPBitMask)',
    'led':
        '(LEDTag, x"00", ClockLowTag, x"{:02x}", LEDAddr&PadT, '
            + 'LEDNumRegs, x"00", LEDMPBitMask)',
    'qcount':
        '(QcountTag, x"02", ClockLowTag, x"{:02x}", QcounterAddr&PadT, '
            + 'QCounterNumRegs, x"00", QCounterMPBitMask)',
    'inm':
        '(InMTag, x"00", ClockLowTag, x"{:02x}", InMControlAddr&PadT, '
            + 'InMNumRegs, x"00", InMMPBitMask)',
    'inmux':
        '(InMuxTag, x"00", ClockLowTag, x"{:02x}", InMuxControlAddr&PadT, '
            + 'InMuxNumRegs, x"00", InmuxMPBitMask)',
    'sserial':
        '(SSerialTag, x"00", ClockLowTag, x"{:02x}", SSerialCommandAddr&PadT, '
            + 'SSerialNumRegs, x"10", SSerialMPBitMask)',
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
    'inm': {
        'data0': ['InMData0Pin', 'in'],
        'data1': ['InMData1Pin', 'in'],
        'data2': ['InMData2Pin', 'in'],
        'data3': ['InMData3Pin', 'in'],
        'data4': ['InMData4Pin', 'in'],
        'data5': ['InMData5Pin', 'in'],
        'data6': ['InMData6Pin', 'in'],
        'data7': ['InMData7Pin', 'in'],
        'data8': ['InMData8Pin', 'in'],
        'data9': ['InMData9Pin', 'in'],
        'dataA': ['InMDataAPin', 'in'],
        'dataB': ['InMDataBPin', 'in'],
        'dataC': ['InMDataCPin', 'in'],
        'dataD': ['InMDataDPin', 'in'],
        'dataE': ['InMDataEPin', 'in'],
        'dataF': ['InMDataFPin', 'in'],
    },
    'inmux': {
        'data': ['InMuxDataPin', 'in'],
        'addr0': ['InMuxAddr0Pin', 'in'],
        'addr1': ['InMuxAddr1Pin', 'in'],
        'addr2': ['InMuxAddr2Pin', 'in'],
        'addr3': ['InMuxAddr3Pin', 'in'],
        'addr4': ['InMuxAddr4Pin', 'in'],
    },
    'sserial': {
        'tx0en': ['SSerialTxEn0Pin', 'in'],
        'tx1en': ['SSerialTxEn1Pin', 'in'],
        'tx2en': ['SSerialTxEn2Pin', 'in'],
        'tx3en': ['SSerialTxEn3Pin', 'in'],
        'tx4en': ['SSerialTxEn4Pin', 'in'],
        'tx5en': ['SSerialTxEn5Pin', 'in'],
        'tx6en': ['SSerialTxEn6Pin', 'in'],
        'tx7en': ['SSerialTxEn7Pin', 'in'],
        'tx8en': ['SSerialTxEn8Pin', 'in'],
        'tx9en': ['SSerialTxEn9Pin', 'in'],
        'txaen': ['SSerialTxEnAPin', 'in'],
        'txben': ['SSerialTxEnBPin', 'in'],
        'txcen': ['SSerialTxEnCPin', 'in'],
        'txden': ['SSerialTxEnDPin', 'in'],
        'txeen': ['SSerialTxEnEPin', 'in'],
        'ntx0en': ['SSerialNTxEn0Pin', 'in'],
        'ntx1en': ['SSerialNTxEn1Pin', 'in'],
        'ntx2en': ['SSerialNTxEn2Pin', 'in'],
        'ntx3en': ['SSerialNTxEn3Pin', 'in'],
        'ntx4en': ['SSerialNTxEn4Pin', 'in'],
        'ntx5en': ['SSerialNTxEn5Pin', 'in'],
        'ntx6en': ['SSerialNTxEn6Pin', 'in'],
        'ntx7en': ['SSerialNTxEn7Pin', 'in'],
        'ntx8en': ['SSerialNTxEn8Pin', 'in'],
        'ntx9en': ['SSerialNTxEn9Pin', 'in'],
        'ntxaen': ['SSerialNTxEnAPin', 'in'],
        'ntxben': ['SSerialNTxEnBPin', 'in'],
        'ntxcen': ['SSerialNTxEnCPin', 'in'],
        'ntxden': ['SSerialNTxEnDPin', 'in'],
        'ntxeen': ['SSerialNTxEnEPin', 'in'],
        'tx0': ['SSerialTx0Pin', 'out'],
        'tx1': ['SSerialTx1Pin', 'out'],
        'tx2': ['SSerialTx2Pin', 'out'],
        'tx3': ['SSerialTx3Pin', 'out'],
        'tx4': ['SSerialTx4Pin', 'out'],
        'tx5': ['SSerialTx5Pin', 'out'],
        'tx6': ['SSerialTx6Pin', 'out'],
        'tx7': ['SSerialTx7Pin', 'out'],
        'tx8': ['SSerialTx8Pin', 'out'],
        'tx9': ['SSerialTx9Pin', 'out'],
        'txa': ['SSerialTxAPin', 'out'],
        'txb': ['SSerialTxBPin', 'out'],
        'txc': ['SSerialTxCPin', 'out'],
        'txd': ['SSerialTxDPin', 'out'],
        'txe': ['SSerialTxEPin', 'out'],
        'rx0': ['SSerialRx0Pin', 'in'],
        'rx1': ['SSerialRx1Pin', 'in'],
        'rx2': ['SSerialRx2Pin', 'in'],
        'rx3': ['SSerialRx3Pin', 'in'],
        'rx4': ['SSerialRx4Pin', 'in'],
        'rx5': ['SSerialRx5Pin', 'in'],
        'rx6': ['SSerialRx6Pin', 'in'],
        'rx7': ['SSerialRx7Pin', 'in'],
        'rx8': ['SSerialRx8Pin', 'in'],
        'rx9': ['SSerialRx9Pin', 'in'],
        'rxa': ['SSerialRxAPin', 'in'],
        'rxb': ['SSerialRxBPin', 'in'],
        'rxc': ['SSerialRxCPin', 'in'],
        'rxd': ['SSerialRxDPin', 'in'],
        'rxe': ['SSerialRxEPin', 'in'],
    },
}

pin_lines = {
    'stepgen': 'std_logic_vector\'(IOPortTag & x"{:02x}" & StepGenTag & {})',
    'pwm': 'std_logic_vector\'(IOPortTag & x"{:02x}" & PWMTag & {})',
    'gpio': 'std_logic_vector\'(IOPortTag & x"{:02x}" & NullTag & x"00")',
    'qcount': 'std_logic_vector\'(IOPortTag & x"{:02x}" & QCountTag & {})',
    'inm': 'std_logic_vector\'(IOPortTag & x"{:02x}" & InMTag & {})',
    'inmux': 'std_logic_vector\'(IOPortTag & x"{:02x}" & InMuxTag & {})',
    'sserial': 'std_logic_vector\'(IOPortTag & x"{:02x}" & SSerialTag & {})',
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
constant IOPorts: integer := {ioports};
constant IOWidth: integer := {iowidth};
constant PortWidth: integer := {portwidth};
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
    def __init__(self, soc, sys_clk_freq, fast_clk_freq, leds=None,
            with_converter=False, config=None, builddir='build'):
        platform = soc.platform

        if config is None:
            raise ValueError("no config given")

        #
        # read board config
        #
        aliases = {}
        apins = {}
        for line in config:
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
                    if apins.get(toks[1]) is not None:
                        raise ValueError("parsing board config fails, pin " +
                            "{} used more than once".format(toks[1]))
                    apins[toks[1]] = toks[2]
                else:
                    apins[toks[1]] = 'gpio.0'
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
        funccnt = {}
        for _, v in bpins.items():
            v = re.sub('^!', '', v)
            toks = v.split('.')
            if len(toks) < 2:
                raise ValueError("parsing board config fails, function {}"
                    .format(v))
            ix = funcs.setdefault(toks[0], 0)
            if int(toks[1]) > ix:
                funcs[toks[0]] = int(toks[1])
            cntkey = toks[0] + '.' + toks[1]
            funccnt[cntkey] = funccnt.get(cntkey, 0) + 1

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

        # valid port widths: 17, 19, 21, 24, 27, 29, 30, 32
        ioports, portwidth = calc_ports(npins)
        iowidth = ioports * portwidth
        cout = open(builddir + '/consts_gen.vhd', 'w')
        cout.write(consts_header.format(
            fast_clk = int(fast_clk_freq),
            sys_clk = int(sys_clk_freq),
            ioports = int(ioports),
            portwidth = int(portwidth),
            iowidth = int(iowidth),
        ))

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
            if n == 'gpio':
                v = ioports - 1
            func_consts.append(line.format(v + 1))
        n_inm = funcs.get('inm')
        n_inmux = funcs.get('inmux')
        n = 32
        if n_inm is not None:
            n -= n_inm + 1
        if n_inmux is not None:
            n -= n_inmux + 1
        for _ in range(len(func_consts), n):
            func_consts.append(func_null_tag)
        if n_inm is not None:
            for i in range(n_inm + 1):
                # need at least 8 for mpg to work
                inm_width = max(funccnt["inm.{}".format(i)], 8)
                func_consts.append(
                    '(InMWidth{}Tag, x"00", NullTag, x"00", NullAddr&PadT, x"00", x"00", x"{:08x}")'
                        .format(i, inm_width)
                )
        if n_inmux is not None:
            for i in range(n_inmux + 1):
                func_consts.append(
                    '(InMuxWidth{}Tag, x"00", NullTag, x"00", NullAddr&PadT, x"00", x"00", x"{:08x}")'
                        .format(i, 32)
                )

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
        hm2_leds = leds

        hm2_ioins = []
        hm2_ioouts = []
        for n, p in enumerate(pins):
            if p[2] == 'in':
                hm2_ioins.append(hmio[n])
                hm2_ioouts.append(Signal())
            else:
                io = None
                if p[1]:
                    s = Signal()
                    self.comb += hmio[n].eq(~s)
                    io = s
                else:
                    io = hmio[n]
                hm2_ioins.append(io)
                hm2_ioouts.append(io)

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
            i_ioins         = Cat(*hm2_ioins),
            o_ioouts        = Cat(*hm2_ioouts),
            o_rates         = hm2_rates,
            o_leds          = hm2_leds,
            o_wdlatchedbite = hm2_wdlatchedbite,
            # io_liobits not used
        )

        src_target = platform
        if with_converter:
            self.submodules.hm2_vhd2v_converter = VHD2VConverter(platform,
                top_entity = "TopHostMot2",
                build_dir = os.path.abspath(builddir + "/gateware/"),
                work_package = "unisim",
                force_convert = True,
            )
            conv = self.hm2_vhd2v_converter
            conv._ghdl_opts.append("-fsynopsys")
            conv._ghdl_opts.append("-frelaxed")
            path = "hostmot2/";
            for item in os.listdir(path):
                if os.path.isfile(os.path.join(path, item)):
                    print("add source %s" % item)
                    conv.add_source(os.path.join(path, item))
            conv.add_source("consts_gen.vhd")
            conv.add_source("hostmot2_top.vhd")
        else:
            src_target.add_source_dir(path="hostmot2/")
            src_target.add_source(builddir + "/consts_gen.vhd")
            src_target.add_source("hostmot2_top.vhd")

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

def calc_ports(npins):
    valid_widths = [17, 19, 21, 24, 27, 29, 30, 32]
    best_n = None
    best_w = None

    for n in range(1, 9):
        for w in valid_widths:
            if n * w >= npins and (best_n is None
                    or n * w < best_n * best_w):
                best_n = n
                best_w = w

    if best_n * best_w != npins:
        raise ValueError(("invalid number of pins. Have {} pins. Best match" +
            " would be {} pins.").format(npins, best_n * best_w))

    return best_n, best_w
