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
        self.root.title("트랙터-트레일러 주행 시뮬레이터 (v1.7 - 프리셋 기능 확장 및 버그 수정)")

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
        
        # --- History & Presets ---
        self.history = deque(maxlen=50)
        self._ignore_history_selection = False
        self.presets = {}
        self.PRESETS_FILE = "truck_sim_presets.json"
        self.preset_load_buttons = []
        
        self.free_set_mode = False # Flag to indicate if free set mode is active
        self.ghost_state = {}     # Stores the tentative state of the ghost car
        self.previous_canvas_bindings = {} # To store canvas bindings before free set mode
        self.free_set_control_frame = None # Frame for Free Set buttons

        self.dragging_part = None # 'tractor', 'trailer', 'kingpin', or None
        self.start_drag_x = 0
        self.start_drag_y = 0
        self.start_part_x = 0 # World x of the part being dragged
        self.start_part_y = 0 # World y of the part being dragged
        self.start_part_yaw = 0 # Yaw of the part being dragged
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.free_set_initial_state = {} # Stores the state when Free Set mode was activated

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
        self.setup_preset_panel()   # New method for preset panel
        self.setup_history_panel()  # Existing method for history panel
        self._load_config()         # Load general config
        self._load_presets()        # New method to load presets from file

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

    def setup_preset_panel(self):
        preset_frame = tk.LabelFrame(self.right_frame, text="--- 프리셋 (Preset) ---", padx=5, pady=5)
        preset_frame.pack(fill=tk.X, pady=(0, 10))

        num_presets = 5
        for i in range(num_presets):
            slot_num = i + 1
            
            load_btn = tk.Button(preset_frame, text=f"프리셋 {slot_num} 로드", command=lambda s=slot_num: self._load_preset(s), state=tk.DISABLED)
            load_btn.grid(row=i, column=0, sticky="ew", padx=2, pady=2)
            self.preset_load_buttons.append(load_btn)

            save_btn = tk.Button(preset_frame, text=f"프리셋 {slot_num} 저장", command=lambda s=slot_num: self._save_preset(s))
            save_btn.grid(row=i, column=1, sticky="ew", padx=2, pady=2)

        preset_frame.grid_columnconfigure((0, 1), weight=1)

        ttk.Separator(preset_frame, orient='horizontal').grid(row=num_presets, column=0, columnspan=2, sticky='ew', pady=10)

        tk.Button(preset_frame, text="Free Set", command=self._activate_free_set_mode).grid(row=num_presets + 1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

    def _load_presets(self):
        if os.path.exists(self.PRESETS_FILE):
            try:
                with open(self.PRESETS_FILE, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
                self.logger.info("프리셋 로드 완료.")
                # Update button states based on loaded presets
                for i, btn in enumerate(self.preset_load_buttons):
                    if f"slot_{i+1}" in self.presets:
                        btn.config(state=tk.NORMAL)
            except Exception as e:
                self.logger.error(f"프리셋 로드 실패: {e}")
        else:
            self.logger.info("저장된 프리셋 파일이 없습니다.")

    def _save_presets(self):
        try:
            with open(self.PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=4)
            self.logger.info("프리셋 저장 완료.")
        except Exception as e:
            self.logger.error(f"프리셋 저장 실패: {e}")

    def _save_preset(self, slot_number):
        slot_key = f"slot_{slot_number}"
        self.presets[slot_key] = self._capture_state()
        self._save_presets()
        self.preset_load_buttons[slot_number - 1].config(state=tk.NORMAL)
        messagebox.showinfo("프리셋 저장", f"현재 상태를 프리셋 {slot_number}에 저장했습니다.")

    def _load_preset(self, slot_number):
        slot_key = f"slot_{slot_number}"
        if slot_key in self.presets:
            state_to_restore = self.presets[slot_key]
            self._restore_state(state_to_restore)
            
            # Clear and reset history
            self.history.clear()
            description = f"프리셋 {slot_number} 로드"
            self.history.append((description, self._capture_state()))
            self._update_history_listbox()

            messagebox.showinfo("프리셋 로드", f"프리셋 {slot_number}을(를) 로드했습니다.")
        else:
            messagebox.showerror("오류", f"저장된 프리셋 {slot_number}이(가) 없습니다.")

    def _activate_free_set_mode(self):
        self.logger.info("Free Set 모드 활성화.")
        self.free_set_mode = True
        self.free_set_initial_state = self._capture_state() # Save state for cancellation
        self.ghost_state = self.free_set_initial_state.copy() # Initialize ghost state with current state
        
        # Disable main simulation controls
        for child in self.control_frame.winfo_children():
            try:
                if child not in [self.scale_trailer_len, self.trailer_len_label]: # Keep trailer length adjustable
                    child.config(state=tk.DISABLED)
            except tk.TclError: # Catch TclError for widgets that don't have a 'state' option
                pass
        
        # Store current canvas bindings and unbind them
        self.previous_canvas_bindings['<ButtonPress-1>'] = self.canvas.bind('<ButtonPress-1>')
        self.previous_canvas_bindings['<B1-Motion>'] = self.canvas.bind('<B1-Motion>')
        self.previous_canvas_bindings['<ButtonRelease-1>'] = self.canvas.bind('<ButtonRelease-1>')
        self.previous_canvas_bindings['<MouseWheel>'] = self.canvas.bind('<MouseWheel>')

        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        self.canvas.unbind('<MouseWheel>')

        # Bind new events for Free Set mode
        self.canvas.bind("<ButtonPress-1>", self._free_set_start_manipulation)
        self.canvas.bind("<B1-Motion>", self._free_set_manipulation)
        self.canvas.bind("<ButtonRelease-1>", self._free_set_end_manipulation)
        self.canvas.bind("<MouseWheel>", self._free_set_rotate_tractor_yaw) # Mouse wheel for tractor rotation

        # Create Free Set control frame
        self.free_set_control_frame = tk.Frame(self.right_frame, padx=5, pady=5, bg="lightyellow")
        self.free_set_control_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(self.free_set_control_frame, text="--- Free Set Mode ---", font=("Arial", 10, "bold"), bg="lightyellow").pack(pady=(0,5))
        tk.Button(self.free_set_control_frame, text="Save Free Set", command=self._save_free_set_state, fg="green").pack(fill=tk.X, pady=2)
        tk.Button(self.free_set_control_frame, text="Cancel Free Set", command=self._cancel_free_set_state, fg="red").pack(fill=tk.X, pady=2)

        # Initially draw ghost car
        self.draw_scene()

    def _deactivate_free_set_mode(self):
        self.logger.info("Free Set 모드 비활성화.")
        self.free_set_mode = False
        self.ghost_state = {} # Clear ghost state
        
        # Re-enable main simulation controls
        for child in self.control_frame.winfo_children():
            try:
                child.config(state=tk.NORMAL)
            except tk.TclError: # Catch TclError for widgets that don't have a 'state' option
                pass
        
        # Restore original canvas bindings
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        self.canvas.unbind('<MouseWheel>')

        if self.previous_canvas_bindings.get('<ButtonPress-1>'):
            self.canvas.bind('<ButtonPress-1>', self.previous_canvas_bindings['<ButtonPress-1>'])
        if self.previous_canvas_bindings.get('<B1-Motion>'):
            self.canvas.bind('<B1-Motion>', self.previous_canvas_bindings['<B1-Motion>'])
        # Add back general canvas binding if it exists
        if self.previous_canvas_bindings.get('<ButtonPress-1>') == self._pan_start:
             self.canvas.bind("<ButtonPress-1>", self._pan_start)
        if self.previous_canvas_bindings.get('<B1-Motion>') == self._pan_move:
             self.canvas.bind("<B1-Motion>", self._pan_move)


        # Destroy Free Set control frame
        if self.free_set_control_frame:
            self.free_set_control_frame.destroy()
            self.free_set_control_frame = None
        
        # Redraw scene to remove ghost car
        self.draw_scene()

    def _save_free_set_state(self):
        if self.free_set_mode:
            self.x = self.ghost_state['x']
            self.y = self.ghost_state['y']
            self.yaw_tractor = self.ghost_state['yaw_tractor']
            self.yaw_trailer = self.ghost_state['yaw_trailer']
            self._initialize_paths() # Re-initialize paths at the new location
            self.history.clear() # Clear history on manual state change
            self._add_to_history("Free Set 상태 저장")
            messagebox.showinfo("Free Set", "Free Set 상태가 저장되었습니다.")
            self._deactivate_free_set_mode()

    def _cancel_free_set_state(self):
        if self.free_set_mode:
            self._restore_state(self.free_set_initial_state) # Restore the state from before Free Set activation
            self._deactivate_free_set_mode()
            messagebox.showinfo("Free Set", "Free Set 상태 변경이 취소되었습니다.")
            # draw_scene is called by _deactivate_free_set_mode already

    def to_world(self, screen_x, screen_y):
        if self.auto_follow.get():
            view_offset_x = self.x * self.pixels_per_meter
            view_offset_y = self.y * self.pixels_per_meter
        else:
            view_offset_x = -self.manual_offset_x
            view_offset_y = -self.manual_offset_y

        abs_cx, abs_cy = self.canvas_width / 2, self.canvas_height / 2
        
        world_x = (screen_x - abs_cx + view_offset_x) / self.pixels_per_meter
        world_y = (abs_cy - screen_y + view_offset_y) / self.pixels_per_meter
        return world_x, world_y
    
    def _get_world_tractor_corners(self, state, steer_rad=0.0):
        cab_len = 2.5; cab_center_dist = self.tractor_wb - 0.5 
        cab_cx = state['x'] + cab_center_dist * math.cos(state['yaw_tractor'])
        cab_cy = state['y'] + cab_center_dist * math.sin(state['yaw_tractor'])
        return self._get_rect_corners(cab_cx, cab_cy, state['yaw_tractor'], cab_len, self.tractor_width)

    def _get_world_trailer_corners(self, state):
        total_visual_len = self.trailer_len + 1.0
        trailer_swing_len = 2.0
        container_len = total_visual_len - trailer_swing_len
        container_center_offset = trailer_swing_len + (container_len / 2.0)
        container_cx = state['x'] - container_center_offset * math.cos(state['yaw_trailer'])
        container_cy = state['y'] - container_center_offset * math.sin(state['yaw_trailer'])
        return self._get_rect_corners(container_cx, container_cy, state['yaw_trailer'], container_len, self.tractor_width)

    def _get_rect_corners(self, cx, cy, yaw, length, width):
        corners_local=[(length/2,width/2), (length/2,-width/2), (-length/2,-width/2), (-length/2,width/2)]
        corners_world = []
        for lx, ly in corners_local:
            wx = cx + lx * math.cos(yaw) - ly * math.sin(yaw)
            wy = cy + lx * math.sin(yaw) + ly * math.cos(yaw)
            corners_world.append((wx, wy))
        return corners_world

    def _get_tractor_front_center(self, state):
        # Calculate the center of the front axle of the tractor
        # The tractor's pivot point (self.x, self.y) is the rear axle.
        # Front axle is tractor_wb meters forward along yaw_tractor
        front_axle_x = state['x'] + self.tractor_wb * math.cos(state['yaw_tractor'])
        front_axle_y = state['y'] + self.tractor_wb * math.sin(state['yaw_tractor'])
        return front_axle_x, front_axle_y

    def _get_trailer_rear_center(self, state):
        # Calculate the center of the rear axle of the trailer
        # The kingpin is at state['x'], state['y']
        # The trailer's visual rear is at -(self.trailer_len + 1.0) meters along yaw_trailer from kingpin
        # For simplicity, let's say the rear most point of the trailer
        total_visual_len = self.trailer_len + 1.0
        rear_x = state['x'] - total_visual_len * math.cos(state['yaw_trailer'])
        rear_y = state['y'] - total_visual_len * math.sin(state['yaw_trailer'])
        return rear_x, rear_y

    def _is_point_in_polygon(self, point, polygon):
        # Ray casting algorithm
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def _free_set_start_manipulation(self, event):
        self.free_set_initial_state = self.ghost_state.copy() # Save state for cancellation
        world_x, world_y = self.to_world(event.x, event.y)
        self.start_drag_x = event.x
        self.start_drag_y = event.y

        # Check for kingpin (highest priority)
        dist_to_kingpin = math.hypot(world_x - self.ghost_state['x'], world_y - self.ghost_state['y'])
        if dist_to_kingpin * self.pixels_per_meter < 10: # within 10 pixels of kingpin
            self.dragging_part = 'kingpin'
            self.start_part_x = self.ghost_state['x']
            self.start_part_y = self.ghost_state['y']
            self.start_part_yaw = self.ghost_state['yaw_tractor'] # Store tractor yaw for rotation ref
            self.logger.info("Free Set: Kingpin 드래그 시작.")
            return

        # Check for tractor front (for rotation)
        tractor_front_x, tractor_front_y = self._get_tractor_front_center(self.ghost_state)
        dist_to_tractor_front = math.hypot(world_x - tractor_front_x, world_y - tractor_front_y)
        if dist_to_tractor_front * self.pixels_per_meter < 20: # Wider click area for rotation
            self.dragging_part = 'tractor_front_rotate'
            self.start_part_x = tractor_front_x
            self.start_part_y = tractor_front_y
            self.start_part_yaw = self.ghost_state['yaw_tractor']
            self.logger.info("Free Set: 트랙터 전면 회전 드래그 시작.")
            return

        # Check for trailer rear (for articulation)
        trailer_rear_x, trailer_rear_y = self._get_trailer_rear_center(self.ghost_state)
        dist_to_trailer_rear = math.hypot(world_x - trailer_rear_x, world_y - trailer_rear_y)
        if dist_to_trailer_rear * self.pixels_per_meter < 20: # Wider click area for articulation
            self.dragging_part = 'trailer_rear_articulate'
            # For articulation, reference point should be the kingpin, not the dragged point
            self.start_part_x = self.ghost_state['x']
            self.start_part_y = self.ghost_state['y']
            self.start_part_yaw = self.ghost_state['yaw_trailer']
            self.logger.info("Free Set: 트레일러 후면 꺾임 드래그 시작.")
            return

        # Check for tractor body (moves tractor, thus kingpin and trailer)
        cab_len = 2.5; cab_center_dist = self.tractor_wb - 0.5 
        cab_cx = self.ghost_state['x'] + cab_center_dist * math.cos(self.ghost_state['yaw_tractor'])
        cab_cy = self.ghost_state['y'] + cab_center_dist * math.sin(self.ghost_state['yaw_tractor'])
        tractor_body_corners = self._get_rect_corners(cab_cx, cab_cy, self.ghost_state['yaw_tractor'], cab_len, self.tractor_width)
        if self._is_point_in_polygon((world_x, world_y), tractor_body_corners):
            self.dragging_part = 'tractor_body'
            self.start_part_x = self.ghost_state['x']
            self.start_part_y = self.ghost_state['y']
            self.logger.info("Free Set: 트랙터 본체 드래그 시작.")
            return

        # Check for trailer body (moves trailer, kingpin, and tractor together)
        total_visual_len = self.trailer_len + 1.0
        trailer_swing_len = 2.0
        container_len = total_visual_len - trailer_swing_len
        container_center_offset = trailer_swing_len + (container_len / 2.0)
        container_cx = self.ghost_state['x'] - container_center_offset * math.cos(self.ghost_state['yaw_trailer'])
        container_cy = self.ghost_state['y'] - container_center_offset * math.sin(self.ghost_state['yaw_trailer'])
        trailer_body_corners = self._get_rect_corners(container_cx, container_cy, self.ghost_state['yaw_trailer'], container_len, self.tractor_width)
        if self._is_point_in_polygon((world_x, world_y), trailer_body_corners):
            self.dragging_part = 'trailer_body'
            self.start_part_x = self.ghost_state['x']
            self.start_part_y = self.ghost_state['y']
            self.logger.info("Free Set: 트레일러 본체 드래그 시작.")
            return
        
        self.last_mouse_x = event.x # For rotation reference if nothing is dragged
        self.last_mouse_y = event.y

    def _free_set_manipulation(self, event):
        if self.dragging_part:
            world_x, world_y = self.to_world(event.x, event.y)
            
            if self.dragging_part == 'kingpin' or self.dragging_part == 'tractor_body' or self.dragging_part == 'trailer_body':
                # Move kingpin directly
                self.ghost_state['x'] = world_x
                self.ghost_state['y'] = world_y

            elif self.dragging_part == 'tractor_front_rotate':
                # Tractor rotates around its rear axle (which is effectively the kingpin location)
                # Kingpin position (ghost_state['x'], ghost_state['y']) remains fixed.
                # Calculate new yaw_tractor based on the angle from the kingpin to the current mouse position.
                dx = world_x - self.ghost_state['x']
                dy = world_y - self.ghost_state['y']
                new_yaw_tractor = math.atan2(dy, dx)
                
                self.ghost_state['yaw_tractor'] = new_yaw_tractor
                
                # Adjust trailer yaw to maintain the original articulation angle from when drag started.
                initial_articulation_angle = self.free_set_initial_state['yaw_tractor'] - self.free_set_initial_state['yaw_trailer']
                self.ghost_state['yaw_trailer'] = new_yaw_tractor - initial_articulation_angle

            elif self.dragging_part == 'trailer_rear_articulate':
                # Trailer articulates around the fixed kingpin.
                # Kingpin position (ghost_state['x'], ghost_state['y']) and yaw_tractor remain fixed.
                # Calculate new yaw_trailer based on the angle from the kingpin to the current mouse position.
                dx = world_x - self.ghost_state['x']
                dy = world_y - self.ghost_state['y']
                new_yaw_trailer = math.atan2(dy, dx) + math.pi # Add pi to flip 180 degrees for rear drag
                
                # Normalize angle to be within -pi to pi range if needed
                if new_yaw_trailer > math.pi:
                    new_yaw_trailer -= 2 * math.pi
                elif new_yaw_trailer < -math.pi:
                    new_yaw_trailer += 2 * math.pi
                
                self.ghost_state['yaw_trailer'] = new_yaw_trailer
                
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.draw_scene()
    def _free_set_end_manipulation(self, event):
        self.dragging_part = None
        self.logger.info("Free Set: 드래그 종료.")

    def _free_set_rotate_tractor_yaw(self, event):
        if self.free_set_mode:
            # For Windows, event.delta is typically 120 per "notch"
            # For MacOS, event.delta is typically +1/-1 or similar
            if self.root.tk.call('tk', 'windowingsystem') == 'aqua': # MacOS
                angle_delta = event.delta * 0.01 # Adjust sensitivity for MacOS
            else: # Windows/Linux
                angle_delta = event.delta / 120 * 0.05 # Adjust sensitivity for Windows/Linux
            
            # Rotation around current kingpin
            old_yaw_tractor = self.ghost_state['yaw_tractor']
            old_yaw_trailer = self.ghost_state['yaw_trailer']
            
            # We want to rotate the tractor around the kingpin
            # And the trailer's yaw should adjust to maintain articulation
            
            # Update tractor yaw
            self.ghost_state['yaw_tractor'] += angle_delta

            # Calculate new trailer yaw to maintain articulation relative to new tractor yaw
            # Current articulation angle = old_yaw_tractor - old_yaw_trailer
            # New yaw_trailer = new_yaw_tractor - current_articulation_angle
            
            articulation_angle = old_yaw_tractor - old_yaw_trailer
            self.ghost_state['yaw_trailer'] = self.ghost_state['yaw_tractor'] - articulation_angle

            self.draw_scene()
            
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
        self._initialize_paths() # Re-initialize paths to reflect new trailer length based on current vehicle state
        self.draw_scene(current_steer=math.radians(self.scale_angle.get())) # Redraw scene with new length

    def _update_target_angle_display(self, val):
        self.target_angle_display_label.config(text=f"{float(val):.0f}°")

    def _initialize_paths(self):
        self.wheel_paths.clear()
        current_state = self._capture_state()
        for name, pos in self._get_world_wheel_positions(state=current_state).items(): self.wheel_paths[name]=deque([pos], maxlen=self.max_path_points)
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
        
    def _get_world_wheel_positions(self, steer_rad=0.0, state=None):
        if state is None:
            state = {'x': self.x, 'y': self.y, 'yaw_tractor': self.yaw_tractor, 'yaw_trailer': self.yaw_trailer}

        positions={}; tractor_axles, trailer_axles=self._get_axle_definitions(); half_w=self.tractor_width/2.0
        # 트랙터 축 계산
        for name, dist in tractor_axles.items():
            is_front = (name == 'front')
            axle_x = state['x'] + dist * math.cos(state['yaw_tractor'])
            axle_y = state['y'] + dist * math.sin(state['yaw_tractor'])
            
            final_steer = steer_rad if is_front else 0.0
            yaw_eff = state['yaw_tractor'] + final_steer
            
            # 바퀴 위치 계산
            wl_x = axle_x + half_w * math.cos(yaw_eff + math.pi/2)
            wl_y = axle_y + half_w * math.sin(yaw_eff + math.pi/2)
            wr_x = axle_x - half_w * math.cos(yaw_eff + math.pi/2)
            wr_y = axle_y - half_w * math.sin(yaw_eff + math.pi/2)
            positions[f't_{name}_l']=(wl_x,wl_y); positions[f't_{name}_r']=(wr_x,wr_y)

        # 트레일러 기준점 (킹핀)
        kingpin_x = state['x'] 
        kingpin_y = state['y']

        # 트레일러 축 계산
        for name, dist in trailer_axles.items():
            # 트레일러의 실제 기준점은 킹핀에서 트레일러 길이만큼 뒤에 있습니다.
            # 하지만 각 축의 위치는 트레일러의 기하학적 중심을 기준으로 계산하는 것이 더 직관적일 수 있습니다.
            # 여기서는 트레일러의 회전 중심(뒷바퀴 축의 중심)을 기준으로 계산합니다.
            # 트레일러 회전 중심 위치
            trailer_pivot_x = kingpin_x - self.trailer_len * math.cos(state['yaw_trailer'])
            trailer_pivot_y = kingpin_y - self.trailer_len * math.sin(state['yaw_trailer'])

            axle_x = trailer_pivot_x + dist * math.cos(state['yaw_trailer'])
            axle_y = trailer_pivot_y + dist * math.sin(state['yaw_trailer'])
            
            # 바퀴 위치 계산
            wl_x = axle_x + half_w * math.sin(state['yaw_trailer'])
            wl_y = axle_y - half_w * math.cos(state['yaw_trailer'])
            wr_x = axle_x - half_w * math.sin(state['yaw_trailer'])
            wr_y = axle_y + half_w * math.cos(state['yaw_trailer'])
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
            self.trailer_len_var.trace_add('write', self._update_trailer_len)
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
        for name, pos in self._get_world_wheel_positions(steer_rad, state={'x': self.x, 'y': self.y, 'yaw_tractor': self.yaw_tractor, 'yaw_trailer': self.yaw_trailer}).items():
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

        # 3. Wheel paths (always for the actual truck)
        for name, path in self.wheel_paths.items():
            if len(path)>1:
                color="#00a0a0" if 't_' in name else "#ff8080"; 
                if 'front' in name: color="#00ffff"
                pts=[c for p in list(path) for c in self.to_screen(*p, view_offset_x, view_offset_y)]
                self.canvas.create_line(pts, fill=color, width=1)
        
        # Draw actual truck
        current_actual_state = {'x': self.x, 'y': self.y, 'yaw_tractor': self.yaw_tractor, 'yaw_trailer': self.yaw_trailer}
        self._draw_truck(current_actual_state, current_steer, view_offset_x, view_offset_y)

        # Draw ghost car if Free Set mode is active
        if self.free_set_mode:
            # When drawing ghost car, ensure we use its yaw_tractor value for steer calculation for visualization
            ghost_steer = math.radians(self.scale_angle.get()) # Use current steer from controls for ghost tractor wheels
            self._draw_truck(self.ghost_state, ghost_steer, view_offset_x, view_offset_y, is_ghost=True)
        
        # Calculate current angle difference
        current_angle_diff_rad = self.yaw_tractor - self.yaw_trailer
        current_angle_diff_deg = math.degrees(current_angle_diff_rad) # Use actual signed value

        # Determine direction for display (User prefers signed display for non-zero, and 0 for exact)
        if current_angle_diff_deg > 0: 
            angle_display_text = f"좌 {current_angle_diff_deg:.1f}°"
        elif current_angle_diff_deg < 0:
            angle_display_text = f"우 {abs(current_angle_diff_deg):.1f}°" # abs를 사용하여 양수로 표시
        else: # Exactly zero
            angle_display_text = f"0.0°"

        steer_deg = self.scale_angle.get()
        # Determine direction for steer angle display
        if steer_deg > 0:
            steer_display_text = f"좌 {steer_deg:.1f}°"
        elif steer_deg < 0:
            steer_display_text = f"우 {abs(steer_deg):.1f}°"
        else:
            steer_display_text = f"0.0°"
        
        info_text_str = f"현재 꺾인 각도: {angle_display_text} | 조향각: {steer_display_text}"
        
        # Calculate bounding box for the text to draw a background rectangle
        # A rough estimate for text width, will be more accurate after creating text
        # Using a fixed width multiplier and font size to estimate
        text_width_estimate = len(info_text_str) * 25 # Increased multiplier
        text_height_estimate = 40 # Based on font size 32
        
        # Position the rectangle behind the text
        text_center_x = self.canvas_width / 2
        text_top_y = 30
        
        rect_x1 = text_center_x - text_width_estimate / 2 - 20 # Increased padding
        rect_y1 = text_top_y - 5
        rect_x2 = text_center_x + text_width_estimate / 2 + 20 # Increased padding
        rect_y2 = text_top_y + text_height_estimate + 5
        
        self.canvas.create_rectangle(rect_x1, rect_y1, rect_x2, rect_y2, fill="lightgray", outline="lightgray", tags="info_display_bg")
        
        self.canvas.create_text(text_center_x, text_top_y, text=info_text_str, 
                                font=("Arial", 32, "bold"), fill="blue", tags="info_display", anchor='n')

    def draw_wheel(self, cx, cy, yaw, steer, is_dual, view_offset_x, view_offset_y, fill_color="black", outline_color="#333", dash=None):
        wheel_len, wheel_width=0.8, 0.3 if not is_dual else 0.5; final_angle=yaw+steer
        # --------------------------------------------------------------------------------------------------
        # draw_wheel 내부의 'width' 변수명 오류 수정: wheel_width로 변경
        # --------------------------------------------------------------------------------------------------
        corners=[(wheel_len/2,wheel_width/2), (wheel_len/2,-wheel_width/2), (-wheel_len/2,-wheel_width/2), (-wheel_len/2,wheel_width/2)]
        scr_pts=[c for dx,dy in corners for c in self.to_screen(cx+dx*math.cos(final_angle)-dy*math.sin(final_angle), cy+dx*math.sin(final_angle)+dy*math.cos(final_angle), view_offset_x, view_offset_y)]
        self.canvas.create_polygon(scr_pts, fill=fill_color, outline=outline_color, dash=dash)

    def draw_rect_body(self, cx, cy, yaw, length, width, color, view_offset_x, view_offset_y, outline_color="black", dash=None):
        corners=[(length/2,width/2), (length/2,-width/2), (-length/2,-width/2), (-length/2,width/2)]
        scr_pts=[c for dx,dy in corners for c in self.to_screen(cx+dx*math.cos(yaw)-dy*math.sin(yaw), cy+dx*math.sin(yaw)+dy*math.cos(yaw), view_offset_x, view_offset_y)]
        self.canvas.create_polygon(scr_pts, fill=color, outline=outline_color, dash=dash)

    def _draw_truck(self, state, steer_rad, view_offset_x, view_offset_y, is_ghost=False):
        # 4. Truck bodies (cab, swing areas, container)
        cab_len = 2.5; cab_center_dist = self.tractor_wb - 0.5 
        cab_cx = state['x'] + cab_center_dist * math.cos(state['yaw_tractor']); cab_cy = state['y'] + cab_center_dist * math.sin(state['yaw_tractor'])
        
        color_cab = "#8888ff" if not is_ghost else "lightgray"
        color_swing = "#99bbaa" if not is_ghost else "lightgray"
        color_trailer_swing = "#aaddff" if not is_ghost else "lightgray"
        color_container = "#ffaaaa" if not is_ghost else "lightgray"
        outline_color = "black" if not is_ghost else "darkgray"
        dash_pattern = None if not is_ghost else (3, 2)

        self.draw_rect_body(cab_cx, cab_cy, state['yaw_tractor'], cab_len, self.tractor_width, color_cab, view_offset_x, view_offset_y, outline_color=outline_color, dash=dash_pattern)
        
        swing_area_len = 3.0
        swing_area_width = self.tractor_width
        swing_center_offset = 0.5
        swing_cx = state['x'] + swing_center_offset * math.cos(state['yaw_tractor'])
        swing_cy = state['y'] + swing_center_offset * math.sin(state['yaw_tractor'])
        self.draw_rect_body(swing_cx, swing_cy, state['yaw_tractor'], swing_area_len, swing_area_width, color_swing, view_offset_x, view_offset_y, outline_color=outline_color, dash=dash_pattern)
        
        trailer_swing_len = 2.0
        trailer_swing_center_offset = trailer_swing_len / 2.0
        swing_cx_tr = state['x'] - trailer_swing_center_offset * math.cos(state['yaw_trailer'])
        swing_cy_tr = state['y'] - trailer_swing_center_offset * math.sin(state['yaw_trailer'])
        self.draw_rect_body(swing_cx_tr, swing_cy_tr, state['yaw_trailer'], trailer_swing_len, self.tractor_width, color_trailer_swing, view_offset_x, view_offset_y, outline_color=outline_color, dash=dash_pattern)

        total_visual_len = self.trailer_len + 1.0
        container_len = total_visual_len - trailer_swing_len
        container_center_offset = trailer_swing_len + (container_len / 2.0)
        container_cx = state['x'] - container_center_offset * math.cos(state['yaw_trailer'])
        container_cy = state['y'] - container_center_offset * math.sin(state['yaw_trailer'])
        self.draw_rect_body(container_cx, container_cy, state['yaw_trailer'], container_len, self.tractor_width, color_container, view_offset_x, view_offset_y, outline_color=outline_color, dash=dash_pattern)
        
        # 5. Wheels
        wheel_positions = self._get_world_wheel_positions(steer_rad, state) # Pass state to get wheel positions
        for name, pos in wheel_positions.items():
            is_front='front' in name; yaw=state['yaw_tractor'] if 't_' in name else state['yaw_trailer']; steer=steer_rad if is_front else 0.0
            wheel_color = "black" if not is_ghost else "darkgray"
            self.draw_wheel(pos[0], pos[1], yaw, steer, not is_front, view_offset_x, view_offset_y, fill_color=wheel_color, outline_color=outline_color, dash=dash_pattern)
        
        # 6. Kingpin
        kpx, kpy = self.to_screen(state['x'], state['y'], view_offset_x, view_offset_y)
        kingpin_color = "yellow" if not is_ghost else "darkgray"
        self.canvas.create_oval(kpx-4, kpy-4, kpx+4, kpy+4, fill=kingpin_color, outline=outline_color, dash=dash_pattern)

if __name__ == "__main__":
    root = tk.Tk()
    app = TractorTrailerSim(root)
    root.mainloop()
