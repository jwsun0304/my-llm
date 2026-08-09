// prpg.v
// ------
// 16-bit Galois LFSR + XOR phase-shifter PRPG.
// src/prpg_misr.py 의 GaloisLFSR + PhaseShifterPRPG 를 그대로 하드웨어로 옮김:
//   - LFSR: taps=0xB400, step()은 오른쪽 시프트 후 lsb==1이면 taps를 XOR.
//   - phase shifter: 채널 j의 출력은 LFSR state의 3개 탭
//     ((3*j)%16, (7*j+1)%16, (11*j+5)%16) 을 XOR한 값.
// next_pattern()이 "step 후의 새 상태로 패턴을 만든다"는 순서와 동일하게,
// pattern은 매 클록마다 갱신되는 state(레지스터)로부터 조합적으로 나온다.
//
// next_pattern 포트 (왜 필요한가):
//   pattern(=state 기반)을 그 자리에서 바로 CUT을 거쳐 MISR의 response로
//   먹이면, misr의 always@(posedge) 블록이 "이번 엣지에서 막 갱신될 state"가
//   아니라 "이번 엣지 이전(=한 사이클 전)의 state"를 보게 되는 문제가 있다.
//   (state<=next_state와 signature<=next_signature가 같은 엣지에서 각자
//   NBA를 스케줄하는데, NBA의 RHS는 "스케줄되는 시점"의 값으로 고정되고,
//   그 시점엔 아직 서로의 NBA가 커밋되지 않았기 때문 - 시뮬레이션 버그가
//   아니라 실제 동기 회로에서도 동일하게 나타나는, 레지스터 A의 출력을
//   같은 엣지에 레지스터 B가 조합적으로 바로 쓸 수 없다는 근본적인 제약.)
//   next_pattern은 state가 아니라 "이번 엣지에 state가 될 값"인 next_state
//   로부터 미리 계산해두므로, 같은 엣지에서 CUT/MISR이 바로 소비해도
//   (state의 NBA 커밋을 기다릴 필요 없이) 항상 최신값을 본다.
//   외부에서 CUT/MISR을 이 사이클에 구동하려면 pattern이 아니라
//   next_pattern을 써야 한다 (lbist_top.v, lbist_top_with_cut.v 참고).

module prpg #(
    parameter NUM_BITS      = 16,
    parameter [15:0] SEED   = 16'hACE1,
    parameter [15:0] TAPS   = 16'hB400
)(
    input  wire                  clk,
    input  wire                  rst_n,   // active-low: state <= SEED
    input  wire                  enable,  // 1이면 매 posedge에 한 스텝 전진
    output reg  [NUM_BITS-1:0]   pattern,       // state(레지스터, 이미 갱신된 값) 기반
    output reg  [NUM_BITS-1:0]   next_pattern,  // next_state(이번 엣지에 될 값) 기반 - CUT/MISR 구동용
    output wire [15:0]           lfsr_state
);

    reg [15:0] state;

    wire        lsb          = state[0];
    wire [15:0] shifted      = state >> 1;
    wire [15:0] next_state   = lsb ? (shifted ^ TAPS) : shifted;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= SEED;
        else if (enable)
            state <= next_state;
    end

    assign lfsr_state = state;

    integer j, a, b, c;
    always @* begin
        for (j = 0; j < NUM_BITS; j = j + 1) begin
            a = (3 * j) % 16;
            b = (7 * j + 1) % 16;
            c = (11 * j + 5) % 16;
            pattern[j]      = state[a]      ^ state[b]      ^ state[c];
            next_pattern[j] = next_state[a] ^ next_state[b] ^ next_state[c];
        end
    end

endmodule
