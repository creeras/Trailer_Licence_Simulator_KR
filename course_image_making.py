import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from matplotlib import font_manager, rc

# ================================
# 1. 한글 폰트 설정 (Windows 전용)
# ================================
# 말끔하게 한 줄로 해결하는 가장 안정적인 방법
font_path = "C:/Windows/Fonts/malgun.ttf"   # 맑은 고딕 Regular 권장
font_prop = font_manager.FontProperties(fname=font_path)
plt.rcParams["font.family"] = font_prop.get_name()
plt.rcParams["axes.unicode_minus"] = False      # - 깨짐 방지

# ================================
# 2. 치수 및 각도 설정
# ================================
L_platform = 10.0
L_approach = 12.0
L_gate = 9.7
W_clearance = 3.6
W_left_span = 25.0
W_right_span = 17.4
H_taper_offset = 3.0

W_total = W_left_span + W_clearance + W_right_span

X_gate_half = W_clearance / 2
X_taper_end_half = X_gate_half + H_taper_offset

Y_start = 0.0
Y_gate_top = Y_start + L_gate
Y_platform_start = Y_gate_top + L_approach
Y_platform_top = Y_platform_start + L_platform

# ================================
# 3. 비대칭 기울기 계산
# ================================
delta_Y = L_approach
theta_base_deg = np.degrees(np.arctan(delta_Y / 5.2))
theta_left_deg = theta_base_deg - 10.0
theta_right_deg = theta_base_deg + 5.0

delta_X_left = delta_Y / np.tan(np.radians(theta_left_deg))
delta_X_right = delta_Y / np.tan(np.radians(theta_right_deg))

X_taper_start_L = X_taper_end_half + delta_X_left
X_taper_start_R = X_taper_end_half + delta_X_right

# ================================
# 4. Plot 그리기
# ================================
fig, ax = plt.subplots(figsize=(16, 7))
ax.set_aspect("equal", adjustable="box")

color_structure = "#00798C"
color_dim = "purple"
color_stopline = "red" # 정지선 색상
dim_offset = 3

X_left_edge = -(W_left_span + X_gate_half)
X_right_edge = W_right_span + X_gate_half

# 4.1 상단 주행로
rect = patches.Rectangle(
    (X_left_edge, Y_platform_start),
    W_total,
    L_platform,
    linewidth=2,
    edgecolor=color_structure,
    facecolor="none"
)
ax.add_patch(rect)
ax.text(0, Y_platform_top - 1.5, "상단 주행로", color=color_structure,
        ha="center", va="top", fontsize=12)

# 4.2 중앙 공간
style = "-"
ax.plot([-X_gate_half, X_gate_half], [Y_start, Y_start], color=color_structure, linewidth=2)
ax.plot([-X_gate_half, -X_gate_half], [Y_start, Y_gate_top], color=color_structure, linewidth=2)
ax.plot([X_gate_half, X_gate_half], [Y_start, Y_gate_top], color=color_structure, linewidth=2)

# 4.3 경사
style = "--"
ax.plot([-X_taper_start_L, -X_taper_end_half], [Y_platform_start, Y_gate_top],
        linestyle=style, color=color_structure)
ax.plot([X_taper_start_R, X_taper_end_half], [Y_platform_start, Y_gate_top],
        linestyle=style, color=color_structure)

# 4.4 수평 연결선
style = "-"
ax.plot([-X_taper_end_half, -X_gate_half], [Y_gate_top, Y_gate_top],
        color=color_structure, linewidth=2)
ax.plot([X_taper_end_half, X_gate_half], [Y_gate_top, Y_gate_top],
        color=color_structure, linewidth=2)
        
# 4.5 정지선 추가 (Stop Lines)
# 정지선은 해당 섹션의 끝에서 1m 떨어진 지점에 위치합니다.
stopline_style = "r--"
stopline_linewidth = 1.5

# 1. 상단 주행로 - 왼쪽 끝 (X_left_edge에서 1m 안쪽)
X_stop_platform = X_left_edge + 1.0 
ax.plot([X_stop_platform, X_stop_platform], [Y_platform_start, Y_platform_top],
        color=color_stopline, linestyle="--", linewidth=stopline_linewidth)
ax.text(X_stop_platform, Y_platform_top, "1 M", color=color_stopline, ha="left", va="bottom", fontsize=10) # 1 M 표시

# 2. 중앙 공간 - 왼쪽 (Y_start에서 1m 위쪽)
Y_stop_gate = Y_start + 1.0
ax.plot([-X_gate_half, X_gate_half], [Y_stop_gate, Y_stop_gate],
        color=color_stopline, linestyle="--", linewidth=stopline_linewidth)
ax.text(X_gate_half, Y_stop_gate, "1 M", color=color_stopline, ha="left", va="bottom", fontsize=10) # 1 M 표시

# ================================
# 5. 치수선 함수
# (이 부분은 변경하지 않았습니다)
# ================================
def draw_vertical_dim(ax, x, y1, y2, label):
    ax.annotate("", xy=(x, y1), xytext=(x, y2),
                arrowprops=dict(arrowstyle="<->", color=color_dim, linewidth=1.5))
    ax.text(x + 0.5, (y1 + y2) / 2, label, color=color_dim, va="center")


def draw_horizontal_dim(ax, x1, x2, y, label, offset=1.5):
    y_arrow = y + offset   # 화살표만 위로 이동
    ax.annotate("", xy=(x1, y_arrow), xytext=(x2, y_arrow),
                arrowprops=dict(arrowstyle="<->", color=color_dim, linewidth=1.5))

    # 숫자는 원래 y 기준으로 그리기 → 화살표와 분리됨
    ax.text((x1 + x2) / 2, y - 0.5, label, color=color_dim, ha="center")


# 수직 치수
draw_vertical_dim(ax, X_right_edge + dim_offset, Y_platform_start, Y_platform_top, "10 M")
draw_vertical_dim(ax, X_right_edge + dim_offset, Y_gate_top, Y_platform_start, "12 M")
draw_vertical_dim(ax, X_right_edge + dim_offset, Y_start, Y_gate_top, "9.7 M")

# 수평 치수
dim_y_pos = -dim_offset
draw_horizontal_dim(ax, X_left_edge, -X_gate_half, dim_y_pos, f"{W_left_span} M")
draw_horizontal_dim(ax, -X_gate_half, X_gate_half, dim_y_pos, "3.6 M")
draw_horizontal_dim(ax, X_gate_half, X_right_edge, dim_y_pos, f"{W_right_span} M")

# ================================
# 완료
# ================================
ax.set_xlim(X_left_edge - 5, X_right_edge + 10)
ax.set_ylim(-10, Y_platform_top + 5)
ax.set_title("대형 견인 시험장 구조도", fontsize=16)

plt.show()