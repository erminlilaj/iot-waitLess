from pathlib import Path
import tkinter as tk

import visual_simulator as base
from traffic_logic import Decision, Phase, Side, demand_score


class EmergencyVisualTrafficSimulator(base.VisualTrafficSimulator):
    def __init__(self, root: tk.Tk):
        self.emergency_var = tk.StringVar(master=root, value="")
        self.emergency_buffer_px = 120.0
        self.ambulance_sequence = 0
        self.esp_board_image = self._load_esp_board_image(root)
        super().__init__(root)
        self.root.title("Wait Less - Emergency Priority Simulator")
        self._add_emergency_controls()

    def reset(self) -> None:
        self.ambulance_sequence = 0
        super().reset()

    def _add_emergency_controls(self) -> None:
        card = tk.Frame(self.panel, bg="#f7f0ef", relief="groove", bd=1)
        card.pack(anchor="w", fill=tk.X, pady=(0, 12), after=self.control_card)

        tk.Label(
            card,
            text="Emergency Override",
            font=("Segoe UI", 11, "bold"),
            bg="#f7f0ef",
            fg="#7a1f1f",
            padx=10,
            pady=8,
        ).pack(anchor="w")

        tk.Label(
            card,
            text="Dispatch an ambulance from any direction.\nIf its road is red, the current green road enters yellow,\nthen the ambulance road gets priority green.",
            justify="left",
            font=("Segoe UI", 9),
            bg="#f7f0ef",
            fg="#6a4a4a",
            padx=10,
        ).pack(anchor="w", pady=(0, 6))

        button_grid = tk.Frame(card, bg="#f7f0ef")
        button_grid.pack(anchor="w", padx=8, pady=(0, 8))

        buttons = [
            ("north", "Ambulance N"),
            ("south", "Ambulance S"),
            ("east", "Ambulance E"),
            ("west", "Ambulance W"),
        ]

        for index, (direction, label) in enumerate(buttons):
            tk.Button(
                button_grid,
                text=label,
                width=14,
                command=lambda d=direction: self.dispatch_ambulance(d),
                bg="#d94b4b",
                fg="white",
                relief="flat",
            ).grid(row=index // 2, column=index % 2, padx=4, pady=4)

        tk.Label(
            card,
            textvariable=self.emergency_var,
            justify="left",
            font=("Consolas", 10),
            bg="#fff7f5",
            fg="#3a2a2a",
            relief="groove",
            bd=1,
            padx=10,
            pady=8,
            width=32,
            anchor="w",
        ).pack(anchor="w", fill=tk.X, padx=8, pady=(0, 8))

    def dispatch_ambulance(self, direction: str) -> None:
        lane = base.LANES[direction]
        spawn_progress = max(0.0, self._sensor_progress(lane, "far") - 36.0)
        car = base.Car(direction=direction, progress=spawn_progress, color="#ffffff")
        car.is_ambulance = True
        car.request_order = self.ambulance_sequence
        self.ambulance_sequence += 1
        self.cars.append(car)

    def _active_ambulances(self) -> list[base.Car]:
        active = []
        for car in self.cars:
            if not getattr(car, "is_ambulance", False):
                continue
            lane = base.LANES[car.direction]
            if car.progress < lane.stop_progress + self.emergency_buffer_px:
                active.append(car)
        active.sort(key=lambda car: getattr(car, "request_order", 0))
        return active

    def _current_emergency_side(self) -> Side | None:
        active = self._active_ambulances()
        if not active:
            return None
        return base.LANES[active[0].direction].side

    def _decision_snapshot(self, side_a, side_b) -> Decision:
        current = side_a if self.controller.green_side == Side.A else side_b
        other = side_b if self.controller.green_side == Side.A else side_a
        return Decision(
            green_side=self.controller.green_side,
            phase=self.controller.phase,
            current_demand=demand_score(current),
            other_demand=demand_score(other),
            elapsed_ms=self.sim_time_ms - self.controller.phase_started_ms,
        )

    def _update_emergency_decision(self, target_side: Side, side_a, side_b) -> Decision:
        now = self.sim_time_ms

        if self.controller.green_side != target_side and self.controller.phase == Phase.GREEN:
            self.controller.phase = Phase.YELLOW
            self.controller.phase_started_ms = now

        if self.controller.phase == Phase.YELLOW and now - self.controller.phase_started_ms >= self.controller.yellow_ms:
            self.controller.green_side = target_side
            self.controller.phase = Phase.GREEN
            self.controller.phase_started_ms = now

        if self.controller.green_side == target_side and self.controller.phase == Phase.GREEN:
            self.controller.phase_started_ms = min(self.controller.phase_started_ms, now)

        return self._decision_snapshot(side_a, side_b)

    def _advance(self, dt: float) -> None:
        self.sim_time_ms += base.FRAME_MS
        self._spawn_cars(dt)

        side_a = self._build_side_telemetry(Side.A)
        side_b = self._build_side_telemetry(Side.B)
        emergency_side = self._current_emergency_side()

        if emergency_side is None:
            self.next_decision = self.controller.update(side_a, side_b, self.sim_time_ms)
        else:
            self.next_decision = self._update_emergency_decision(emergency_side, side_a, side_b)

        self.latest_side_a = side_a
        self.latest_side_b = side_b

        survivors = []
        for direction, lane in base.LANES.items():
            lane_cars = [car for car in self.cars if car.direction == direction]
            lane_cars.sort(key=lambda car: car.progress, reverse=True)

            lead_progress = None
            can_enter_intersection = self.next_decision.phase == Phase.GREEN and self.next_decision.green_side == lane.side
            far_sensor_progress = self._sensor_progress(lane, "far")

            for car in lane_cars:
                speed = base.CAR_SPEED * (1.18 if getattr(car, "is_ambulance", False) else 1.0)
                proposed_progress = car.progress + speed * dt

                if car.progress < lane.stop_progress and not can_enter_intersection:
                    proposed_progress = min(proposed_progress, lane.stop_progress - base.STOP_MARGIN)

                if lead_progress is not None:
                    proposed_progress = min(proposed_progress, lead_progress - base.CAR_SPACING)

                if proposed_progress < car.progress:
                    proposed_progress = car.progress

                car.progress = proposed_progress

                if not car.counted_incoming and car.progress >= far_sensor_progress:
                    self.incoming_counts[lane.side] += 1
                    car.counted_incoming = True

                if not car.counted_passed and car.progress >= lane.stop_progress:
                    self.passed_counts[lane.side] += 1
                    car.counted_passed = True

                lead_progress = car.progress

                if car.progress <= lane.length + base.EXIT_MARGIN:
                    survivors.append(car)

        self.cars = survivors

    def _draw_static_scene(self) -> None:
        super()._draw_static_scene()
        self._draw_esp_layout()

    def _draw_esp_layout(self) -> None:
        for node_key, box, title, subtitle in self._node_boxes():
            self._draw_esp_board(box, title, subtitle)

    def _node_boxes(self):
        board_width = self.esp_board_image.width() if self.esp_board_image is not None else 210
        board_height = self.esp_board_image.height() if self.esp_board_image is not None else 130
        top = 126
        side_margin = 40
        return [
            ("A", (side_margin, top, side_margin + board_width, top + board_height), "ESP32 LoRa - Node A", "North/South"),
            (
                "B",
                (
                    base.CANVAS_WIDTH - side_margin - board_width,
                    top,
                    base.CANVAS_WIDTH - side_margin,
                    top + board_height,
                ),
                "ESP32 LoRa - Node B",
                "East/West",
            ),
        ]

    def _draw_esp_board(self, box, title: str, subtitle: str) -> None:
        x1, y1, x2, y2 = box
        center_x = (x1 + x2) / 2
        self.canvas.create_rectangle(x1 + 10, y1 + 10, x2 + 10, y2 + 10, fill="#a0917c", outline="", tags="static")
        if self.esp_board_image is not None:
            self.canvas.create_image(x1, y1, anchor="nw", image=self.esp_board_image, tags="static")
        else:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill="#1f6ba5", outline="#10344f", width=3, tags="static")
            self.canvas.create_rectangle(x1 + 12, y1 + 12, x2 - 12, y2 - 12, fill="#2f8cd2", outline="#85bee9", width=2, tags="static")

        node_name = title.split(" - ", 1)[-1]
        self.canvas.create_text(center_x, y2 + 18, text=f"{node_name} | {subtitle}", fill="#24303a", font=("Segoe UI", 11, "bold"), tags="static")

    def _redraw(self) -> None:
        super()._redraw()
        self._draw_esp_status()

    def _draw_esp_status(self) -> None:
        emergency_side = self._current_emergency_side()
        node_a_active = self.next_decision.green_side == Side.A
        node_b_active = self.next_decision.green_side == Side.B

        for node_key, box, _, _ in self._node_boxes():
            is_green_side = node_a_active if node_key == "A" else node_b_active
            emergency = emergency_side == (Side.A if node_key == "A" else Side.B)
            self._draw_board_status(box, node_key, is_green_side, emergency)

    def _draw_board_status(self, box, label: str, is_green_side: bool, emergency: bool) -> None:
        x1, y1, x2, y2 = box
        if emergency:
            pill_fill = "#b83b3b"
            pill_text = "AMBULANCE PRIORITY"
        else:
            pill_fill = "#36c66a" if is_green_side else "#6f7d86"
            pill_text = f"Node {label} ACTIVE" if is_green_side else f"Node {label} WAIT"
        pill_x1 = x1 + 24
        pill_y1 = y2 + 34
        pill_x2 = x2 - 24
        pill_y2 = y2 + 58
        self.canvas.create_rectangle(pill_x1, pill_y1, pill_x2, pill_y2, fill=pill_fill, outline="", tags="dynamic")
        self.canvas.create_text((pill_x1 + pill_x2) / 2, (pill_y1 + pill_y2) / 2, text=pill_text, fill="white", font=("Segoe UI", 9, "bold"), tags="dynamic")

    def _draw_cars(self) -> None:
        flash_on = (self.sim_time_ms // 180) % 2 == 0

        for car in self.cars:
            lane = base.LANES[car.direction]
            x, y = base.point_on_lane(lane, car.progress)
            is_ambulance = getattr(car, "is_ambulance", False)

            if not is_ambulance:
                if car.direction in ("north", "south"):
                    self.canvas.create_rectangle(
                        x - base.CAR_WIDTH / 2,
                        y - base.CAR_LENGTH / 2,
                        x + base.CAR_WIDTH / 2,
                        y + base.CAR_LENGTH / 2,
                        fill=car.color,
                        outline="#152027",
                        width=2,
                        tags="dynamic",
                    )
                else:
                    self.canvas.create_rectangle(
                        x - base.CAR_LENGTH / 2,
                        y - base.CAR_WIDTH / 2,
                        x + base.CAR_LENGTH / 2,
                        y + base.CAR_WIDTH / 2,
                        fill=car.color,
                        outline="#152027",
                        width=2,
                        tags="dynamic",
                    )
                continue

            if car.direction in ("north", "south"):
                self.canvas.create_rectangle(
                    x - base.CAR_WIDTH / 2 - 2,
                    y - base.CAR_LENGTH / 2 - 2,
                    x + base.CAR_WIDTH / 2 + 2,
                    y + base.CAR_LENGTH / 2 + 2,
                    fill="#fff9f6",
                    outline="#cc3a3a",
                    width=3,
                    tags="dynamic",
                )
                self.canvas.create_rectangle(x - 4, y - 10, x + 4, y + 10, fill="#cc3a3a", outline="", tags="dynamic")
                self.canvas.create_rectangle(x - 10, y - 4, x + 10, y + 4, fill="#cc3a3a", outline="", tags="dynamic")
                self.canvas.create_rectangle(x - 8, y - base.CAR_LENGTH / 2 - 8, x + 8, y - base.CAR_LENGTH / 2 - 2, fill="#4ea5ff" if flash_on else "#d0e8ff", outline="", tags="dynamic")
            else:
                self.canvas.create_rectangle(
                    x - base.CAR_LENGTH / 2 - 2,
                    y - base.CAR_WIDTH / 2 - 2,
                    x + base.CAR_LENGTH / 2 + 2,
                    y + base.CAR_WIDTH / 2 + 2,
                    fill="#fff9f6",
                    outline="#cc3a3a",
                    width=3,
                    tags="dynamic",
                )
                self.canvas.create_rectangle(x - 10, y - 4, x + 10, y + 4, fill="#cc3a3a", outline="", tags="dynamic")
                self.canvas.create_rectangle(x - 4, y - 10, x + 4, y + 10, fill="#cc3a3a", outline="", tags="dynamic")
                self.canvas.create_rectangle(x - base.CAR_LENGTH / 2 - 8, y - 8, x - base.CAR_LENGTH / 2 - 2, y + 8, fill="#4ea5ff" if flash_on else "#d0e8ff", outline="", tags="dynamic")

    def _update_panel_text(self) -> None:
        super()._update_panel_text()
        active = self._active_ambulances()
        target_side = self._current_emergency_side()

        if not active:
            self.emergency_var.set("Emergency status\n  Ambulance: none\n  Override: inactive")
            return

        labels = []
        for car in active:
            labels.append(car.direction[0].upper())

        target = "North/South" if target_side == Side.A else "East/West"
        state = "priority green" if self.next_decision.green_side == target_side and self.next_decision.phase == Phase.GREEN else "transitioning"
        self.emergency_var.set(
            "Emergency status\n"
            f"  Ambulance roads: {', '.join(labels)}\n"
            f"  Target axis: {target}\n"
            f"  Override: {state}"
        )

    def _load_esp_board_image(self, root: tk.Tk) -> tk.PhotoImage | None:
        image_path = Path(__file__).resolve().parent.parent / "docs" / "esp.png"
        if not image_path.exists():
            return None

        try:
            return tk.PhotoImage(master=root, file=str(image_path)).subsample(2, 2)
        except tk.TclError:
            return None


def main() -> None:
    root = tk.Tk()
    simulator = EmergencyVisualTrafficSimulator(root)
    window_width = min(base.WINDOW_WIDTH, max(base.MIN_VIEWPORT_WIDTH, root.winfo_screenwidth() - 80))
    window_height = min(base.WINDOW_HEIGHT, max(base.MIN_VIEWPORT_HEIGHT, root.winfo_screenheight() - 120))
    root.geometry(f"{int(window_width)}x{int(window_height)}")
    root.mainloop()


if __name__ == "__main__":
    main()
