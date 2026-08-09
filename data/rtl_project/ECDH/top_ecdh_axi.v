`timescale 1ns / 1ns

module top_ecdh_axi (
    input  wire        clk,
    input  wire        rst_n,
    
    // AXI-Stream Input
    input  wire [63:0] in,
    input  wire        in_valid,
    input  wire        in_last,    
    output reg         in_ready, 

    // AXI-Stream Output
    output reg  [63:0] out,       
    output reg         out_valid, 
    output reg         out_last,     
    input  wire        out_ready,

    output reg         done,       
    input  wire        mode
);

    reg [3:0] state;
    reg [2:0] cnt;
    reg [255:0] scalar_buf, base_buf, out_buf;
    
    reg         inner_start;
    reg  [63:0] inner_din;
    wire [63:0] inner_dout;
    wire        inner_valid;

    localparam S_IDLE      = 4'd0, 
               S_RECV_SCAL = 4'd1, 
               S_RECV_BASE = 4'd2, 
               S_FEED      = 4'd3, 
               S_WAIT      = 4'd4, 
               S_CATCH     = 4'd5, 
               S_SEND      = 4'd6, 
               S_DONE      = 4'd7, 
               S_HALT      = 4'd8; 

    top_x25519_wrapper u_inner (
        .clk(clk), .rst_n(rst_n), .start(inner_start), .din(inner_din),
        .dout(inner_dout), .out_valid(inner_valid), .busy()
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; 
            in_ready <= 0; // 리셋 중에는 반드시 0
            out <= 0; out_valid <= 0; out_last <= 0; done <= 0; cnt <= 0;
            inner_start <= 0; scalar_buf <= 0; base_buf <= 0; out_buf <= 0; inner_din <= 0;
        end else begin
            inner_start <= 0; done <= 0;

            case (state)
                S_IDLE: begin
                    in_ready <= 1; // 리셋 해제 후 다음 클럭에 비로소 1이 됨
                    if (in_valid && in_ready) begin
                        scalar_buf[63:0] <= in; 
                        cnt <= 1; 
                        if (in_last) begin
                            in_ready <= 0;
                            state <= (mode == 0) ? S_FEED : S_RECV_BASE;
                            if (mode == 0) base_buf <= 256'd9;
                            cnt <= 0;
                        end else state <= S_RECV_SCAL;
                    end
                end
                
                S_RECV_SCAL: begin
                    in_ready <= 1;
                    if (in_valid && in_ready) begin
                        scalar_buf[cnt*64 +: 64] <= in;
                        if (cnt == 3 || in_last) begin
                            cnt <= 0;
                            if (mode == 0) begin 
                                base_buf <= 256'd9; 
                                in_ready <= 0; 
                                state <= S_FEED; 
                            end
                            else state <= S_RECV_BASE;
                        end else cnt <= cnt + 1;
                    end
                end

                S_RECV_BASE: begin
                    in_ready <= 1;
                    if (in_valid && in_ready) begin
                        base_buf[cnt*64 +: 64] <= in;
                        if (cnt == 3 || in_last) begin 
                            in_ready <= 0; // 수신 끝, ready 닫음
                            state <= S_FEED; cnt <= 0; 
                        end else cnt <= cnt + 1;
                    end
                end

                S_FEED: begin
                    in_ready <= 0; // 연산 중에는 켜지지 않음
                    inner_din <= (cnt < 4) ? scalar_buf[cnt*64 +: 64] : base_buf[(cnt-4)*64 +: 64];
                    if (cnt == 0) inner_start <= 1; 
                    if (cnt == 7) begin state <= S_WAIT; cnt <= 0; end
                    else cnt <= cnt + 1;
                end

                S_WAIT: begin
                    if (inner_valid) begin 
                        out_buf[63:0] <= inner_dout; 
                        cnt <= 1; 
                        state <= S_CATCH; 
                    end
                end

                S_CATCH: begin
                    if (inner_valid) begin
                        out_buf[cnt*64 +: 64] <= inner_dout;
                        if (cnt == 3) begin 
                            out <= out_buf[63:0]; 
                            out_valid <= 1; 
                            cnt <= 1; 
                            state <= S_SEND; 
                        end else cnt <= cnt + 1;
                    end
                end

                S_SEND: begin
                    if (out_ready && out_valid) begin
                        if (cnt == 4) begin 
                            out_valid <= 0; out_last <= 0; state <= S_DONE; 
                        end else begin
                            out <= out_buf[cnt*64 +: 64];
                            out_last <= (cnt == 3); 
                            cnt <= cnt + 1;
                        end
                    end
                end

                S_DONE: begin 
                    done <= 1; 
                    state <= S_HALT; 
                end

                S_HALT: begin 
                    done <= 0; 
                    in_ready <= 0;
                    state <= S_HALT; // 리셋 전까지 대기
                end
                
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule