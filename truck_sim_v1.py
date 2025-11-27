import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import math
import logging
import os
from collections import deque
import json # Import json module

class TractorTrailerSim:
    CONFIG_FILE = "truck_sim_config.json" # Define config file constant
    def __init__(self, root):
        self.root = root
        self.root.title("트랙터-트레일러 주행 시뮬레이터 (v24.0 - 실행 오류 수정)")

        self.animation_id = None
        self.setup_logging()
        
        # --- 상수 및 변수 ---
        self.tractor_wb = 3.8
        self.trailer_len_var = tk.DoubleVar(value=10.0) # 트레일러 길이 제어 변수
        self.trailer_len = self.trailer_len_var.get()
        self.tractor_width = 2.5
        self.pixels_per_meter = 12 
        self.x = 0.0; self.y = 0.0; self.yaw_tractor = 0.0; self.yaw_trailer = 0.0
        self.wheel_paths = {}; self.max_path_points = 2000
        
        self.bg_photo = None
        self.pil_bg_image = None
        self.bg_offset_x = 0.0
        self.bg_offset_y = 0.0
        self.bg_scale = 1.0
        self.bg_image_path = None # Initialize background image path
        
        # --- 제어 변수 ---
        self.var_gear = tk.StringVar(value="F") 
        self.auto_follow = tk.BooleanVar(value=True) 
        self.angle_control_mode = tk.StringVar(value="manual") 
        self.initial_angle_for_stop = None
        self.previous_angle_error = None
        
        # --- History ---
        self.history = deque(maxlen=50)
        self._ignore_history_selection = False # Flag to prevent selection event loops

        # --- 뷰 이동(Panning) 변수 ---
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.manual_offset_x = 0
        self.manual_offset_y = 0

        # --- 레이아웃 ---
        self.control_frame = tk.Frame(root, padx=10, pady=10, width=250)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.canvas_width = 900; self.canvas_height = 700
        self.canvas = tk.Canvas(root, width=self.canvas_width, height=self.canvas_height, bg="#f0f0f0", cursor="fleur")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(root, padx=10, pady=10, width=250)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)


        # 마우스 이벤트 바인딩
        self.canvas.bind("<ButtonPress-1>", self._pan_start)
        self.canvas.bind("<B1-Motion>", self._pan_move)

        self.setup_controls()
        self.setup_history_panel() # New method for history panel
        self._load_config() # Load configuration after controls are set up

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.logger.info("="*50)
        self.logger.info("시뮬레이터 애플리케이션 시작 (v9.0).")
        
        # 초기 상태 저장
        self.reset_simulation()

    def setup_logging(self):
        log_dir="Truck_Sim"; 
        if not os.path.exists(log_dir): os.makedirs(log_dir)
        log_file=os.path.join(log_dir, "simulation_log.txt")
        self.logger=logging.getLogger("TractorTrailerSim"); self.logger.setLevel(logging.INFO)
        if self.logger.hasHandlers(): self.logger.handlers.clear()
        fh=logging.FileHandler(log_file, encoding='utf-8'); fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'); fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def _load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.bg_image_path = config.get("bg_image_path")
                    self.bg_offset_x = config.get("bg_offset_x", 0.0)
                    self.bg_offset_y = config.get("bg_offset_y", 0.0)
                    self.bg_scale = config.get("bg_scale", 1.0)

                    # Update UI controls if they exist
                    if hasattr(self, 'scale_bg_x'):
                        self.scale_bg_x.set(self.bg_offset_x)
                        self.scale_bg_y.set(self.bg_offset_y)
                        self.scale_bg_scale.set(int(self.bg_scale * 100))
                    
                    if self.bg_image_path and os.path.exists(self.bg_image_path):
                        self._load_background_from_path(self.bg_image_path)
                    
                    self.logger.info(f"설정 로드 완료: {self.CONFIG_FILE}")
            except Exception as e:
                self.logger.error(f"설정 로드 실패: {e}")
        else:
            self.logger.info("설정 파일이 없어 기본값으로 초기화됩니다.")
            self._save_config() # Create a default config file

    def _save_config(self):
        config = {
            "bg_image_path": self.bg_image_path,
            "bg_offset_x": self.bg_offset_x,
            "bg_offset_y": self.bg_offset_y,
            "bg_scale": self.bg_scale
        }
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            self.logger.info(f"설정 저장 완료: {self.CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"설정 저장 실패: {e}")

    def _load_background_from_path(self, file_path):
        try:
            from PIL import Image, ImageTk
            self.pil_bg_image = Image.open(file_path)
            self.bg_photo = ImageTk.PhotoImage(self.pil_bg_image)
            self.logger.info(f"배경 이미지 로드 성공: {file_path}")
            return True
        except ImportError:
            self.pil_bg_image = None
            try:
                self.bg_photo = tk.PhotoImage(file=file_path) # Fallback to tkinter if Pillow not installed
                self.logger.warning("Pillow 라이브러리가 없어 스케일링이 불가능합니다. 'pip install Pillow'로 설치해주세요.")
                messagebox.showwarning("라이브러리 필요", "배경 이미지의 크기를 조절하려면 'Pillow' 라이브러리가 필요합니다.\n\n'pip install Pillow' 명령어로 설치할 수 있습니다.")
                return True
            except Exception as e:
                self.logger.error(f"tkinter로 배경 이미지 로드 실패: {e}")
                messagebox.showerror("오류", f"배경 이미지를 로드하는 데 실패했습니다:\n{e}")
                return False
        except Exception as e:
            self.logger.error(f"배경 이미지 로드 실패: {e}")
            messagebox.showerror("오류", f"배경 이미지를 로드하는 데 실패했습니다:\n{e}")
            return False

    def on_closing(self):
        self.logger.info("시뮬레이터 애플리케이션 종료."); self.logger.info("="*50 + "\n")
        self._save_config() # Save configuration before closing
        if self.animation_id: self.root.after_cancel(self.animation_id)
        self.root.destroy()

    def setup_controls(self):
        tk.Label(self.control_frame, text="--- 트레일러 길이 ---", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.trailer_len_var.trace_add("write", self._update_trailer_len)
        self.scale_trailer_len = tk.Scale(self.control_frame, from_=8.5, to=12.0, orient=tk.HORIZONTAL, resolution=0.5,
                                           variable=self.trailer_len_var, length=200)
        self.scale_trailer_len.pack(fill=tk.X)
        self.trailer_len_label = tk.Label(self.control_frame, text=f"{self.trailer_len_var.get():.1f}m")
        self.trailer_len_label.pack(anchor='w')
        
        tk.Label(self.control_frame, text="--- 기어 및 조향 ---", font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 5))
        self.gear_canvas = tk.Canvas(self.control_frame, height=100, bg="#e0e0e0", highlightthickness=1, highlightbackground="gray"); self.gear_canvas.pack(fill=tk.X, pady=5); self.gear_canvas.bind("<Button-1>", self.toggle_gear); self._draw_gear_shifter()
        tk.Label(self.control_frame, text="헤드 바퀴 각도 (좌/우, deg)").pack(anchor="w")
        self.scale_angle = tk.Scale(self.control_frame, from_=40, to_=-40, orient=tk.HORIZONTAL, resolution=1, command=self.update_steer_visualization); self.scale_angle.set(0); self.scale_angle.pack(fill=tk.X)
        
        tk.Label(self.control_frame, text="--- 트레일러 각도 제어 ---", font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 5))
        self.angle_control_mode.trace_add("write", lambda *args: self.logger.info(f"각도 제어 모드 변경: {self.angle_control_mode.get()}"))
        ttk.Radiobutton(self.control_frame, text="수동 조향", variable=self.angle_control_mode, value="manual").pack(anchor="w")
        ttk.Radiobutton(self.control_frame, text="목표 각도 도달 시 정지 (수동 조향)", variable=self.angle_control_mode, value="stop_at_target").pack(anchor="w")
        
        tk.Label(self.control_frame, text="목표 꺾임 각도 (deg)").pack(anchor="w", pady=(5,0))
        self.target_articulation_angle = tk.DoubleVar(value=45.0) 
        self.scale_target_angle = tk.Scale(self.control_frame, from_=0, to=90, orient=tk.HORIZONTAL, resolution=1, 
                                            variable=self.target_articulation_angle, command=self._update_target_angle_display)
        self.scale_target_angle.pack(fill=tk.X)
        
        self.target_angle_display_label = tk.Label(self.control_frame, text=f"{self.target_articulation_angle.get():.0f}°")
        self.target_angle_display_label.pack(anchor="w")

        ttk.Radiobutton(self.control_frame, text="꺾임 각도 유지 주행 (Auto Steer)", variable=self.angle_control_mode, value="maintain").pack(anchor="w")

        tk.Label(self.control_frame, text="--- 조작 및 뷰 ---", font=("Arial", 10, "bold")).pack(anchor="w", pady=(20, 5))
        
        dist_button_frame = tk.Frame(self.control_frame)
        dist_button_frame.pack(fill=tk.X, pady=(2, 0))
        distances = [0.2, 0.5, 1, 5, 10, 20]
        for i, dist in enumerate(distances):
            btn = tk.Button(dist_button_frame, text=f"{dist}m", command=lambda d=dist: self._start_drive_with_dist(d))
            btn.grid(row=i//3, column=i%3, sticky="ew", padx=1, pady=1)
        dist_button_frame.grid_columnconfigure((0,1,2), weight=1)

        ttk.Separator(self.control_frame, orient='horizontal').pack(fill='x', pady=10)
        
        self.auto_follow.trace_add("write", lambda *args: self.logger.info(f"자동 추적 모드: {self.auto_follow.get()}"))
        ttk.Checkbutton(self.control_frame, text="화면 자동 추적", variable=self.auto_follow, command=self._on_auto_follow_toggle).pack(anchor="w")
        tk.Button(self.control_frame, text="초기화 (Reset)", command=self.reset_simulation, fg="red").pack(fill=tk.X, pady=5)
        tk.Button(self.control_frame, text="배경 이미지 로드", command=self.load_background).pack(fill=tk.X)

        # --- v12: 배경 이미지 제어 ---
        bg_control_frame = tk.LabelFrame(self.control_frame, text="배경 이미지 조정", padx=5, pady=5)
        bg_control_frame.pack(fill=tk.X, pady=5, padx=2)

        tk.Label(bg_control_frame, text="X 오프셋(m)").grid(row=0, column=0, sticky="w")
        self.scale_bg_x = tk.Scale(bg_control_frame, from_=-100, to=100, orient=tk.HORIZONTAL, resolution=0.5, command=self._update_background_transform)
        self.scale_bg_x.set(0.0)
        self.scale_bg_x.grid(row=0, column=1, sticky="ew")

        tk.Label(bg_control_frame, text="Y 오프셋(m)").grid(row=1, column=0, sticky="w")
        self.scale_bg_y = tk.Scale(bg_control_frame, from_=-100, to=100, orient=tk.HORIZONTAL, resolution=0.5, command=self._update_background_transform)
        self.scale_bg_y.set(0.0)
        self.scale_bg_y.grid(row=1, column=1, sticky="ew")

        tk.Label(bg_control_frame, text="스케일(%)").grid(row=2, column=0, sticky="w")
        self.scale_bg_scale = tk.Scale(bg_control_frame, from_=10, to=500, orient=tk.HORIZONTAL, resolution=1, command=self._update_background_transform)
        self.scale_bg_scale.set(100)
        self.scale_bg_scale.grid(row=2, column=1, sticky="ew")
        
        bg_control_frame.grid_columnconfigure(1, weight=1)

    def setup_history_panel(self):
        # --- History ---
        history_frame = tk.LabelFrame(self.right_frame, text="--- 조작 기록 (History) ---", padx=5, pady=5)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=0)
        
        tk.Button(history_frame, text="기록 초기화", command=self._clear_history).pack(fill=tk.X, pady=(0,5))

        listbox_frame = tk.Frame(history_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        self.history_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=6)
        scrollbar.config(command=self.history_listbox.yview)
        
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_listbox.bind("<<ListboxSelect>>", self._on_history_select)

    def _pan_start(self, event):
        self.auto_follow.set(False)
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.logger.info("뷰 이동 시작.")

    def _pan_move(self, event):
        if not self.auto_follow.get():
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.manual_offset_x += dx
            self.manual_offset_y += dy
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.draw_scene(current_steer=math.radians(self.scale_angle.get()))

    def _on_auto_follow_toggle(self):
        if self.auto_follow.get():
            self.manual_offset_x = 0
            self.manual_offset_y = 0
            self.logger.info("자동 추적 활성화. 수동 뷰 이동 초기화.")
        self.draw_scene(current_steer=math.radians(self.scale_angle.get()))

    def _draw_gear_shifter(self):
        self.gear_canvas.delete("all"); w=self.gear_canvas.winfo_width(); h=self.gear_canvas.winfo_height()
        if w<2: w=238
        if h<2: h=100
        slot_x = w/2; self.gear_canvas.create_line(slot_x, 15, slot_x, h-15, width=4, fill="gray")
        self.gear_canvas.create_text(slot_x+30, 25, text="F\n(전진)", fill="green", font=("Arial",10,"bold"))
        self.gear_canvas.create_text(slot_x+30, h-25, text="R\n(후진)", fill="red", font=("Arial",10,"bold"))
        knob_y = 25 if self.var_gear.get()=="F" else h-25
        self.gear_canvas.create_line(slot_x, knob_y, slot_x, h/2, width=3, fill="black")
        self.gear_canvas.create_oval(slot_x-12, knob_y-12, slot_x+12, knob_y+12, fill="#cc5555", outline="black", width=2)

    def toggle_gear(self, event=None):
        if self.var_gear.get()=="F": self.var_gear.set("R")
        else: self.var_gear.set("F")
        self._draw_gear_shifter(); self.logger.info(f"기어 변경: {'R' if self.var_gear.get()=='R' else 'F'}")





    def update_steer_visualization(self, angle_str="0"):
        self.draw_scene(current_steer=math.radians(float(angle_str)))

    def _update_trailer_len(self, *args):
        self.trailer_len = self.trailer_len_var.get()
        self.trailer_len_label.config(text=f"{self.trailer_len:.1f}m")
        self.logger.info(f"트레일러 길이 변경: {self.trailer_len:.1f}m")
        self.reset_simulation(keep_paths=True) # Redraw with new length

    def _update_target_angle_display(self, val):
        self.target_angle_display_label.config(text=f"{float(val):.0f}°")

    def _initialize_paths(self):
        self.wheel_paths.clear()
        for name, pos in self._get_world_wheel_positions().items(): self.wheel_paths[name]=deque([pos], maxlen=self.max_path_points)
        self.logger.info("바퀴 궤적 초기화 완료.")

    def reset_simulation(self, keep_paths=False):
        self.manual_offset_x = 0; self.manual_offset_y = 0
        if self.animation_id: self.root.after_cancel(self.animation_id); self.animation_id=None
        self.x=0.0; self.y=0.0; self.yaw_tractor=math.pi; self.yaw_trailer=math.pi
        self.initial_angle_for_stop = None; self.previous_angle_error = None

        # '초기화' 버튼을 눌렀을 때만(keep_paths=False) 전체 컨트롤을 초기화
        if not keep_paths:
            self.scale_angle.set(0)
            self.var_gear.set("F")
            self._draw_gear_shifter()
            self.angle_control_mode.set("manual")
            
            self.target_articulation_angle.set(45.0)
            self.target_angle_display_label.config(text=f"{self.target_articulation_angle.get():.0f}°")
            
            self.trailer_len_var.set(10.0)
            self.trailer_len_label.config(text=f"{self.trailer_len_var.get():.1f}m")
            
            self.auto_follow.set(True)

            # History clear and initialize
            self.history.clear()
            self.history.append(("초기 상태", self._capture_state()))
            self._update_history_listbox()

        log_msg="시뮬레이션 전체 초기화." if not keep_paths else "차량 구성 변경으로 초기화."
        self._initialize_paths(); self.logger.info(log_msg)
        self.draw_scene(current_steer=math.radians(self.scale_angle.get()))

    def _get_axle_definitions(self):
        tractor_axles={'front':self.tractor_wb, 'rear1':0.65, 'rear2':-0.65}
        trailer_axles={'tr_rear1':1.1/2, 'tr_rear2':-1.1/2}
        return tractor_axles, trailer_axles
        
    def _get_world_wheel_positions(self, steer_rad=0.0):
        positions={}; tractor_axles, trailer_axles=self._get_axle_definitions(); half_w=self.tractor_width/2.0
        # 트랙터 축 계산
        for name, dist in tractor_axles.items():
            is_front = (name == 'front')
            axle_x = self.x + dist * math.cos(self.yaw_tractor)
            axle_y = self.y + dist * math.sin(self.yaw_tractor)
            
            final_steer = steer_rad if is_front else 0.0
            yaw_eff = self.yaw_tractor + final_steer
            
            # 바퀴 위치 계산
            wl_x = axle_x + half_w * math.cos(yaw_eff + math.pi/2)
            wl_y = axle_y + half_w * math.sin(yaw_eff + math.pi/2)
            wr_x = axle_x - half_w * math.cos(yaw_eff + math.pi/2)
            wr_y = axle_y - half_w * math.sin(yaw_eff + math.pi/2)
            positions[f't_{name}_l']=(wl_x,wl_y); positions[f't_{name}_r']=(wr_x,wr_y)

        # 트레일러 기준점 (킹핀)
        kingpin_x = self.x 
        kingpin_y = self.y

        # 트레일러 축 계산
        for name, dist in trailer_axles.items():
            # 트레일러의 실제 기준점은 킹핀에서 트레일러 길이만큼 뒤에 있습니다.
            # 하지만 각 축의 위치는 트레일러의 기하학적 중심을 기준으로 계산하는 것이 더 직관적일 수 있습니다.
            # 여기서는 트레일러의 회전 중심(뒷바퀴 축의 중심)을 기준으로 계산합니다.
            # 트레일러 회전 중심 위치
            trailer_pivot_x = kingpin_x - self.trailer_len * math.cos(self.yaw_trailer)
            trailer_pivot_y = kingpin_y - self.trailer_len * math.sin(self.yaw_trailer)

            axle_x = trailer_pivot_x + dist * math.cos(self.yaw_trailer)
            axle_y = trailer_pivot_y + dist * math.sin(self.yaw_trailer)
            
            # 바퀴 위치 계산
            wl_x = axle_x + half_w * math.sin(self.yaw_trailer)
            wl_y = axle_y - half_w * math.cos(self.yaw_trailer)
            wr_x = axle_x - half_w * math.sin(self.yaw_trailer)
            wr_y = axle_y + half_w * math.cos(self.yaw_trailer)
            positions[f'{name}_l']=(wl_x, wl_y); positions[f'{name}_r']=(wr_x, wr_y)
        return positions

    def to_screen(self, x, y, view_offset_x, view_offset_y):
        abs_cx, abs_cy = self.canvas_width/2, self.canvas_height/2
        screen_x = abs_cx + x*self.pixels_per_meter - view_offset_x
        screen_y = abs_cy - y*self.pixels_per_meter + view_offset_y
        return screen_x, screen_y

    def calculate_steer_for_angle_maintenance(self, angle_diff):
        if abs(angle_diff) > math.radians(90): return 0 
        return math.atan((self.tractor_wb / self.trailer_len) * math.sin(angle_diff))

    def calculate_steer_for_target_angle(self, current_angle_diff_rad, target_angle_rad, direction):
        error=target_angle_rad-abs(current_angle_diff_rad); sign=1 if current_angle_diff_rad>0 else -1 
        steer_adjustment=0.8*error; base_steer=self.calculate_steer_for_angle_maintenance(current_angle_diff_rad)
        if direction==-1: final_steer=base_steer-(sign*steer_adjustment)
        else: final_steer=base_steer+(sign*steer_adjustment)
        return max(min(final_steer, math.radians(40)), -math.radians(40))





    def _capture_state(self):
        # wheel_paths의 deque를 list로 변환하여 저장
        paths_copy = {name: list(path) for name, path in self.wheel_paths.items()}
        state = {
            "x": self.x, "y": self.y,
            "yaw_tractor": self.yaw_tractor, "yaw_trailer": self.yaw_trailer,
            "wheel_paths": paths_copy,
            "angle_control_mode": self.angle_control_mode.get(),
            "var_gear": self.var_gear.get(),
            "scale_angle": self.scale_angle.get(),
            "target_articulation_angle": self.target_articulation_angle.get(),
            "trailer_len_var": self.trailer_len_var.get(),
            "auto_follow": self.auto_follow.get(),
            "manual_offset_x": self.manual_offset_x,
            "manual_offset_y": self.manual_offset_y,
        }
        return state

    def _restore_state(self, state):
        self.x = state["x"]; self.y = state["y"]
        self.yaw_tractor = state["yaw_tractor"]; self.yaw_trailer = state["yaw_trailer"]
        
        # list를 다시 deque로 변환하여 복원
        self.wheel_paths.clear()
        for name, path_list in state["wheel_paths"].items():
            self.wheel_paths[name] = deque(path_list, maxlen=self.max_path_points)

        self.angle_control_mode.set(state["angle_control_mode"])
        self.var_gear.set(state["var_gear"])
        self.scale_angle.set(state["scale_angle"])
        
        self.target_articulation_angle.set(state["target_articulation_angle"])
        
        # --- Trace 비활성화 후 값 설정 ---
        trace_info = self.trailer_len_var.trace_info()
        if trace_info:
            self.trailer_len_var.trace_remove('write', trace_info[0][1])
        
        self.trailer_len_var.set(state["trailer_len_var"])
        
        if trace_info:
            self.trailer_len_var.trace_add('write', trace_info[0][1])
        # --- Trace 재활성화 ---

        self.auto_follow.set(state["auto_follow"])
        self.manual_offset_x = state["manual_offset_x"]
        self.manual_offset_y = state["manual_offset_y"]

        self._draw_gear_shifter()
        self.draw_scene(current_steer=math.radians(self.scale_angle.get()))
        self.logger.info("상태 복원 완료.")

    def _add_to_history(self, description):
        # This is called *after* an action is complete.
        current_selection = self.history_listbox.curselection()
        history_len_before_add = len(self.history)
        
        # If a specific point in history is selected, and it's not the last one, truncate.
        if current_selection and current_selection[0] < (history_len_before_add - 1):
            branch_index = current_selection[0]
            self.logger.info(f"새로운 조작 기록 분기 생성 (기존 {branch_index}번 기록에서 이어짐).")
            # Deque doesn't support slicing. Convert, truncate, rebuild.
            history_list = list(self.history)
            self.history.clear()
            # Add back only the states up to and including the branch point.
            for i in range(branch_index + 1):
                self.history.append(history_list[i])

        state = self._capture_state()
        self.history.append((description, state))
        self._update_history_listbox()

    def _update_history_listbox(self):
        self._ignore_history_selection = True
        self.history_listbox.delete(0, tk.END)
        for i, (desc, _) in enumerate(self.history):
            self.history_listbox.insert(tk.END, f"{i}: {desc}")
        # Select the last item
        self.history_listbox.see(tk.END)
        self.history_listbox.selection_clear(0, tk.END)
        self.history_listbox.selection_set(tk.END)
        self._ignore_history_selection = False


    def _on_history_select(self, event):
        if self._ignore_history_selection:
            return
        if not event.widget.curselection():
            return
        
        selected_index = event.widget.curselection()[0]
        
        try:
            _, state_to_restore = self.history[selected_index]
            self._restore_state(state_to_restore)
            self.logger.info(f"{selected_index}번 조작 기록으로 복원합니다.")
        except IndexError:
            self.logger.error("선택한 기록을 복원하는 데 실패했습니다. 인덱스가 범위를 벗어났습니다.")

    def _clear_history(self):
        self.reset_simulation() # Resetting simulation clears history

    def _start_drive_with_dist(self, distance):
        self.logger.info(f"주행 거리 버튼 클릭: {distance}m")
        direction_text = "전진" if self.var_gear.get() == "F" else "후진"
        
        mode = self.angle_control_mode.get()
        if mode == 'manual':
            mode_text = "(수동)"
        elif mode == 'stop_at_target':
            target = self.target_articulation_angle.get()
            mode_text = f"(목표/{target:.0f}°)"
        elif mode == 'maintain':
            mode_text = "(자동조향)"
        else:
            mode_text = ""
            
        description = f"{direction_text} {distance}m {mode_text}"
        self.start_drive(dist_goal=distance, description=description)

    def start_drive(self, dist_goal, description):
        if self.animation_id: self.root.after_cancel(self.animation_id); self.animation_id=None
        try:
            direction=1 if self.var_gear.get()=="F" else -1
            target_angle=self.target_articulation_angle.get() if self.target_articulation_angle.get() is not None else None
        except ValueError: 
            self.logger.error("주행 시작 실패: 잘못된 입력 값."); return
        
        self.initial_angle_for_stop = None
        self.previous_angle_error = None

        if self.angle_control_mode.get() == 'stop_at_target' and target_angle is not None:
            current_angle_deg = abs(math.degrees(self.yaw_tractor - self.yaw_trailer))
            self.initial_angle_for_stop = current_angle_deg
            self.previous_angle_error = current_angle_deg - target_angle
            self.logger.info(f"목표 각도 정지 모드 시작: 현재 {current_angle_deg:.1f}°, 목표 {target_angle:.1f}°")

        self.logger.info(f"주행 시작: 거리={dist_goal}m, 방향={'전진' if direction==1 else '후진'}, 제어={self.angle_control_mode.get()}, 목표각도={target_angle}°")
        self.animate_step(int(dist_goal/0.078), 0.078, direction, target_angle, description)

    def animate_step(self, steps_left, step_dist, direction, target_angle, description):
        current_angle_diff_rad=self.yaw_tractor-self.yaw_trailer
        current_angle_diff_deg=abs(math.degrees(current_angle_diff_rad))

        # --- v10: 잭나이프(Jackknife) 방지 ---
        if current_angle_diff_deg > 90.0 and direction == 1: # 전진 시에만 적용
            self.logger.warning(f"잭나이프 현상 발생! 현재 꺾임 각도: {current_angle_diff_deg:.1f}°. 주행을 중지합니다.")
            messagebox.showwarning("잭나이프 위험!", f"트랙터와 트레일러의 각도가 90도를 초과했습니다({current_angle_diff_deg:.1f}°).\n\n잭나이프 현상으로 인해 주행을 중지합니다.")
            if self.animation_id: self.root.after_cancel(self.animation_id); self.animation_id=None
            self._add_to_history(description + " (잭나이프 중단)")
            self.draw_scene(current_steer=math.radians(self.scale_angle.get())); return
        
        control_mode = self.angle_control_mode.get()
        target_mode_active = target_angle is not None

        if control_mode == 'stop_at_target' and target_mode_active and self.initial_angle_for_stop is not None:
            current_error = current_angle_diff_deg - target_angle
            if abs(current_error) < 1.0 or (self.previous_angle_error is not None and (current_error * self.previous_angle_error) <= 0):
                self.logger.info(f"목표 각도 {target_angle}° 도달. 주행 중지."); 
                messagebox.showinfo("목표 각도 도달", f"현재 꺾임 각도 {current_angle_diff_deg:.1f}°가 목표 {target_angle}°에 도달하여 주행을 중지합니다.")
                if self.animation_id: self.root.after_cancel(self.animation_id); self.animation_id=None
                self._add_to_history(description)
                self.draw_scene(current_steer=math.radians(self.scale_angle.get())); return
            self.previous_angle_error = current_error

        if steps_left<=0: 
            self.logger.info("주행 완료.")
            self.animation_id=None
            self._add_to_history(description)
            return

        steer_rad=math.radians(self.scale_angle.get()) # 기본값: 수동 조향
        if control_mode == 'maintain':
            steer_rad = self.calculate_steer_for_angle_maintenance(current_angle_diff_rad)
            self.scale_angle.set(math.degrees(steer_rad))
        
        v=step_dist*direction; self.x+=v*math.cos(self.yaw_tractor); self.y+=v*math.sin(self.yaw_tractor); self.yaw_tractor+=(v/self.tractor_wb)*math.tan(steer_rad)
        angle_diff=self.yaw_tractor-self.yaw_trailer; delta_yaw_trailer=(step_dist/self.trailer_len)*math.sin(angle_diff)
        if direction==1: self.yaw_trailer+=delta_yaw_trailer
        else: self.yaw_trailer-=delta_yaw_trailer
        for name, pos in self._get_world_wheel_positions(steer_rad).items():
            if name in self.wheel_paths: self.wheel_paths[name].append(pos)
        self.draw_scene(steer_rad)
        
        if steps_left%20==0: self.logger.info(f"주행 중... 현재 꺾임 각도: {current_angle_diff_deg:.1f}° | 헤드 조향각: {math.degrees(steer_rad):.1f}°")
        self.animation_id=self.root.after(10, self.animate_step, steps_left-1, step_dist, direction, target_angle, description)


    def _update_background_transform(self, _=None):
        if not self.bg_photo:
            return

        self.bg_offset_x = self.scale_bg_x.get()
        self.bg_offset_y = self.scale_bg_y.get()
        new_scale_percent = self.scale_bg_scale.get()
        
        if self.pil_bg_image:
            try:
                from PIL import Image, ImageTk
                
                # 스케일이 변경되었을 때만 이미지 재생성
                if int(self.bg_scale * 100) != new_scale_percent:
                    self.bg_scale = new_scale_percent / 100.0
                    
                    original_width, original_height = self.pil_bg_image.size
                    new_width = int(original_width * self.bg_scale)
                    new_height = int(original_height * self.bg_scale)

                    if new_width > 0 and new_height > 0:
                        resized_pil_image = self.pil_bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        self.bg_photo = ImageTk.PhotoImage(resized_pil_image)
                    else: # 이미지가 너무 작아지면 기존 이미지 유지
                        self.bg_scale = int(self.bg_scale * 100) / 100.0
                        self.scale_bg_scale.set(int(self.bg_scale*100))

            except ImportError:
                 pass # load_background에서 이미 처리됨

        self.draw_scene(current_steer=math.radians(self.scale_angle.get()))
        self._save_config() # Save the updated background transform

    def load_background(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if not file_path:
            return
        
        if self._load_background_from_path(file_path):
            self.bg_image_path = file_path
            # Reset offsets and scale when a new image is loaded
            self.bg_offset_x = 0.0
            self.bg_offset_y = 0.0
            self.bg_scale = 1.0
            if hasattr(self, 'scale_bg_x'): # Check if controls are initialized
                self.scale_bg_x.set(0)
                self.scale_bg_y.set(0)
                self.scale_bg_scale.set(100)
            
            self._save_config() # Save the new background config
            self.draw_scene(current_steer=math.radians(self.scale_angle.get()))

    def draw_scene(self, current_steer=0.0):
        self.canvas.delete("all")
        
        if self.auto_follow.get():
            view_offset_x = self.x * self.pixels_per_meter
            view_offset_y = self.y * self.pixels_per_meter
        else:
            view_offset_x = -self.manual_offset_x
            view_offset_y = -self.manual_offset_y

        abs_cx, abs_cy = self.canvas_width/2, self.canvas_height/2
        
        # 1. Background image
        if self.bg_photo:
            bg_screen_x, bg_screen_y = self.to_screen(self.bg_offset_x, self.bg_offset_y, view_offset_x, view_offset_y)
            self.canvas.create_image(bg_screen_x, bg_screen_y, image=self.bg_photo)

        # 2. Grid
        gap = 5*self.pixels_per_meter; w, h = self.canvas_width, self.canvas_height
        grid_origin_x = abs_cx - view_offset_x
        grid_origin_y = abs_cy + view_offset_y
        start_x = grid_origin_x % gap
        start_y = grid_origin_y % gap
        for i in range(int(-w/gap)-2, int(w/gap)+2): self.canvas.create_line(start_x + i*gap, 0, start_x + i*gap, h, fill="#e0e0e0")
        for i in range(int(-h/gap)-2, int(h/gap)+2): self.canvas.create_line(0, start_y + i*gap, w, start_y + i*gap, fill="#e0e0e0")

        # 3. Wheel paths
        for name, path in self.wheel_paths.items():
            if len(path)>1:
                color="#00a0a0" if 't_' in name else "#ff8080"; 
                if 'front' in name: color="#00ffff"
                pts=[c for p in list(path) for c in self.to_screen(*p, view_offset_x, view_offset_y)]
                self.canvas.create_line(pts, fill=color, width=1)

        # 4. Truck bodies (cab, swing areas, container)
        cab_len = 2.5; cab_center_dist = self.tractor_wb - 0.5 
        cab_cx = self.x + cab_center_dist * math.cos(self.yaw_tractor); cab_cy = self.y + cab_center_dist * math.sin(self.yaw_tractor)
        self.draw_rect_body(cab_cx, cab_cy, self.yaw_tractor, cab_len, self.tractor_width, "#8888ff", view_offset_x, view_offset_y)
        
        swing_area_len = 3.0
        swing_area_width = self.tractor_width
        swing_center_offset = 0.5
        swing_cx = self.x + swing_center_offset * math.cos(self.yaw_tractor)
        swing_cy = self.y + swing_center_offset * math.sin(self.yaw_tractor)
        self.draw_rect_body(swing_cx, swing_cy, self.yaw_tractor, swing_area_len, swing_area_width, "#99bbaa", view_offset_x, view_offset_y)
        
        trailer_swing_len = 2.0
        trailer_swing_center_offset = trailer_swing_len / 2.0
        swing_cx_tr = self.x - trailer_swing_center_offset * math.cos(self.yaw_trailer)
        swing_cy_tr = self.y - trailer_swing_center_offset * math.sin(self.yaw_trailer)
        self.draw_rect_body(swing_cx_tr, swing_cy_tr, self.yaw_trailer, trailer_swing_len, self.tractor_width, "#aaddff", view_offset_x, view_offset_y)

        total_visual_len = self.trailer_len + 1.0
        container_len = total_visual_len - trailer_swing_len
        container_center_offset = trailer_swing_len + (container_len / 2.0)
        container_cx = self.x - container_center_offset * math.cos(self.yaw_trailer)
        container_cy = self.y - container_center_offset * math.sin(self.yaw_trailer)
        self.draw_rect_body(container_cx, container_cy, self.yaw_trailer, container_len, self.tractor_width, "#ffaaaa", view_offset_x, view_offset_y)
        
        # 5. Wheels
        wheel_positions = self._get_world_wheel_positions(current_steer)
        for name, pos in wheel_positions.items():
            is_front='front' in name; yaw=self.yaw_tractor if 't_' in name else self.yaw_trailer; steer=current_steer if is_front else 0.0
            self.draw_wheel(pos[0], pos[1], yaw, steer, not is_front, view_offset_x, view_offset_y)
        
        # 6. Kingpin
        kpx, kpy = self.to_screen(self.x, self.y, view_offset_x, view_offset_y)
        self.canvas.create_oval(kpx-4, kpy-4, kpx+4, kpy+4, fill="yellow", outline="black")
        
        # 7. Info text (ALWAYS LAST to be on top)
        current_angle_diff_rad = self.yaw_tractor - self.yaw_trailer
        current_angle_diff_deg = abs(math.degrees(current_angle_diff_rad))
        steer_deg = self.scale_angle.get()
        
        info_text = f"꺾임 각도: {current_angle_diff_deg:.1f}° | 조향각: {steer_deg:.1f}°"
        self.canvas.create_text(self.canvas_width / 2, 30, text=info_text, 
                                font=("Arial", 32, "bold"), fill="blue", tags="info_display", anchor='n')

    def draw_wheel(self, cx, cy, yaw, steer, is_dual, view_offset_x, view_offset_y):
        wheel_len, wheel_width=0.8, 0.3 if not is_dual else 0.5; final_angle=yaw+steer
        # --------------------------------------------------------------------------------------------------
        # draw_wheel 내부의 'width' 변수명 오류 수정: wheel_width로 변경
        # --------------------------------------------------------------------------------------------------
        corners=[(wheel_len/2,wheel_width/2), (wheel_len/2,-wheel_width/2), (-wheel_len/2,-wheel_width/2), (-wheel_len/2,wheel_width/2)]
        scr_pts=[c for dx,dy in corners for c in self.to_screen(cx+dx*math.cos(final_angle)-dy*math.sin(final_angle), cy+dx*math.sin(final_angle)+dy*math.cos(final_angle), view_offset_x, view_offset_y)]
        self.canvas.create_polygon(scr_pts, fill="black", outline="#333")

    def draw_rect_body(self, cx, cy, yaw, length, width, color, view_offset_x, view_offset_y):
        corners=[(length/2,width/2), (length/2,-width/2), (-length/2,-width/2), (-length/2,width/2)]
        scr_pts=[c for dx,dy in corners for c in self.to_screen(cx+dx*math.cos(yaw)-dy*math.sin(yaw), cy+dx*math.sin(yaw)+dy*math.cos(yaw), view_offset_x, view_offset_y)]
        self.canvas.create_polygon(scr_pts, fill=color, outline="black")

if __name__ == "__main__":
    root = tk.Tk()
    app = TractorTrailerSim(root)
    root.mainloop()
