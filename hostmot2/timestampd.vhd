library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;

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


entity timestampd is
    Port ( ibus : in std_logic_vector(15 downto 0);
           obus : out std_logic_vector(15 downto 0);
			  loadtsdiv : in std_logic;
           readts : in std_logic;
			  readtsdiv : in std_logic;
			  tscount : out std_logic_vector (15 downto 0);
			  timer : in std_logic;
			  timerenable : in std_logic;
           clk : in std_logic);
end timestampd;

architecture Behavioral of timestampd is

signal counter: std_logic_vector(15 downto 0);
signal counterlatch: std_logic_vector(15 downto 0);
signal sample: std_logic;
signal dtimer: std_logic;
signal div: std_logic_vector(15 downto 0);
alias divmsb: std_logic is div(15);
signal divlatch: std_logic_vector (15 downto 0);

begin

	atimestamp: process (clk,readts, counter, readtsdiv, divlatch,timer, dtimer, counterlatch)
	begin
		if rising_edge(clk) then
			div <= div -1;
			if divmsb = '1' then
				div <= divlatch;
		      counter <= counter + 1;
			end if;
			if sample = '1' then		-- sample counter on DPLL
				counterlatch <= counter;
			end if;	
			if loadtsdiv = '1' then
				divlatch <= ibus;
			end if;
			dtimer <= timer;
	 	end if; -- clk
		
		if (timer = '1' and dtimer = '0') or (timerenable = '0') then 		-- rising edge of selected timer
			sample <= '1';
		else
			sample <= '0';
		end if;

		obus <= (others => 'Z');
		if readts = '1' then
			obus <= counterlatch;	-- host reads get the DPLL sampled timestamp
		end if;
		if readtsdiv = '1' then
			obus <= divlatch;			
		end if;	 
	 tscount <= counter;				-- encoders get the live timestamp
	 end process;
		
end Behavioral;
