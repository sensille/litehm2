library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;
--library UNISIM;
--use UNISIM.VComponents.all;

use work.consts_gen.all;
use work.IDROMConst.all;

entity TopHostMot2 is
	generic (
		ThePinDesc: PinDescType := PinDesc;
		TheModuleID: ModuleIDType := ModuleID;
		PWMRefWidth: integer := 13;
		IDROMType: integer := 3;
		UseStepGenPrescaler : boolean := true;
		UseIRQLogic: boolean := true;
		UseWatchDog: boolean := true;
		OffsetToModules: integer := 64;
		OffsetToPinDesc: integer := 448;
		BusWidth: integer := 32;
		AddrWidth: integer := 16;
		InstStride0: integer := 4;	-- instance stride 0 = 4 bytes = 1 x 32 bit
		InstStride1: integer := 64;	-- instance stride 1 = 64 bytes = 16 x 32 bit registers sserial
		RegStride0: integer := 256;	-- register stride 0 = 256 bytes = 64 x 32 bit registers
		RegStride1: integer := 256;	-- register stride 1 = 256 bytes - 64 x 32 bit
		FallBack: boolean := false	-- is this a fallback config?
	);

	Port (
		ibus: in std_logic_vector(buswidth -1 downto 0);
		obus: out std_logic_vector(buswidth -1 downto 0);
		addr: in std_logic_vector(addrwidth -1 downto 2);
		readstb: in std_logic;
		writestb: in std_logic;
		clklow: in std_logic;
		clkmed: in std_logic;
		clkhigh: in std_logic;
		int: out std_logic; 
		dreq: out std_logic;
		demandmode: out std_logic;
		ioins: in std_logic_vector (IOWidth -1 downto 0);
		ioouts: out std_logic_vector (IOWidth -1 downto 0);
		ioenas: out std_logic_vector (IOWidth -1 downto 0);
		rates: out std_logic_vector (4 downto 0);
		leds: out std_logic_vector(ledcount-1 downto 0);
		wdlatchedbite: out std_logic
	);
end TopHostMot2;

architecture Behavioral of TopHostMot2 is

signal lioins: std_logic_vector (LIOWidth -1 downto 0);
signal lioouts: std_logic_vector (LIOWidth -1 downto 0);

begin

ahostmot2: entity work.HostMot2
	generic map (
		thepindesc => ThePinDesc,
		themoduleid => TheModuleID,
		idromtype  => IDROMType,
		sepclocks  => SepClocks,
		onews  => OneWS,
		useirqlogic  => UseIRQLogic,
		pwmrefwidth  => PWMRefWidth,
		usewatchdog  => UseWatchDog,
		offsettomodules  => OffsetToModules,
		offsettopindesc  => OffsetToPinDesc,
		clockhigh  => ClockHigh,
		clockmed => CLockMed,
		clocklow  => ClockLow,
		boardnamelow => BoardNameLow,
		boardnamehigh => BoardNameHigh,
		fpgasize  => FPGASize,
		fpgapins  => FPGAPins,
		ioports  => IOPorts,
		iowidth  => IOWidth,
		liowidth  => LIOWidth,
		portwidth  => PortWidth,
		buswidth  => BusWidth,
		addrwidth  => AddrWidth,
		inststride0 => InstStride0,
		inststride1 => InstStride1,
		regstride0 => RegStride0,
		regstride1 => RegStride1,
		ledcount  => LEDCount
	) port map (
		ibus => ibus,
		obus => obus, 
		addr => addr(15 downto 2),
		readstb => readstb,
		writestb => writestb,
		clklow => clklow,
		clkmed => clkmed,				-- on Ethernet cards procclk is same as clocklow
		clkhigh => clkhigh,
		int => int, 
		dreq => dreq,
		demandmode => demandmode,
		ioins => ioins,
		ioouts => ioouts,
		ioenas => ioenas,
		lioins => lioins,
		lioouts => lioouts,
		rates => rates,
		leds => leds,
		wdlatchedbite => wdlatchedbite 
	);

end Behavioral;
