`timescale 1ns / 1ps

module led7219(
	input wire clk,
	input wire [255:0] data,
	output wire leds_out,
	output reg leds_clk,
	output reg leds_cs = 1
);

localparam ST_SCAN = 0;
localparam ST_INTENSITY = 1;
localparam ST_NORMAL = 2;
localparam ST_TEST = 3;
localparam ST_DATA1 = 4;
localparam ST_DATA2 = 5;
localparam ST_DATA3 = 6;
localparam ST_DATA4 = 7;
localparam ST_DATA5 = 8;
localparam ST_DATA6 = 9;
localparam ST_DATA7 = 10;
localparam ST_DATA8 = 11;

reg [5:0] clk_div = 0;
reg [3:0] state = 0;
reg [6:0] bit_cnt = 0;
reg [63:0] dout = 0;

assign leds_out = dout[63];

always @(posedge clk) begin
	clk_div <= clk_div + 5'b1;
	leds_clk <= clk_div[5];
	if (clk_div == 0) begin
		if (bit_cnt == 0)
			leds_cs <= 0;
		else if (bit_cnt == 64)
			leds_cs <= 1;

		if (bit_cnt == 0) begin
			case (state)
			ST_SCAN: begin
				dout <= 64'h0b07_0b07_0b07_0b07;
				state <= ST_INTENSITY;
			end
			ST_INTENSITY: begin
				dout <= 64'h0a07_0a07_0a07_0a07;
				state <= ST_NORMAL;
			end
			ST_NORMAL: begin
				dout <= 64'h0c01_0c01_0c01_0c01;
				state <= ST_TEST;
			end
			ST_TEST: begin
				dout <= 64'h0f00_0f00_0f00_0f00;
				state <= ST_DATA1;
			end
			ST_DATA1: begin
				dout <= {
					8'h01, data[255:248],
					8'h01, data[247:240],
					8'h01, data[239:232],
					8'h01, data[231:224]
				       };
				state <= ST_DATA2;
			end
			ST_DATA2: begin
				dout <= {
					8'h02, data[223:216],
					8'h02, data[215:208],
					8'h02, data[207:200],
					8'h02, data[199:192]
				       };
				state <= ST_DATA3;
			end
			ST_DATA3: begin
				dout <= {
					8'h03, data[191:184],
					8'h03, data[183:176],
					8'h03, data[175:168],
					8'h03, data[167:160]
				       };
				state <= ST_DATA4;
			end
			ST_DATA4: begin
				dout <= {
					8'h04, data[159:152],
					8'h04, data[151:144],
					8'h04, data[143:136],
					8'h04, data[135:128]
				       };
				state <= ST_DATA5;
			end
			ST_DATA5: begin
				dout <= {
					8'h05, data[127:120],
					8'h05, data[119:112],
					8'h05, data[111:104],
					8'h05, data[103: 96]
				       };
				state <= ST_DATA6;
			end
			ST_DATA6: begin
				dout <= {
					8'h06, data[ 95: 88],
					8'h06, data[ 87: 80],
					8'h06, data[ 79: 72],
					8'h06, data[ 71: 64]
				       };
				state <= ST_DATA7;
			end
			ST_DATA7: begin
				dout <= {
					8'h07, data[ 63: 56],
					8'h07, data[ 55: 48],
					8'h07, data[ 47: 40],
					8'h07, data[ 39: 32]
				       };
				state <= ST_DATA8;
			end
			ST_DATA8: begin
				dout <= {
					8'h08, data[ 31: 24],
					8'h08, data[ 23: 16],
					8'h08, data[ 15:  8],
					8'h08, data[  7:  0]
				       };
				state <= ST_SCAN;
			end
			endcase
		end else begin
			dout <= { dout[62:0], 1'b1 };
		end
		if (bit_cnt == 68)
			bit_cnt <= 0;
		else
			bit_cnt <= bit_cnt + 7'b1;
	end
end
endmodule
