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

entity periodm is
	port ( 
			clk : in std_logic;
			ibus : in  std_logic_vector (31 downto 0);
			obus : out  std_logic_vector (31 downto 0);
			loadmode : in  std_logic;
			readmode : in std_logic;
			loadlimit : in std_logic;
			readlimit : in std_logic;
			readperiod : in std_logic;	
			readwidth : in std_logic;	
			input : in std_logic
		  );
end periodm;

architecture Behavioral of periodm is
signal ptimer: std_logic_vector(31 downto 0); 
signal wtimer: std_logic_vector(31 downto 0); 
signal periodlatch: std_logic_vector(31 downto 0); 
signal periodoutlatch: std_logic_vector(31 downto 0);
signal periodlimit: std_logic_vector(31 downto 0); 
signal prewidthlatch: std_logic_vector(31 downto 0);
signal widthlatch: std_logic_vector(31 downto 0);
signal widthoutlatch: std_logic_vector(31 downto 0);
signal filtercount: std_logic_vector(15 downto 0);
signal avecount: std_logic_vector(11 downto 0);
signal modereg: std_logic_vector(31 downto 0);
alias  polarity : std_logic is modereg(0);
alias  filterreg: std_logic_vector(15 downto 0) is modereg(31 downto 16);
alias  avecountreg: std_logic_vector(11 downto 0) is modereg(15 downto 4);
signal inputd: std_logic;
signal filtoutput: std_logic;
signal filtoutputd: std_logic;
signal filtoutputdd: std_logic;
signal valid: std_logic;
signal periodvalid: std_logic;

begin
	aperiodm: process (clk,readmode,modereg,inputd,readperiod,readwidth,
	                   periodoutlatch,widthoutlatch,readlimit,periodlimit)
	begin
		if rising_edge(clk) then            

			inputd <= polarity xor input;		


			if ptimer < periodlimit then		-- check if the input frequency is high enough
				ptimer <= ptimer + 1;				-- and dead-end the timer
				periodvalid <= '1';
			end if;
			if ptimer = periodlimit then		-- if stuck at limit = no signal, period is invalid		
				periodvalid <= '0';
				valid <= '0';							-- invalidate status immediately
			end if;		
						
			if (inputd = '1') and (filtercount < filterreg) then	-- digital filter on input
				filtercount <= filtercount + 1;							-- note: this does not change period/width
			end if;																-- but will limit minimum pulse width
			if (inputd = '0') and (filtercount /= 0) then 
				filtercount <= filtercount -1;
			end if;
			if filtercount >= filterreg then
				filtoutput <= '1';
			end if;
			if filtercount = 0 then
				filtoutput <= '0';
			end if;
			filtoutputd <= filtoutput;

         if filtoutput = '1' then
				wtimer <= wtimer +1;
			end if;
		
			if filtoutput = '1' and filtoutputd = '0' then 	-- on rising edge of input for period
				valid <= periodvalid;
				if avecount = 0 then
					periodlatch <= ptimer;
					avecount <= avecountreg;
					widthlatch <= prewidthlatch;					-- likewise with width average	
					ptimer <= x"00000000";
					wtimer <= x"00000000";
				else
					avecount <= avecount -1;
				end if;	 

			end if;
			
			if filtoutput = '0' and filtoutputd = '1' then -- on falling edge of input
				if avecount = 0 then
					prewidthlatch <= wtimer;
				end if;	
			end if;	
			
			if loadmode = '1' then
				modereg(31 downto 3) <= ibus(31 downto 3);
				modereg(0) <= ibus(0);
			end if;	
			if loadlimit = '1' then
				periodlimit <= ibus;
			end if;	
			if readmode = '1' then					-- latch our read data so period and width values 
				periodoutlatch <= periodlatch;	-- are synchronous. This requires that the mode 		
				widthoutlatch <= widthlatch;		-- register be read first
			end if;	
		end if;	-- clk
		
		obus <= (others => 'Z');     
		if readmode = '1' then
			obus(31 downto 3) <= modereg(31 downto 3);
			obus(2) <= inputd;
			obus(1) <= valid;
			obus(0) <= polarity;
		end if;	
		if readperiod = '1' then
			obus <= periodoutlatch;
--			obus <= timer;
		end if;	
		if readwidth = '1' then
			obus <= widthoutlatch;
		end if;	
		if readlimit = '1' then
			obus <= periodlimit;
		end if;	

	end process;
		
end Behavioral;
