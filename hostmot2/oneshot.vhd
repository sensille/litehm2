library ieee;
use IEEE.std_logic_1164.ALL;
use IEEE.std_logic_ARITH.ALL;
use IEEE.std_logic_UNSIGNED.ALL;
--
-- Copyright (C) 2007, Peter C. Wallace, Mesa Electronics
-- http://www.mesanet.com
--
-- This program is is licensed under a disjunctive dual license giving you
-- the choice of one of the two following sets of free software/open source
-- licensing terms:
--
--    * GNU General Public License (GPL), version 2.0 or later
--    * 3-clause BSD License
-- 
--
-- The GNU GPL License:
-- 
--     This program is free software; you can redistribute it and/or modify
--     it under the terms of the GNU General Public License as published by
--     the Free Software Foundation; either version 2 of the License, or
--     (at your option) any later version.
-- 
--     This program is distributed in the hope that it will be useful,
--     but WITHOUT ANY WARRANTY; without even the implied warranty of
--     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
--     GNU General Public License for more details.
-- 
--     You should have received a copy of the GNU General Public License
--     along with this program; if not, write to the Free Software
--     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
-- 
-- 
-- The 3-clause BSD License:
-- 
--     Redistribution and use in source and binary forms, with or without
--     modification, are permitted provided that the following conditions
--     are met:
-- 
--         * Redistributions of source code must retain the above copyright
--           notice, this list of conditions and the following disclaimer.
-- 
--         * Redistributions in binary form must reproduce the above
--           copyright notice, this list of conditions and the following
--           disclaimer in the documentation and/or other materials
--           provided with the distribution.
-- 
--         * Neither the name of Mesa Electronics nor the names of its
--           contributors may be used to endorse or promote products
--           derived from this software without specific prior written
--           permission.
-- 
-- 
-- Disclaimer:
-- 
--     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
--     "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
--     LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
--     FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
--     COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
--     INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
--     BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
--     LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
--     CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
--     LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
--     ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
--     POSSIBILITY OF SUCH DAMAGE.
-- 

entity oneshot is
	port ( clk : in std_logic;
        ibus : in  std_logic_vector (31 downto 0);
        obus : out  std_logic_vector (31 downto 0);
        loadpw1 : in  std_logic;
        loadpw2 : in  std_logic;
		loadfilter1 : in std_logic;	  
        loadfilter2 : in std_logic;
        loadrate : in std_logic;
        loadcontrol : in std_logic;
        readcontrol : in std_logic;		  
        timers : in std_logic_vector(4 downto 0);		
        pulse1out : out  std_logic;
	    pulse2out : out  std_logic;
	    hwtrigger1 : in std_logic;
	    hwtrigger2 : in std_logic);
end oneshot;

architecture Behavioral of oneshot is
signal pw1: std_logic_vector(31 downto 0); 
signal pw2: std_logic_vector(31 downto 0);
signal pw1count: std_logic_vector(32 downto 0); 
signal pw2count: std_logic_vector(32 downto 0);
alias pw1countmsb: std_logic is pw1count(32);
alias pw2countmsb: std_logic is pw2count(32);
signal pw1prevmsb: std_logic;
signal pw2prevmsb: std_logic;
signal rateaccum: std_logic_vector(31 downto 0);
signal rateaccumreg: std_logic_vector(31 downto 0);
alias  ratemsb: std_logic is rateaccum(31);
signal timerdiv: std_logic_vector(15 downto 0); 
signal timerdivreg: std_logic_vector(15 downto 0); 
signal trigfilterreg1: std_logic_vector(23 downto 0);
signal trigfilterreg2: std_logic_vector(23 downto 0);
signal trigfiltercount1: std_logic_vector(23 downto 0);
signal trigfiltercount2: std_logic_vector(23 downto 0);
signal trigger1: std_logic;
signal trigger2: std_logic;
signal triggerd1: std_logic;
signal triggerd2: std_logic;
signal exttrigger1: std_logic;
signal exttrigger2: std_logic;
signal dplltrigger: std_logic;
signal controlreg:  std_logic_vector(31 downto 0);

signal run1: std_logic;
signal run2: std_logic;

alias startselect1: std_logic_vector(2 downto 0) is controlreg(2 downto 0);
alias startrise1: std_logic is controlreg(3);
alias startfall1: std_logic is controlreg(4);
alias retrigger1: std_logic is controlreg(5);
alias enable1: std_logic is controlreg(6);
alias reset1: std_logic is controlreg(7);
alias swtrigger1: std_logic is controlreg(10);
alias timerselect: std_logic_vector(3 downto 0) is controlreg(15 downto 12);
alias startselect2: std_logic_vector(2 downto 0) is controlreg(18 downto 16);
alias startrise2: std_logic is controlreg(19);
alias startfall2: std_logic is controlreg(20);
alias retrigger2: std_logic is controlreg(21);
alias enable2: std_logic is controlreg(22);
alias reset2: std_logic is controlreg(23);
alias swtrigger2: std_logic is controlreg(26);


begin
	aoneshot: process (clk)
	begin
		
		if rising_edge(clk) then
            
            triggerd1 <= trigger1;
		    triggerd2 <= trigger2;
			
            if (hwtrigger1 = '1') and (trigfiltercount1 < trigfilterreg1) then
				trigfiltercount1 <= trigfiltercount1 + 1;
			end if;
			if (hwtrigger1 = '0') and (trigfiltercount1 /= 0) then 
				trigfiltercount1 <= trigfiltercount1 -1;
			end if;
			if trigfiltercount1 >= trigfilterreg1 then
				exttrigger1 <= '1';
--				trigfiltercount1 <= trigfilterreg1;		-- handle the case where the filter time is reduced
			end if;
			if trigfiltercount1 = 0 then
				exttrigger1 <= '0';
			end if;

			if (hwtrigger2 = '1') and (trigfiltercount2 < trigfilterreg2) then
				trigfiltercount2 <= trigfiltercount2 + 1;
			end if;
			if (hwtrigger2 = '0') and (trigfiltercount2 /= 0) then 
				trigfiltercount2 <= trigfiltercount2 -1;
			end if;
			if trigfiltercount2 >= trigfilterreg2 then
				exttrigger2 <= '1';
--				trigfiltercount2 <= trigfilterreg2;		-- handle the case where the filter time is reduced
			end if;
			if trigfiltercount2 = 0 then
				exttrigger2 <= '0';
			end if;
			
			rateaccum <= rateaccum + rateaccumreg;

			case startselect1 is
				when "000" => 
					run1 <= '0';							-- cancel any pulse in progress
				when "001" => trigger1 <= swtrigger1;
				when "010" => trigger1 <= exttrigger1;
				when "011" => trigger1 <= dplltrigger;
				when "100" => trigger1 <= ratemsb;
				when "101" => trigger1 <= run1;
				when "110" => trigger1 <= run2;
				when others => 
					run1 <= '0';
			end case;	

			case startselect2 is
				when "000" => 
					run2 <= '0';							-- cancel any pulse in progress
				when "001" => trigger2 <= swtrigger2;
				when "010" => trigger2 <= exttrigger2;
				when "011" => trigger2 <= dplltrigger;
				when "100" => trigger2 <= ratemsb;
				when "101" => trigger2 <= run1;
				when "110" => trigger2 <= run2;
				when others => 
					run2 <= '0';
			end case;	

			if reset1 = '1' then
				run1 <= '0';
			end if;	
			
			if run1 = '1' then
				if pw1countmsb = '0' then
					pw1count <= pw1count -1;
				end if;
			end if;
			if pw1countmsb = '1' then	-- end of pulse
				run1 <= '0';
			end if;
			if (run1 = '0') then
				pw1count(31 downto 0)  <= pw1;
				pw1countmsb <='0';
			end if;		
			
			if reset2 = '1' then
				run2 <= '0';
			end if;	
			
			if run2 = '1' then
				if pw2countmsb = '0' then
					pw2count <= pw2count -1;
				end if;
			end if;
			if pw2countmsb = '1' then-- end of pulse
				run2 <= '0';
			end if;
			if (run2 = '0') then
				pw2count(31 downto 0)  <= pw2;
				pw2countmsb <='0';
			end if;		
			
			if (startrise1 = '1' and trigger1 = '1' and triggerd1='0' and enable1='1')
			or (startfall1 = '1' and trigger1 = '0' and triggerd1='1' and enable1='1') then
				if retrigger1 = '1' then
					run1 <= '1';
					pw1count(31 downto 0) <= pw1;		-- reload timer if retriggerable
				    pw1countmsb <='0';
				else
					if run1 = '0' then
						run1 <= '1';
					end if;
				end if;		
			end if;

			if (startrise2 = '1' and trigger2 = '1' and triggerd2='0' and enable2='1')
			or (startfall2 = '1' and trigger2 = '0' and triggerd2='1' and enable2='1') then
				if retrigger2 = '1' then
					run2 <= '1';
					pw2count(31 downto 0) <= pw2;		-- reload timer if retriggerable
				    pw2countmsb <='0';				
                else
					if run2 = '0' then
						run2 <= '1';
					end if;
				end if;		
			end if;
			
			if loadcontrol =  '1' then 
				controlreg <= ibus(31 downto 0);
			end if;	
			
			if loadpw1 = '1' then
				pw1 <= ibus;
			end if;

			if loadpw2 = '1' then
				pw2 <= ibus;
			end if;

			if loadfilter1 = '1' then
				trigfilterreg1 <= ibus(23 downto 0);
			end if;

			if loadfilter2 = '1' then
				trigfilterreg2 <= ibus(23 downto 0);
			end if;

			if loadrate = '1' then
				rateaccumreg <= ibus;
			end if;				
		
		end if;	-- clk

		case timerselect(2 downto 0) is
			when "000" => dplltrigger <= timers(0);
			when "001" => dplltrigger <= timers(1);
			when "010" => dplltrigger <= timers(2);
			when "011" => dplltrigger <= timers(3);
			when "100" => dplltrigger <= timers(4);	
			when others => dplltrigger <= timers(0);
		end case;

		obus <= (others => 'Z');     
		if readcontrol = '1' then
			obus(7 downto 0) <= controlreg(7 downto 0);
			obus(8)  <= run1;
			obus(9)  <= exttrigger1;  
			obus(10) <= swtrigger1;  
			obus(15 downto 12) <= timerselect;
			obus(23 downto 16) <= controlreg(23 downto 16);
			obus(24) <= run2;
			obus(25) <= exttrigger2;
			obus(26) <= swtrigger2;
			obus(31 downto 27) <= (others => '0');		-- zero unused readback bits		
			obus(11) <= '0';		
		end if;	

		pulse1out <= run1;
		pulse2out <= run2;

	 end process;
		
end Behavioral;
