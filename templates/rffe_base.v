//===========================================
// global var      
//===========================================
`define  SCLK_PERIOD_PARA       (1923/2)/100 
`define  NRF                    9'b1000_0000_0
`define  CMD_PARITY_ERR_YES     7'b100_0000
`define  CMD_PARITY_ERR_NO      7'b000_0000
`define  CMD_LEN_ERR_YES     		7'b010_0000
`define  CMD_LEN_ERR_NO      		7'b000_0000
`define  ADDRL_PARITY_ERR_YES   7'b001_0000
`define  ADDRL_PARITY_ERR_NO    7'b000_0000
`define  DATA_PARITY_ERR_YES    7'b000_1000
`define  DATA_PARITY_ERR_NO     7'b000_0000

`define FSDB
class packet;
	randc bit [7:0] data_packet;
	function new(int seed);
		this.srandom(seed);
	endfunction 
endclass

class packet_two;
	randc bit [7:0] data_two_packet;
	function new(int seed);
		this.srandom(seed);
	endfunction
endclass
packet packet_rand;
packet_two packet_rand_two;
integer cmd_cnt;
integer i,j,k;

tri0 sclk_test;
tri0 sdata_test;

wire           sdata_out; //
wire           sdata_oe;

integer err_cnt;
initial begin
	err_cnt = 0;
	cmd_cnt = 0;
end

integer sclk_period;

initial begin
	sclk_period      = `SCLK_PERIOD_PARA; //19.23ns
end

reg trigger_clk;//           
initial begin
	trigger_clk = 1'b0;
end
always #100000  trigger_clk = ~trigger_clk ; //9600hz

reg sys_rstn;
initial begin
	sys_rstn = 1'b0;
	#200
	sys_rstn = 1'b1;
end

//===========================================
// Module Instance      
//===========================================

 mipi_core mipi_slave(/*autoinst*/
        //Inputs
        .usid_in           ( usid_user[3:0]          ),  
        .product_id_in     ( product_id_user[7:0]    ),
        .man_id_lsb_in     ( man_id_user[7:0]        ),
        .man_id_msb_in     ( man_id_user[11:8]       ),
        .ext_product_id_in ( ext_product_id_user[7:0]),
        .gsid0_din         ( gusid0_user[3:0]        ),
        .gsid1_din         ( gusid1_user[3:0]        ),
        .revision_id_in    ( revision_id_user[7:0]   ),
        .pm_default_in     ( pm_default_user         ),
        .busld_default_in  ( busld_user[3:0]         ),
        .sdata_in          ( sdata_test              ),
        .sdata_in1         ( sdata_test              ),
        .rst_n             ( sys_rstn                ),
        .sclk              ( sclk_test               ),
        //.sclk1             ( sclk0                   ),
        //.VDD            ( 1'b1      ),
        //.VSS            ( 1'b0      ),
        //Outputs
        .sdata_out      ( sdata_out ),
        .sdata_oe       ( sdata_oe  ));

// reg_logic reg_logic(/*autoinst*/
//        //Inputs
//        .reg01    (8'h34    ),
//        .reg02    (8'h00    ),
//        .reg03    (8'h00    ),
//        .reg53    (8'h00    ),
//        .reg54    (8'h00    ),
//        .reg55    (8'h00    ),
//        .pm       (1'b0          ));
//
 
//===========================================
// SCLK PERIOD SELECT      
//===========================================
task sclk_sel;
input [5:0] sel;
	if(sel == 1)//52M
		sclk_period = `SCLK_PERIOD_PARA;
	else if(sel == 2)//26M
		sclk_period = `SCLK_PERIOD_PARA * 2;
	else if(sel == 3)//13M
		sclk_period = `SCLK_PERIOD_PARA * 4;
	else if(sel == 4)//6.5M
		sclk_period = `SCLK_PERIOD_PARA * 8;
	else if(sel == 5)//3.25M
		sclk_period = `SCLK_PERIOD_PARA * 16;
	else if(sel == 6)//1.625M
		sclk_period = `SCLK_PERIOD_PARA * 32;
	else if(sel == 7)//0.8125M
		sclk_period = `SCLK_PERIOD_PARA * 64;
	else//0.40625M
		sclk_period = `SCLK_PERIOD_PARA * 128;
endtask

//===========================================
// SSC - Sequence Start Condition
//===========================================
//                              _    _    _    _
// SCLK  ______________________| |__| |__| |__| |__
//            ________          ____ ____ ____ ____
// SDATA ____|        |________|_S3_|_S2_|_S1_|_S0_|
//
task ssc;
	//force sclk_test = 0; force sdata_test = 0; #(sclk_period*1); 
	force sclk_test = 0; force sdata_test = 1; #(sclk_period*2); 
	force sclk_test = 0; force sdata_test = 0; #(sclk_period*2); 
	release sclk_test;
	release sdata_test;
endtask
//===========================================
// Bit Send      
//===========================================
//           _    _    _    _
// SCLK  ___| |__| |__| |__| |__
//           ____ ____ ____ ____
// SDATA ___|_D3_|_D2_|_D1_|_D0_|
task bit_send;
input bit_data;
	if(bit_data==1'b1) begin
		force sclk_test = 1; force sdata_test = 1; #(sclk_period*1); 
		force sclk_test = 0; force sdata_test = 1; #(sclk_period*1); 
	end
	else begin	
		force sclk_test = 1; force sdata_test = 0; #(sclk_period*1); 
		force sclk_test = 0; force sdata_test = 0; #(sclk_period*1); 
	end
	release sclk_test;
	release sdata_test;
endtask
//===========================================
// Bit Receive   
//===========================================
//              _    _    _    _
// SCLK (M) ___| |__| |__| |__| |__
//              ____ ____ ____ ____
// SDATA(S) ___|_D3_|_D2_|_D1_|_D0_|
task bit_receive;
output bit_data;
	//if(sdata_oe) begin
		force sclk_test = 1; #(sclk_period*1); 
		bit_data = sdata_out && sdata_oe;	
		//$display("sunyuan:%b",bit_data);
		force sclk_test = 0; #(sclk_period*1); 
	//end
	//else begin
	//	force sclk_test = 1; #(sclk_period*1); 
	//	bit_data = 1'b0;	
	//	force sclk_test = 0; #(sclk_period*1); 
	//end
	release sclk_test;
endtask
//===========================================
// Slave Addr Send      
//===========================================
//           _    _    _    _      
// SCLK  ___| |__| |__| |__| |__ 
//           ____ ____ ____ ____
// SDATA ___|_S3_|_S2_|_S1_|_S0_|
task sa_send;
input [3:0] sa;
integer i;
	for(i=0;i<=3;i=i+1)begin
		bit_send(sa[(3-i)]);
	end
endtask
//===========================================
// Data Send      
//===========================================
//           _    _    _    _    _    _    _    _    _    
// SCLK  ___| |__| |__| |__| |__| |__| |__| |__| |__| |__
//           ____ ____ ____ ____ ____ ____ ____ ____ ____ 
// SDATA ___|_D7_|_D6_|_D5_|_D4_|_D3_|_D2_|_D1_|_D0_|__P_|
task data_send;
input [7:0] data;
input       data_parity_err;
input       interrupt_ssc_stop;
integer i;
bit data_parity;
	for(i=0;i<=7;i=i+1)begin
		bit_send(data[(7-i)]);
	end
	// parity(data)
	if(data_parity_err==1'b1)
		data_parity =  (^data[7:0]);
	else
		data_parity = ~(^data[7:0]);
	if(interrupt_ssc_stop==1'b0)
		bit_send(data_parity);	
endtask
//===========================================
// CMD Data Send      
//===========================================
//           _    _    _    _    _    _    _    _    _    _    _    _    _    
// SCLK  ___| |__| |__| |__| |__| |__| |__| |__| |__| |__| |__| |__| |__| |__
//           ____ ____ ____ ____ ____ ____ ____ ____ ____ ____ ____ ____ ____ 
// SDATA ___|_S3_|_S2_|_S1_|_S0_|_D7_|_D6_|_D5_|_D4_|_D3_|_D2_|_D1_|_D0_|__P_|
task cmd_data_send;
input [11:0] data;
input cmd_parity_err;
input interrupt_ssc_stop;
integer i;
bit cmd_parity;
	//sa
	sa_send(data[11:8]);
	//cmd + data
	for(i=0;i<=7;i=i+1)begin
		bit_send(data[(7-i)]);
	end
	// parity(sa+cmd+data)
	if(cmd_parity_err == 1'b0)
		cmd_parity = ~(^data[11:0]);
	else
		cmd_parity =  (^data[11:0]);
	if(interrupt_ssc_stop==1'b0)
		bit_send(cmd_parity);	
endtask
//===========================================
// BPC - Bus Park Cycle      
//===========================================
//        _    _    _
// SCLK  | |__| |__| |______
//        ____ ____ 
// SDATA |_D0_|__P_|________
task bpc;
	bit_send(1'b0);
endtask
//===========================================
// BPC - Silend Bus Park Cycle      
//===========================================
//        _    _    _
// SCLK  | |__| |__| |______
//        ____ ____ 
// SDATA |_D0_|__P_|________
task bpc_silent;
	force sclk_test = 0; force sdata_test = 0; #(sclk_period); 
	force sclk_test = 0; force sdata_test = 0; #(sclk_period); 
	release sclk_test;
	release sdata_test;
endtask
//===========================================
// Data Receive   
//===========================================
//              _    _    _    _    _    _    _    _    _    
// SCLK (M) ___| |__| |__| |__| |__| |__| |__| |__| |__| |__
//              ____ ____ ____ ____ ____ ____ ____ ____ ____ 
// SDATA(S) ___|_D7_|_D6_|_D5_|_D4_|_D3_|_D2_|_D1_|_D0_|__P_|
task data_receive;
output [7:0] data;
output       no_response;
integer i;
bit data_parity;
	//rdata[7:0]
	for(i=0;i<=7;i=i+1)begin
		bit_receive(data[(7-i)]);
	end
	//parity(rdata[7:0])
	bit_receive(data_parity);
	//No Response?
	if({data[7:0],data_parity}==9'b0000_0000_0)
		no_response = 1'b1;
	else
		no_response = 1'b0;
	//Parity true?
	if(no_response==1'b0) begin
		if((~(^data[7:0]))!=data_parity)
			data[7:0] = 8'b0000_0000;
	end
endtask
//===========================================
// reg0_write      
//===========================================
//exampl : reg0_write(8'h0A,8'h55);
//				sa[3:0]    : slave_addr
//				wdata[7:0] : write data ,but valid [6:0]
task reg0_write_pre;
input [7:0] sa ;
input [7:0] wdata;
input [6:0] err_sum;
integer i;
bit cmd_parity_err  	;
bit cmd_len_err     	;//interrupted by ssc
bit addrl_parity_err	;//addrl parity error
bit data_parity_err 	;//first wdata data_mask
		cmd_parity_err  	= err_sum[6];
		cmd_len_err     	= err_sum[5];
		addrl_parity_err	= err_sum[4];
		data_parity_err 	= err_sum[3];

		cmd_cnt = cmd_cnt + 1'b1;
		$display("////////////////////////////////");
		$display("//   CMD_CNT    : %d          ",cmd_cnt);
		$display("//   CMD        : REG0_WRITE    ");
		$display("//   SLAVE_ADDR : 'h%2H         ",sa[3:0]);
		$display("//   REG_ADDR   : 'h00          ");
		$display("//   WRITE_DATA : 'h%2H         ",wdata[6:0]);
		$display("////////////////////////////////");
		//ssc
		ssc;
		//sa[3:0] + reg0_write CMD Code + wdata[6:0] Send
		cmd_data_send({sa[3:0],1'b1,wdata[6:0]},cmd_parity_err,cmd_len_err);
		if(cmd_len_err==1'b0)begin
		//BPC
		bpc;
		end
endtask

task reg0_write;
input [7:0] sa ;
input [7:0] wdata;
	reg0_write_pre(sa[7:0],wdata[7:0],`CMD_PARITY_ERR_NO);
endtask

task reg0_write_cmd_parity_err;
input [7:0] sa ;
input [7:0] wdata;
		$display("////////////////////////////////");
		$display("////////CMD PARITY ERROR////////");
		$display("////////////////////////////////");
	reg0_write_pre(sa[7:0],wdata[7:0],`CMD_PARITY_ERR_YES);
endtask

task reg0_write_cmd_len_err;
input [7:0] sa ;
input [7:0] wdata;
		$display("/////////////////////////////////////////////");
		$display("////////CMD LEN ERROR WITH CMD_PARITY////////");
		$display("/////////////////////////////////////////////");
	reg0_write_pre(sa[7:0],wdata[7:0],`CMD_LEN_ERR_YES);
endtask
//===========================================
// reg_write      
//===========================================
//exampl : reg_write(8'h0A,8'h04,8'h55);
//				sa[3:0]        : slave_addr
//				reg_addrl[4:0] : slave reg_addr
//				wdata[7:0]     : write data
task reg_write_pre;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] wdata;
input [6:0] err_sum;
bit cmd_parity_err  	;
bit cmd_len_err     	;//interrupted by ssc
bit addrl_parity_err	;//addrl parity error
bit data_parity_err 	;//first wdata data_mask
		cmd_parity_err  	= err_sum[6];
		cmd_len_err     	= err_sum[5];
		addrl_parity_err	= err_sum[4];
		data_parity_err 	= err_sum[3];
		cmd_cnt = cmd_cnt + 1'b1;
		$display("////////////////////////////////");
		$display("//   CMD_CNT    : %d          ",cmd_cnt);
		$display("//   CMD        : REG_WRITE     ");
		$display("//   SLAVE_ADDR : 'h%2H         ",sa[3:0]);
		$display("//   REG_ADDR   : 'h%2H         ",reg_addrl[4:0]);
		$display("//   WRITE_DATA : 'h%2H         ",wdata[7:0]);
		$display("////////////////////////////////");
		//ssc
		ssc;
		//sa[3:0] + reg_write CMD Code + addrl[4:0] Send
		cmd_data_send({sa[3:0],3'b010,reg_addrl[4:0]},cmd_parity_err,1'b0);
		//wdata[7:0] send
		data_send(wdata[7:0],data_parity_err,cmd_len_err);
		if(cmd_len_err==1'b0) begin
		//BPC
		bpc;
		end
endtask

task reg_write;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] wdata;
		reg_write_pre(sa[7:0],reg_addrl[7:0],wdata[7:0],`CMD_PARITY_ERR_NO);
endtask

task reg_write_cmd_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] wdata;
		$display("////////////////////////////////");
		$display("////////CMD PARITY ERROR////////");
		$display("////////////////////////////////");
		reg_write_pre(sa[7:0],reg_addrl[7:0],wdata[7:0],`CMD_PARITY_ERR_YES);
endtask

task reg_write_cmd_len_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] wdata;
		$display("///////////////////////////////////////////////");
		$display("////////CMD LEN ERROR WITH WDATA_PARITY////////");
		$display("///////////////////////////////////////////////");
		reg_write_pre(sa[7:0],reg_addrl[7:0],wdata[7:0],`CMD_LEN_ERR_YES);
endtask

task reg_write_data_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] wdata;
		$display("////////////////////////////////");
		$display("////////DATA PARITY ERROR///////");
		$display("////////////////////////////////");
		reg_write_pre(sa[7:0],reg_addrl[7:0],wdata[7:0],`DATA_PARITY_ERR_YES);
endtask
//===========================================
// ext_reg_write      
//===========================================
//exampl : ext_reg_write(8'h0A,8'h88,8'h04,{8'h55,8'h00,8'h55,8'h00,8'hFF});
//				sa[3:0]           : slave_addr
//				reg_addrl[7:0]    : slave reg_addr
//				bc[3:0]           : Write data number
//				wdata[15:0][7:0]  : write data
task ext_reg_write_pre;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [7:0] wdata; 
input [6:0] err_sum;
integer k;
bit cmd_parity_err  	;
bit cmd_len_err     	;//interrupted by ssc
bit addrl_parity_err	;//addrl parity error
bit data_parity_err 	;//first wdata data_mask
		cmd_parity_err  	= err_sum[6];
		cmd_len_err     	= err_sum[5];
		addrl_parity_err	= err_sum[4];
		data_parity_err 	= err_sum[3];
		cmd_cnt = cmd_cnt + 1'b1;

		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("////");
		end
		$display;
		$display("//   CMD_CNT       : %d          ",cmd_cnt);
		$display("//   CMD           : EXT_REG_WRITE               ");
		$display("//   SLAVE_ADDR    : 'h%1H                      ",sa[3:0]);
		$display("//   WRITE_NUM     : 'd%2d                      ",(bc[3:0]+1));
		$write  ("//   REG_ADDR_NUM  : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("'d%2d |",(k[3:0]));
		end
		$display;
		$write  ("//   REG_ADDR      : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
			if((reg_addrl[7:0]+k[3:0])>='h100)
				$write("'hff |");
			else
				$write("'h%2H |",(reg_addrl[7:0]+k[3:0]));
		end
		$display;
		$write  ("//   WDATA         : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("'h%2H |",wdata[(bc[3:0]-k[3:0])]);
		end
		$display;
		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("////");
		end
		$display;

		//ssc
		ssc;
		//sa[3:0] + ext_reg_write CMD Code + bc[3:0] Send
		cmd_data_send({sa[3:0],4'b0000,bc[3:0]},cmd_parity_err,1'b0);
		//addrl[7:0] send
		data_send(reg_addrl[7:0],addrl_parity_err,cmd_len_err);
		if(cmd_len_err==1'b0)begin
		//wdata[7:0] send
		for (k=0;k<=bc[3:0];k=k+1) begin
			if(k==0)
				data_send(wdata[(bc[3:0]-k[3:0])],data_parity_err,1'b0);
			else
				data_send(wdata[(bc[3:0]-k[3:0])],1'b0,1'b0);
		end
		//BPC
		bpc;
		end
endtask

task ext_reg_write;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [7:0] wdata; 
		ext_reg_write_pre(sa[7:0],reg_addrl[7:0],bc[7:0],wdata,`CMD_PARITY_ERR_NO);
endtask

task ext_reg_write_cmd_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////CMD PARITY ERROR////////");
		$display("////////////////////////////////");
		ext_reg_write_pre(sa[7:0],reg_addrl[7:0],bc[7:0],wdata,`CMD_PARITY_ERR_YES);
endtask

task ext_reg_write_cmd_len_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [7:0] wdata; 
		$display("///////////////////////////////////////////////");
		$display("////////CMD LEN ERROR WITH ADDRL_PARITY////////");
		$display("///////////////////////////////////////////////");
		ext_reg_write_pre(sa[7:0],reg_addrl[7:0],bc[7:0],wdata,`CMD_LEN_ERR_YES);
endtask

task ext_reg_write_addrl_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////ADDRL PARITY ERROR//////");
		$display("////////////////////////////////");
		ext_reg_write_pre(sa[7:0],reg_addrl[7:0],bc[7:0],wdata,`ADDRL_PARITY_ERR_YES);
endtask

task ext_reg_write_data_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////WDATA PARITY ERROR////////");
		$display("////////////////////////////////");
		ext_reg_write_pre(sa[7:0],reg_addrl[7:0],bc[7:0],wdata,`DATA_PARITY_ERR_YES);
endtask

//===========================================
// ext_reg_write_long      
//===========================================
//exampl : ext_reg_write_long(8'h0A,8'h88,8'h04,{8'h55,8'h00,8'h55,8'h00,8'hFF});
//				sa[3:0]           : slave_addr
//				reg_addr[15:0]    : slave reg_addr
//				bc[3:0]           : Write data number
//				wdata[15:0][7:0]  : write data
task ext_reg_write_long_pre;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [7:0] wdata; 
input [6:0] err_sum;
integer k;
bit cmd_parity_err  	;
bit cmd_len_err     	;//interrupted by ssc
bit addrl_parity_err	;//addrl parity error
bit data_parity_err 	;//first wdata data_mask
		cmd_parity_err  	= err_sum[6];
		cmd_len_err     	= err_sum[5];
		addrl_parity_err	= err_sum[4];
		data_parity_err 	= err_sum[3];

		cmd_cnt = cmd_cnt + 1'b1;
		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("////");
		end
		$display;
		$display("//   CMD_CNT       : %d          ",cmd_cnt);
		$display("//   CMD           : EXT_REG_WRITE_LONG          ");
		$display("//   SLAVE_ADDR    : 'h%1H                      ",sa[3:0]);
		$display("//   WRITE_NUM     : 'd%1d                      ",(bc[2:0]+1));
		$write  ("//   REG_ADDR_NUM  : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("'d%1d    |",(k[2:0]));
		end
		$display;
		$write  ("//   REG_ADDR      : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
			if((reg_addr[15:0]+k[2:0])>='hFFFF)
				$write("'hffff |");
			else
				$write("'h%4H |",(reg_addr[15:0]+k[2:0]));
		end
		$display;
		$write  ("//   WDATA         : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("'h%2H   |",wdata[(bc[2:0]-k[2:0])]);
		end
		$display;
		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("////");
		end
		$display;

		//ssc
		ssc;
		//sa[3:0] + ext_reg_write_long CMD Code + bc[3:0] Send
		cmd_data_send({sa[3:0],5'b00110,bc[2:0]},cmd_parity_err,1'b0);
		//addrh[7:0] send
		data_send(reg_addr[15:8],1'b0,cmd_len_err);
		if(cmd_len_err==1'b0)begin
		//addrl[7:0] send
		data_send(reg_addr[7:0],addrl_parity_err,1'b0);
		//wdata[7:0] send
		for (k=0;k<=bc[2:0];k=k+1) begin
			if(k==0)
				data_send(wdata[(bc[2:0]-k[2:0])],data_parity_err,1'b0);
			else
				data_send(wdata[(bc[2:0]-k[2:0])],1'b0,1'b0);
		end
		//BPC
		bpc;
		end

endtask

task ext_reg_write_long;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [7:0] wdata; 
		ext_reg_write_long_pre(sa[7:0],reg_addr[15:0],bc[7:0],wdata,`CMD_PARITY_ERR_NO);
endtask

task ext_reg_write_long_cmd_parity_err;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////CMD PARITY ERROR////////");
		$display("////////////////////////////////");
		ext_reg_write_long_pre(sa[7:0],reg_addr[15:0],bc[7:0],wdata,`CMD_PARITY_ERR_YES);
endtask

task ext_reg_write_long_cmd_len_err;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [7:0] wdata; 
		$display("///////////////////////////////////////////////");
		$display("////////CMD LEN ERROR WITH AADRH_PARITY////////");
		$display("///////////////////////////////////////////////");
		ext_reg_write_long_pre(sa[7:0],reg_addr[15:0],bc[7:0],wdata,`CMD_LEN_ERR_YES);
endtask

task ext_reg_write_long_addrl_parity_err;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////ADDRL PARITY ERROR//////");
		$display("////////////////////////////////");
		ext_reg_write_long_pre(sa[7:0],reg_addr[15:0],bc[7:0],wdata,`ADDRL_PARITY_ERR_YES);
endtask

task ext_reg_write_long_data_parity_err;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////WDATA PARITY ERROR//////");
		$display("////////////////////////////////");
		ext_reg_write_long_pre(sa[7:0],reg_addr[15:0],bc[7:0],wdata,`DATA_PARITY_ERR_YES);
endtask

//===========================================
// masked_write      
//===========================================
//exampl : masked_write(8'h0A,8'h88,8'hFF,8'h55);
//				sa[3:0]           : slave_addr
//				reg_addrl[7:0]    : slave reg_addr
//				data_mask[7:0]    : data mask
//				wdata[7:0]        : write data
task masked_write_pre;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] data_mask; 
input [7:0] wdata; 
input [6:0] err_sum;
bit cmd_parity_err  	;
bit cmd_len_err     	;//interrupted by ssc
bit addrl_parity_err	;//addrl parity error
bit data_parity_err 	;//first wdata data_mask
		cmd_parity_err  	= err_sum[6];
		cmd_len_err     	= err_sum[5];
		addrl_parity_err	= err_sum[4];
		data_parity_err 	= err_sum[3];

		cmd_cnt = cmd_cnt + 1'b1;
		$display("///////////////////////////////////");
		$display("//   CMD_CNT      : %d          ",cmd_cnt);
		$display("//   CMD          : MASKED_WRITE   ");
		$display("//   SLAVE_ADDR   : 'h%1H          ",sa[3:0]);
		$display("//   REG_ADDR     : 'h%2H          ",reg_addrl[7:0]);
		$display("//   DATA_MASK    : 'h%2H          ",data_mask[7:0]);
		$display("//   WRITE_DATA   : 'h%2H          ",wdata[7:0]);
		$display("///////////////////////////////////");

		//ssc
		ssc;
		//sa[3:0] + masked_write CMD Code Send
		cmd_data_send({sa[3:0],8'b0001_1001},cmd_parity_err,1'b0);
		//reg_addrl[7:0] send
		data_send(reg_addrl[7:0],addrl_parity_err,1'b0);
		//mask_data[7:0] send
		data_send(data_mask[7:0],data_parity_err,cmd_len_err);
		if(cmd_len_err==1'b0)begin
		//wdata[7:0] send
		data_send(wdata[7:0],1'b0,1'b0);
		//BPC
		bpc;
		end

endtask

task masked_write;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] data_mask; 
input [7:0] wdata; 
		masked_write_pre(sa[7:0],reg_addrl[7:0],data_mask[7:0],wdata[7:0],`CMD_PARITY_ERR_NO);
endtask

task masked_write_cmd_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] data_mask; 
input [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////CMD PARITY ERROR////////");
		$display("////////////////////////////////");
		masked_write_pre(sa[7:0],reg_addrl[7:0],data_mask[7:0],wdata[7:0],`CMD_PARITY_ERR_YES);
endtask

task masked_write_cmd_len_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] data_mask; 
input [7:0] wdata; 
		$display("///////////////////////////////////////////////////");
		$display("////////CMD LEN ERROR WITH MASK_DATA_PARITY////////");
		$display("///////////////////////////////////////////////////");
		masked_write_pre(sa[7:0],reg_addrl[7:0],data_mask[7:0],wdata[7:0],`CMD_LEN_ERR_YES);
endtask

task masked_write_addrl_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] data_mask; 
input [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////ADDRL PARITY ERROR//////");
		$display("////////////////////////////////");
		masked_write_pre(sa[7:0],reg_addrl[7:0],data_mask[7:0],wdata[7:0],`ADDRL_PARITY_ERR_YES);
endtask

task masked_write_mdata_parity_err;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] data_mask; 
input [7:0] wdata; 
		$display("////////////////////////////////");
		$display("////////MASK DATA PARITY ERROR//");
		$display("////////////////////////////////");
		masked_write_pre(sa[7:0],reg_addrl[7:0],data_mask[7:0],wdata[7:0],`DATA_PARITY_ERR_YES);
endtask

//===========================================
// reg_read      
//===========================================
//exampl : reg_read(8'h0A,8'h04,rdata,no_response);
//				sa[3:0]        : slave_addr
//				reg_addrl[4:0] : slave reg_addr
//				rdata[7:0]     : read data
//        no_response    : no_response
task reg_read;
input [7:0] sa ;
input [7:0] reg_addrl ;
output [7:0] rdata ;
output       no_response ; 
		cmd_cnt = cmd_cnt + 1'b1;
		$display("////////////////////////////////");
		$display("//   CMD_CNT    : %d          ",cmd_cnt);
		$display("//   CMD        : REG_READ      ");
		$display("//   SLAVE_ADDR : 'h%1H         ",sa[3:0]);
		$display("//   REG_ADDR   : 'h%2H         ",reg_addrl[4:0]);
		//ssc
		ssc;
		//sa[3:0] + reg_read CMD Code + addrl[4:0] Send
		cmd_data_send({sa[3:0],3'b011,reg_addrl[4:0]},1'b0,1'b0);
		//BPC
		bpc;
		//rdata[7:0] receive
		data_receive(rdata[7:0],no_response);
		//BPC
		bpc;
		//Silent BPC
		bpc_silent;
		$display("//   READ_DATA  : 'h%2H         ",rdata[7:0]);
		if(no_response==1'b1)	
		$display("//   NRF        :  YES          ");
		else
		$display("//   NRF        :  NO           ");
		$display("////////////////////////////////");

endtask

//===========================================
// reg_read_chk      
//===========================================
//exampl : reg_read_chk(8'h0A,8'h04,9'h033);
//				sa[3:0]        : slave_addr
//				reg_addrl[4:0] : slave reg_addr
//				rdata[8:0]     : no_response + idle read data[7:0]
task reg_read_chk;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [8:0] rdata ;
bit [7:0] rdata_tmp;
bit no_response_tmp;
	reg_read(sa,reg_addrl,rdata_tmp[7:0],no_response_tmp);
	//expect no_response(NRF)?
	if(rdata[8:0]==`NRF) begin
		if((no_response_tmp==1'b0)||(rdata_tmp[7:0]!=rdata[7:0])) begin//Not NRF and read unequal idle
		$display("************************************************");
		$display("**   READ_DATA       : 'h%2H           ",rdata_tmp[7:0]);
		$display("**   IDLE_READ_DATA  : 'h%2H(NRF)      ",rdata[7:0]);
		$display("**   ERROR!!!  The Right Result Is NRF!!!       ");
		$display("************************************************");
		err_cnt = err_cnt + 1;	
		end	
	end
	else begin
		if(rdata[7:0]!=rdata_tmp[7:0]) begin
		$display("************************************************");
		$display("**   READ_DATA       : 'h%2H           ",rdata_tmp[7:0]);
		$display("**   IDLE_READ_DATA  : 'h%2H           ",rdata[7:0]);
		$display("**   ERROR!!!                                   ");
		$display("************************************************");
			err_cnt = err_cnt + 1;	
		end
		else begin
			if(no_response_tmp==1'b1) begin
			$display("************************************************");
			$display("**   ERROR!!! The Read REG_ADDR 'h%2H Result is NRF!!!         ",reg_addrl[7:0]);
			$display("************************************************");
			err_cnt = err_cnt + 1;	
			end
		end
	end
endtask

//===========================================
// ext_reg_read      
//===========================================
//exampl : ext_reg_read(8'h00,8'h88,8'h04,rdata,no_response);
//				sa[3:0]           : slave_addr
//				reg_addrl[7:0]    : slave reg_addr
//				bc[3:0]           : Write data number
//				rdata[15:0][7:0]  : read  data 
//				no_response[15:0] : no responsed
task ext_reg_read;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
output [15:0] [7:0] rdata; 
output [15:0]  no_response ; 
integer k;

		cmd_cnt = cmd_cnt + 1'b1;
		

		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("////");
		end
		$display;
		$display("//   CMD_CNT       : %d          ",cmd_cnt);
		$display("//   CMD           : EXT_REG_READ               ");
		$display("//   SLAVE_ADDR    : 'h%1H                      ",sa[3:0]);
		$display("//   READ_NUM      : 'd%2d                      ",(bc[3:0]+1));
		$write  ("//   REG_ADDR_NUM  : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("'d%2d |",(k[3:0]));
		end
		$display;
		$write  ("//   REG_ADDR      : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
			if((reg_addrl[7:0]+k[3:0])>='h100)
				$write("'hff |");
			else
				$write("'h%2H |",(reg_addrl[7:0]+k[3:0]));
		end
		$display;

		//ssc
		ssc;
		//sa[3:0] + ext_reg_read CMD Code + bc[3:0] Send
		cmd_data_send({sa[3:0],4'b0010,bc[3:0]},1'b0,1'b0);
		//addrl[7:0] send
		data_send(reg_addrl[7:0],1'b0,1'b0);
		//BPC
		bpc;
		//rdata[7:0] receive
		for (k=0;k<=bc[3:0];k=k+1) begin
			data_receive(rdata[k],no_response[k]);
		end
		//BPC
		bpc;
		//Silent BPC
		bpc_silent;

		$write  ("//   RDATA         : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("'h%2H |",rdata[(k[3:0])]);
		end
		$display;
		$write  ("//   NRF           : ");
		for (k=0;k<=bc[3:0];k=k+1) begin
			if(no_response[(k[3:0])]==1'b1)	
				$write(" YES |");
			else
				$write("  NO |");
		end
		$display;
		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[3:0];k=k+1) begin
				$write("////");
		end
		$display;

endtask

//===========================================
// ext_reg_read_chk      
//===========================================
//exampl : ext_reg_read_chk(8'h00,8'h88,8'h04,{9'h055,9'h000,9'h055,9'h000,9'h0FF});
//				sa[3:0]           : slave_addr
//				reg_addrl[7:0]    : slave reg_addr
//				bc[3:0]           : Write data number
//				rdata[15:0][8:0]  : no_responed + read  data ideal
task ext_reg_read_chk;
input [7:0] sa ;
input [7:0] reg_addrl ;
input [7:0] bc ;
input [15:0] [8:0] rdata; 
bit [15:0] [7:0] rdata_tmp;
bit [8:0] rdata_tmp_in;
bit [15:0] no_response_tmp;
integer k;
	ext_reg_read(sa,reg_addrl,bc,rdata_tmp,no_response_tmp);
			//$display("**  DEBUG            : 'h%H           ",rdata);
	

	for (k=0;k<=bc[3:0];k=k+1) begin
		rdata_tmp_in[8:0] = rdata[(bc[3:0]-k[3:0])];
		//expect no_response(NRF)?
		if(rdata_tmp_in[8:0]==`NRF) begin
			if((no_response_tmp[k]==1'b0)||(rdata_tmp[k]!=rdata_tmp_in[7:0])) begin//Not NRF and read unequal idle
			$display("************************************************");
			$display("**   REG_ADDR        : 'h%2H           ",(reg_addrl[7:0]+k[3:0]));
			$display("**   READ_DATA       : 'h%2H           ",rdata_tmp[k]);
			$display("**   IDLE_READ_DATA  : 'h%2H(NRF)      ",rdata_tmp_in[7:0]);
			$display("**   ERROR!!!  The Right Result Is NRF!!!       ");
			$display("************************************************");
			err_cnt = err_cnt + 1;	
			end	
		end
		else begin
			if((rdata_tmp[k]!=rdata_tmp_in[7:0])) begin
			$display("************************************************");
			$display("**   REG_ADDR        : 'h%2H           ",(reg_addrl[7:0]+k[3:0]));
			$display("**   READ_DATA       : 'h%2H           ",rdata_tmp[k]);
			$display("**   IDLE_READ_DATA  : 'h%2H           ",rdata_tmp_in[7:0]);
			$display("**   ERROR!!!                                   ");
			$display("************************************************");
				err_cnt = err_cnt + 1;	
			end
			else begin
				if(no_response_tmp[k]==1'b1) begin
				$display("************************************************");
				$display("**   ERROR!!! The Read REG_ADDR 'h%2H Result is NRF!!!         ",(reg_addrl[7:0]+k[3:0]));
				$display("************************************************");
				err_cnt = err_cnt + 1;	
				end
			end
		end
	end
endtask

//===========================================
// ext_reg_read_long      
//===========================================
//exampl : ext_reg_read_long(8'h00,16'h8888,8'h04,rdata,no_response);
//				sa[3:0]           : slave_addr
//				reg_addr[15:0]    : slave reg_addr
//				bc[2:0]           : Write data number
//				rdata[7:0][7:0]   : read  data 
//				no_response[15:0] : no responsed
task ext_reg_read_long;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
output [15:0] [7:0] rdata; 
output [7:0]  no_response ; 
integer k;
		cmd_cnt = cmd_cnt + 1'b1;

		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("////");
		end
		$display;
		$display("//   CMD_CNT       : %d          ",cmd_cnt);
		$display("//   CMD           : EXT_REG_READ_LONG          ");
		$display("//   SLAVE_ADDR    : 'h%1H                      ",sa[3:0]);
		$display("//   READ_NUM      : 'd%1d                      ",(bc[2:0]+1));
		$write  ("//   REG_ADDR_NUM  : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("'d%1d    |",(k[2:0]));
		end
		$display;
		$write  ("//   REG_ADDR      : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
			if((reg_addr[15:0]+k[2:0])>='hFFFF)
				$write("'hffff |");
			else
				$write("'h%4H |",(reg_addr[15:0]+k[2:0]));
		end
		$display;

		//ssc
		ssc;
		//sa[3:0] + ext_reg_read_long CMD Code + bc[2:0] Send
		cmd_data_send({sa[3:0],5'b00111,bc[2:0]},1'b0,1'b0);
		//addrh[7:0] send
		data_send(reg_addr[15:8],1'b0,1'b0);
		//addrl[7:0] send
		data_send(reg_addr[7:0],1'b0,1'b0);
		//BPC
		bpc;
		//rdata[7:0] receive
		for (k=0;k<=bc[2:0];k=k+1) begin
			data_receive(rdata[k],no_response[k]);
		end
		//BPC
		bpc;
		//Silent BPC
		bpc_silent;

		$write  ("//   RDATA         : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("'h%2H   |",rdata[(k[2:0])]);
		end
		$display;
		$write  ("//   NRF           : ");
		for (k=0;k<=bc[2:0];k=k+1) begin
			if(no_response[(k[2:0])]==1'b1)	
				$write(" YES   |");
			else
				$write("  NO   |");
		end
		$display;
		$write  ("/////////////////////////////////////////////////////");
		for (k=0;k<=bc[2:0];k=k+1) begin
				$write("////");
		end
		$display;

endtask

//===========================================
// ext_reg_read_long_chk      
//===========================================
//exampl : ext_reg_read_long_chk(8'h00,16'h8888,8'h04,{9'h055,9'h000,9'h055,9'h000,9'h0FF});
//				sa[3:0]           : slave_addr
//				reg_addr[15:0]    : slave reg_addr
//				bc[2:0]           : Write data number
//				rdata[7:0][7:0]   : no_responed + read  data ideal
task ext_reg_read_long_chk;
input [7:0] sa ;
input [15:0] reg_addr ;
input [7:0] bc ;
input [7:0] [8:0] rdata; 
bit [7:0] [7:0] rdata_tmp;
bit [8:0] rdata_tmp_in;
bit [7:0] no_response_tmp;
integer k;
	ext_reg_read_long(sa,reg_addr,bc,rdata_tmp,no_response_tmp);
			//$display("**  DEBUG            : 'h%H           ",rdata);
	

	for (k=0;k<=bc[2:0];k=k+1) begin
		rdata_tmp_in[8:0] = rdata[(bc[2:0]-k[2:0])];
		//expect no_response(NRF)?
		if(rdata_tmp_in[8:0]==`NRF) begin
			if((no_response_tmp[k]==1'b1)||(rdata_tmp[k]!=rdata_tmp_in[7:0])) begin//Not NRF and read unequal idle
			$display("************************************************");
			$display("**   REG_ADDR        : 'h%4H           ",(reg_addr[15:0]+k[2:0]));
			$display("**   READ_DATA       : 'h%2H           ",rdata_tmp[k]);
			$display("**   IDLE_READ_DATA  : 'h%2H(NRF)      ",rdata_tmp_in[7:0]);
			$display("**   ERROR!!!  The Right Result Is NRF!!!       ");
			$display("************************************************");
			err_cnt = err_cnt + 1;	
			end	
		end
		else begin
			if((rdata_tmp[k]!=rdata_tmp_in[7:0])) begin
			$display("************************************************");
			$display("**   REG_ADDR        : 'h%4H           ",(reg_addr[15:0]+k[2:0]));
			$display("**   READ_DATA       : 'h%2H           ",rdata_tmp[k]);
			$display("**   IDLE_READ_DATA  : 'h%2H           ",rdata_tmp_in[7:0]);
			$display("**   ERROR!!!                                   ");
			$display("************************************************");
				err_cnt = err_cnt + 1;	
			end
			else begin
				if(no_response_tmp[k]==1'b1) begin
				$display("************************************************");
				$display("**   ERROR!!! The Read REG_ADDR 'h%4H Result is NRF!!!         ",(reg_addr[15:0]+k[2:0]));
				$display("************************************************");
				err_cnt = err_cnt + 1;	
				end
			end
		end
	end
endtask

//===========================================
// set_pq_sa      
//===========================================
//exampl : set_p1_sa(4'hA);
//				new_usid[3:0]     : write data
task set_p1_sa;
input [3:0] new_usid;
	
		$display("////////////////////////////////////////////////");
		$display("//   CMD          : CHENGE USID                     ");
		$display("//   OLD_USID     : 'h%1H                      ",usid_user[3:0]);
		$display("//   NEW_USID     : 'h%1H                      ",new_usid[3:0]);
		$display("////////////////////////////////////////////////");

		reg_write (usid_user,8'h1D,product_id_user);
		reg_write (usid_user,8'h1E,man_id_user[7:0]);
		reg_write (usid_user,8'h1F,{man_id_user[11:8],new_usid});
		usid_user = {4'h0,new_usid};
endtask

//===========================================
// set_p2_sa      
//===========================================
//exampl : set_p2_sa(4'hA);
//				new_usid[3:0]     : write data
task set_p2_sa;
input [3:0] new_usid;
	
		$display("////////////////////////////////////////////////");
		$display("//   CMD          : CHENGE USID                     ");
		$display("//   OLD_USID     : 'h%1H                      ",usid_user[3:0]);
		$display("//   NEW_USID     : 'h%1H                      ",new_usid[3:0]);
		$display("////////////////////////////////////////////////");

		ext_reg_write (usid_user,8'h1D,8'h02,{product_id_user,man_id_user[7:0],man_id_user[11:8],new_usid});
		usid_user = {4'h0,new_usid};
endtask

//===========================================
// set_p3_sa      
//===========================================
//exampl : set_p1_sa(4'hA);
//				new_usid[3:0]     : write data
task set_p3_sa;
input [3:0] new_usid;
	
		$display("////////////////////////////////////////////////");
		$display("//   CMD          : CHENGE USID                     ");
		$display("//   OLD_USID     : 'h%1H                      ",usid_user[3:0]);
		$display("//   NEW_USID     : 'h%1H                      ",new_usid[3:0]);
		$display("////////////////////////////////////////////////");

		ext_reg_write (usid_user,8'h1D,8'h03,{product_id_user,man_id_user[7:0],{man_id_user[11:8],new_usid},ext_product_id_user});
		usid_user = {4'h0,new_usid};
endtask

////===========================================
//// mipi rffe sequence happend error                  
////===========================================
//task cmd_parity_err;
//		$display("/////CMD PARITY ERROR///////////////////////////");
//	  uart_reg_write      (`SUM_ERR_REG_ADDR,8'b0100_0000);
//endtask
//task cmd_len_err;
//		$display("/////CMD LEN ERROR//////////////////////////////");
//	  uart_reg_write      (`SUM_ERR_REG_ADDR,8'b0010_0000);
//endtask
//task addr_parity_err;
//		$display("/////ADDR PARITY ERROR///////////////////////////");
//	  uart_reg_write      (`SUM_ERR_REG_ADDR,8'b0001_0000);
//endtask
//task data_parity_err;
//		$display("/////DATA PARITY ERROR///////////////////////////");
//	  uart_reg_write      (`SUM_ERR_REG_ADDR,8'b0000_1000);
//endtask

task disp_pass;
  $display("                                                                              ");
  $display("    ///////////        //          //////////     //////////   ");
  $display("    //       //      //  //      //             //             ");
  $display("    //       //      //  //      //             //             ");
  $display("    //       //     //    //     //             //             ");
  $display("    //       //     //    //      //             //            ");
  $display("    ///////////    //////////      //////////     //////////   ");
  $display("    //             //      //               //             //  ");
  $display("    //            //        //              //             //  ");
  $display("    //            //        //              //             //  ");
  $display("    //           //          //             //             //  ");
  $display("    //           //          //            //             //   ");
  $display("    //          //            //   /////////      /////////    ");
  $display("                                                               ");
	$finish;
endtask
task disp_fail;
	$display("                                                             ");
	$display("    ////////         //           ///////////      //        ");
	$display("    //             //  //              //          //        ");
	$display("    //             //  //              //          //        ");
	$display("    //           //     //             //          //        ");
	$display("    //           //     //             //          //        ");
	$display("    ///////     ///////////            //          //        ");
	$display("    //          //       //            //          //        ");
	$display("    //         //         //           //          //        ");
	$display("    //         //         //           //          //        ");
	$display("    //        //           //          //          //        ");
	$display("    //        //           //          //          //        ");
	$display("    //       //             //    ///////////      ////////  ");
	$display("                                                             ");
	$finish;
endtask

 
`ifdef FSDB
initial begin
	$fsdbDumpfile("tb_xx.fsdb");
	$fsdbDumpvars;
	//$dumpvars;  
  //$fsdbDumpMDA;
end
`else
initial begin
	$dumpfile("tb_xx.vcd");
	$dumpvars;  
end
`endif
  




