import app
from app_components import clear_background 
from events.input import Buttons, BUTTON_TYPES
from tildagonos import tildagonos
from system.eventbus import eventbus
from system.patterndisplay.events import PatternDisable, PatternEnable
import math
import random
import json
import time
import os

# --- Badgagotchi Constants ---
MAX_STAT = 100
MIN_STAT = 0
TICK_RATE = 50  # 50 * 0.05s = 2.5 seconds between updates
POO_THRESHOLD = 50
SAVE_FILE = "badgagotchi_save.json"  # Saved in app's own directory

# Chip color options (RGB tuples)
CHIP_COLORS = [
    (1.0, 0.5, 0.8),   # Pink (default)
    (1.0, 0.6, 0.2),   # Orange
    (1.0, 1.0, 0.3),   # Yellow
    (1.0, 0.2, 0.2),   # Red
    (0.7, 0.3, 0.9),   # Purple
]
CHIP_COLOR_NAMES = ["Pink", "Orange", "Yellow", "Red", "Purple"]

class Badgagotchi(app.App):
    """
    A Tamagotchi-style app for the EMF Tildagon Badge.
    Tracks Hunger, Happiness, and Poo levels with time-based decay.
    """

    def __init__(self):
        super().__init__()
        
        # Initialize core stats (0-100 range)
        self.hunger = 70
        self.happiness = 70
        self.poo = 0 

        # Game state and button handler
        self.tick_counter = 0
        self.button_states = Buttons(self)
        self.status_message = "Hi There!"
        
        # Game over state
        self.game_over = False
        self.death_reason = ""
        self.app_should_close = False  # Flag to completely stop the app
        
        # Intro screen state
        self.show_intro = True
        
        # LED control
        self.led_brightness = 0
        self.led_direction = 1
        self.led_warning_active = False
        
        # Eye animation state
        self.eye_look_direction = 0  # -1 (left), 0 (center), 1 (right)
        self.eye_look_counter = 0
        self.eye_look_duration = 20  # Frames to hold each direction
        self.blink_active = False
        self.blink_counter = 0
        self.blink_duration = 5  # Frames to hold blink
        
        # High score tracking and color preference
        self.high_score_seconds = 0
        self.game_start_time = None
        self.time_alive_seconds = 0
        self.is_new_high_score = False
        self.chip_color_index = 0
        self._load_save_data()


    def _load_save_data(self):
        """Load high score and color preference from persistent storage."""
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                self.high_score_seconds = data.get('high_score_seconds', 0)
                self.chip_color_index = data.get('chip_color_index', 0)
                # Validate color index
                if not (0 <= self.chip_color_index < len(CHIP_COLORS)):
                    self.chip_color_index = 0
        except (OSError, ValueError):
            # File doesn't exist or is invalid
            self.high_score_seconds = 0
            self.chip_color_index = 0


    def _save_save_data(self):
        """Save high score and color preference to persistent storage."""
        try:
            data = {
                'high_score_seconds': self.high_score_seconds,
                'chip_color_index': self.chip_color_index
            }
            with open(SAVE_FILE, 'w') as f:
                json.dump(data, f)
        except OSError:
            # Silently fail if we can't write (badge storage issue)
            pass


    def _check_for_warnings(self):
        """Check if stats are critically low and trigger LED warning."""
        # Only warn if not already warning and not in game over
        if self.led_warning_active or self.game_over:
            return
            
        # Check if any stat is within 20 points of game over
        critical = (self.hunger <= 20 or self.hunger >= 80 or 
                   self.happiness <= 20 or self.happiness >= 80 or 
                   self.poo >= 80)
        
        if critical:
            self._trigger_led_warning()


    def _trigger_led_warning(self):
        """Start continuous fade LED warning based on stat values."""
        try:
            self.led_warning_active = True
            # Disable default pattern
            eventbus.emit(PatternDisable())
        except:
            pass


    def _update_led_warning(self):
        """Update LED fade effect based on stat values."""
        if not self.led_warning_active:
            return
            
        try:
            # Calculate LED effect based on how close stats are to critical
            hunger_danger = max(
                max(0, 20 - self.hunger) / 20,
                max(0, self.hunger - 80) / 20
            )
            happiness_danger = max(
                max(0, 20 - self.happiness) / 20,
                max(0, self.happiness - 80) / 20
            )
            poo_danger = max(0, self.poo - 80) / 20
            
            danger_level = max(hunger_danger, happiness_danger, poo_danger)
            
            if danger_level == 0:
                for i in range(1, 13):
                    tildagonos.leds[i] = (0, 0, 0)
            elif danger_level <= 0.5:
                red = int(50 + danger_level * 2 * 150)
                green = int(20 + danger_level * 2 * 80)
                for i in range(1, 13):
                    tildagonos.leds[i] = (red, green, 0)
            else:
                fade_progress = (danger_level - 0.5) * 2
                red = int(200 + fade_progress * 55)
                green = int(100 * (1 - fade_progress))
                for i in range(1, 13):
                    tildagonos.leds[i] = (red, green, 0)
            
            tildagonos.leds.write()
            
            if danger_level == 0:
                self.led_warning_active = False
                eventbus.emit(PatternEnable())
        except:
            pass


    def _update_eye_animation(self):
        """Update eye animation state (looking direction and blinking)."""
        if self.blink_active:
            self.blink_counter += 1
            if self.blink_counter >= self.blink_duration:
                self.blink_active = False
                self.blink_counter = 0
        else:
            if random.randint(1, 40) == 1:
                self.blink_active = True
        
        self.eye_look_counter += 1
        if self.eye_look_counter >= self.eye_look_duration:
            self.eye_look_counter = 0
            self.eye_look_direction = random.randint(-1, 1)


    def _seconds_to_readable(self, seconds):
        """Convert seconds to human-readable format."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)


    def _check_game_over(self):
        """Check if any stat has reached a critical failure state."""
        game_over = False
        if self.hunger <= MIN_STAT:
            self.game_over = True
            self.death_reason = "Died of Hunger"
            self._start_game_over_leds()
            game_over = True
        elif self.hunger >= MAX_STAT:
            self.game_over = True
            self.death_reason = "Oof That's too much food"
            self._start_game_over_leds()
            game_over = True
        elif self.happiness <= MIN_STAT:
            self.game_over = True
            self.death_reason = "Got too sad"
            self._start_game_over_leds()
            game_over = True
        elif self.happiness >= MAX_STAT:
            self.game_over = True
            self.death_reason = "Died of exhaustion"
            self._start_game_over_leds()
            game_over = True
        elif self.poo >= MAX_STAT:
            self.game_over = True
            self.death_reason = "Covered in poo"
            self._start_game_over_leds()
            game_over = True
        
        if game_over and self.game_start_time is not None:
            self.time_alive_seconds = time.time() - self.game_start_time
            if self.time_alive_seconds > self.high_score_seconds:
                self.is_new_high_score = True
                self.high_score_seconds = self.time_alive_seconds
                self._save_save_data()
        
        return game_over


    def _start_game_over_leds(self):
        """Start red breathing LED pattern for game over."""
        try:
            if self.led_warning_active:
                self.led_warning_active = False
            eventbus.emit(PatternDisable())
            self.led_brightness = 0
            self.led_direction = 1
        except:
            pass


    def _update_game_over_leds(self):
        """Update breathing red LEDs during game over."""
        try:
            self.led_brightness += self.led_direction * 5
            if self.led_brightness >= 255:
                self.led_brightness = 255
                self.led_direction = -1
            elif self.led_brightness <= 0:
                self.led_brightness = 0
                self.led_direction = 1
            
            for i in range(1, 13):
                tildagonos.leds[i] = (int(self.led_brightness), 0, 0)
            tildagonos.leds.write()
        except:
            pass


    def _stop_game_over_leds(self):
        """Stop the red breathing LED pattern."""
        try:
            for i in range(1, 13):
                tildagonos.leds[i] = (0, 0, 0)
            tildagonos.leds.write()
            eventbus.emit(PatternEnable())
        except:
            pass


    def _process_decay(self, hunger_decay, happiness_decay, poo_growth):
        """Helper to apply decay/growth and status checks."""
        self.hunger = max(MIN_STAT, self.hunger - hunger_decay)
        self.happiness = max(MIN_STAT, self.happiness - happiness_decay)
        self.poo = min(MAX_STAT, self.poo + poo_growth) 

        if self.hunger < 30:
            self.happiness = max(MIN_STAT, self.happiness - 5) 
        
        if self.poo > POO_THRESHOLD:
            self.happiness = max(MIN_STAT, self.happiness - 5) 
        
        self.hunger = max(MIN_STAT, min(MAX_STAT, self.hunger))
        self.happiness = max(MIN_STAT, min(MAX_STAT, self.happiness))
        self.poo = max(MIN_STAT, min(MAX_STAT, self.poo))
        
        self._check_game_over()


    def background_update(self, delta):
        """Called every 0.05 seconds when app is minimized."""
        if self.app_should_close:
            return
        
        # Don't run any background updates if on intro or game over screen
        if self.show_intro or self.game_over:
            return
        
        if self.led_warning_active:
            self._update_led_warning()
        
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0
            self._process_decay(
                hunger_decay=1, 
                happiness_decay=1, 
                poo_growth=2
            )
            
            self._check_for_warnings()


    def update(self, delta):
        """Called every 0.05 seconds while app is in foreground."""
        
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            if self.game_over:
                self._stop_game_over_leds()
            if self.led_warning_active:
                self.led_warning_active = False
                eventbus.emit(PatternEnable())
            self.minimise()
            return
        
        # Handle intro screen
        if self.show_intro:
            # LEFT/RIGHT buttons to change color
            if self.button_states.get(BUTTON_TYPES["LEFT"]):
                self.button_states.clear()
                self.chip_color_index = (self.chip_color_index - 1) % len(CHIP_COLORS)
                self._save_save_data()
            
            if self.button_states.get(BUTTON_TYPES["RIGHT"]):
                self.button_states.clear()
                self.chip_color_index = (self.chip_color_index + 1) % len(CHIP_COLORS)
                self._save_save_data()
            
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.show_intro = False
                self.game_start_time = time.time()
                self.is_new_high_score = False
            elif self.button_states.get(BUTTON_TYPES["CANCEL"]):
                self.button_states.clear()
                self.app_should_close = True
                self.minimise()
            return
        
        if self.game_over:
            self._update_game_over_leds()
            
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self._stop_game_over_leds()
                self.hunger = 70
                self.happiness = 70
                self.poo = 0
                self.game_over = False
                self.death_reason = ""
                self.status_message = "Hi There!"
                self.tick_counter = 0
                self.game_start_time = time.time()
                self.time_alive_seconds = 0
                self.is_new_high_score = False
            elif self.button_states.get(BUTTON_TYPES["CANCEL"]):
                self.button_states.clear()
                self._stop_game_over_leds()
                self.app_should_close = True
                self.minimise()
            return
        
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0

            self._process_decay(
                hunger_decay=2, 
                happiness_decay=2, 
                poo_growth=3
            )

            if not self.game_over:
                if self.hunger < 30:
                    self.status_message = "I'm hungry!"
                elif self.poo > POO_THRESHOLD:
                    self.status_message = "I'm gunna Poo!"
                elif self.happiness < 30:
                    self.status_message = "Urgh, I'm Bored!"
                else:
                    self.status_message = "This is Great!"

        self._update_eye_animation()

        if self.button_states.get(BUTTON_TYPES["UP"]):
            self.button_states.clear()
            self.hunger = self.hunger + 15
            if self.hunger >= MAX_STAT:
                self.hunger = MAX_STAT
                self._check_game_over()
            self.poo = min(MAX_STAT, self.poo + 5)
            if not self.game_over:
                self.status_message = "Yum!"

        elif self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            self.happiness = self.happiness + 15
            if self.happiness >= MAX_STAT:
                self.happiness = MAX_STAT
                self._check_game_over()
            self.hunger = max(MIN_STAT, self.hunger - 10)
            if not self.game_over:
                self.status_message = "Haha! Woo!"

        elif self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            
            if self.poo > POO_THRESHOLD:
                self.happiness = min(MAX_STAT, self.happiness + 10)
                self.status_message = "Ahhh, clean."
            else:
                self.happiness = max(MIN_STAT, self.happiness - 5)
                self.status_message = "Already clean!"
            
            self.poo = 0


    def _draw_animated_eyes(self, ctx, pet_color):
        """Draw animated eyes with looking direction and blinking."""
        ctx.rgb(0, 0, 0)
        eye_size = 10
        eye_x_offset = 15
        eye_y = -85
        
        if self.blink_active:
            line_height = 2
            ctx.rectangle(eye_x_offset - 5, eye_y - line_height/2, 10, line_height)
            ctx.fill()
            ctx.rectangle(-eye_x_offset - 5, eye_y - line_height/2, 10, line_height)
            ctx.fill()
        else:
            look_offset = self.eye_look_direction * 3
            
            ctx.rectangle(eye_x_offset - eye_size/2 + look_offset, eye_y - eye_size/2, eye_size, eye_size)
            ctx.fill()
            ctx.rectangle(-eye_x_offset - eye_size/2 + look_offset, eye_y - eye_size/2, eye_size, eye_size)
            ctx.fill()


    def draw_stat_bar(self, ctx, y_pos, label, value, color_rgb):
        """Draw a single stat bar."""
        bar_width = 130
        bar_height = 12
        
        if value is None or value < MIN_STAT:
            value = MIN_STAT
        if value > MAX_STAT:
            value = MAX_STAT
        
        fill_ratio = float(value) / float(MAX_STAT)
        fill_width = int(fill_ratio * bar_width)
        
        X_OFFSET = 10 

        ctx.rgb(0.2, 0.2, 0.2)
        ctx.rectangle(-bar_width/2 + X_OFFSET, y_pos, bar_width, bar_height)
        ctx.fill()
        
        if fill_width > 0:
            ctx.rgb(*color_rgb)
            ctx.rectangle(-bar_width/2 + X_OFFSET, y_pos, fill_width, bar_height)
            ctx.fill()

        ctx.rgb(1, 1, 1)
        ctx.font_size = 12
        ctx.move_to(-bar_width/2 + X_OFFSET - 50, y_pos + 9)
        ctx.text(label)


    def draw(self, ctx):
        """Called roughly every 0.05 seconds to update screen display."""
        clear_background(ctx)
        
        # --- INTRO SCREEN ---
        if self.show_intro:
            ctx.save()
            
            ctx.rgb(1, 0.5, 0.8)
            ctx.font = "Arimo Bold"
            ctx.font_size = 28
            title = "Badgagotchi"
            title_width = ctx.text_width(title)
            ctx.move_to(-title_width / 2, -73)
            ctx.text(title)
            
            # Draw pet in selected color - moved up closer to title
            ctx.rgb(*CHIP_COLORS[self.chip_color_index])
            ctx.rectangle(-30, -65, 60, 60)
            ctx.fill()
            
            # Happy eyes (^ shape)
            ctx.rgb(0, 0, 0)
            ctx.rectangle(-20, -43, 3, 8)
            ctx.fill()
            ctx.rectangle(-17, -46, 3, 8)
            ctx.fill()
            ctx.rectangle(-14, -43, 3, 8)
            ctx.fill()
            ctx.rectangle(10, -43, 3, 8)
            ctx.fill()
            ctx.rectangle(13, -46, 3, 8)
            ctx.fill()
            ctx.rectangle(16, -43, 3, 8)
            ctx.fill()
            
            # Text moved up (same amount as pet minus 5px for spacing)
            ctx.rgb(1, 1, 1)
            ctx.font = "Arimo Regular"
            ctx.font_size = 14
            line1 = "This is Chip the"
            line1_width = ctx.text_width(line1)
            ctx.move_to(-line1_width / 2, 10)
            ctx.text(line1)
            
            line2 = "Badge Pet."
            line2_width = ctx.text_width(line2)
            ctx.move_to(-line2_width / 2, 25)
            ctx.text(line2)
            
            ctx.font_size = 14
            line3 = "Look after it!"
            line3_width = ctx.text_width(line3)
            ctx.move_to(-line3_width / 2, 40)
            ctx.text(line3)
            
            # Color selection
            ctx.rgb(*CHIP_COLORS[self.chip_color_index])
            ctx.font_size = 14
            color_text = f"Colour: {CHIP_COLOR_NAMES[self.chip_color_index]}"
            color_width = ctx.text_width(color_text)
            ctx.move_to(-color_width / 2, 56)
            ctx.text(color_text)
            
            # High score
            if self.high_score_seconds > 0:
                ctx.rgb(1, 1, 0)
                ctx.font_size = 18
                high_score_text = f"Best Time: {self._seconds_to_readable(self.high_score_seconds)}"
                high_score_width = ctx.text_width(high_score_text)
                ctx.move_to(-high_score_width / 2, 75)
                ctx.text(high_score_text)
            
            ctx.rgb(0.7, 0.7, 0.7)
            ctx.font_size = 10
            prompt1 = "LEFT/RIGHT to change color"
            prompt1_width = ctx.text_width(prompt1)
            ctx.move_to(-prompt1_width / 2, 93)
            ctx.text(prompt1)
            
            prompt2 = "CONFIRM to Continue"
            prompt2_width = ctx.text_width(prompt2)
            ctx.move_to(-prompt2_width / 2, 105)
            ctx.text(prompt2)
            
            ctx.restore()
            return
        
        # --- GAME OVER SCREEN ---
        if self.game_over:
            ctx.rgb(0.3, 0.3, 0.3)
            ctx.rectangle(-30, -105, 60, 60)
            ctx.fill()
            
            ctx.rgb(1, 0, 0)
            ctx.rectangle(-18, -88, 8, 2)
            ctx.fill()
            ctx.rectangle(-15, -91, 2, 8)
            ctx.fill()
            ctx.rectangle(12, -88, 8, 2)
            ctx.fill()
            ctx.rectangle(15, -91, 2, 8)
            ctx.fill()
            
            ctx.rgb(1, 0, 0)
            ctx.font_size = 24
            game_over_text = "GAME OVER"
            game_over_width = ctx.text_width(game_over_text)
            ctx.move_to(-game_over_width / 2, -20)
            ctx.text(game_over_text)
            
            ctx.rgb(1, 1, 1)
            ctx.font_size = 18
            reason_width = ctx.text_width(self.death_reason)
            ctx.move_to(-reason_width / 2, 10)
            ctx.text(self.death_reason)
            
            ctx.rgb(0.8, 0.8, 0.8)
            ctx.font_size = 14
            time_text = f"Chip lived: {self._seconds_to_readable(self.time_alive_seconds)}"
            time_width = ctx.text_width(time_text)
            ctx.move_to(-time_width / 2, 30)
            ctx.text(time_text)
            
            ctx.rgb(1, 1, 0)
            high_score_text = f"Best: {self._seconds_to_readable(self.high_score_seconds)}"
            high_score_width = ctx.text_width(high_score_text)
            ctx.move_to(-high_score_width / 2, 43)
            ctx.text(high_score_text)
            
            if self.is_new_high_score:
                ctx.save()
                ctx.rgb(1, 1, 0)
                ctx.font_size = 20
                ctx.font = "Arimo Bold"
                ctx.rotate(0.3)
                ctx.move_to(-70, -60)
                ctx.text("HIGH SCORE!")
                ctx.restore()
            
            ctx.rgb(0.7, 0.7, 0.7)
            ctx.font_size = 12
            restart_text = "CONFIRM to restart"
            restart_width = ctx.text_width(restart_text)
            ctx.move_to(-restart_width / 2, 65)
            ctx.text(restart_text)
            
            exit_text = "CANCEL to exit"
            exit_width = ctx.text_width(exit_text)
            ctx.move_to(-exit_width / 2, 85)
            ctx.text(exit_text)
            
            return
        
        # --- NORMAL GAME SCREEN ---
        ctx.save()

        # Use selected color as base
        pet_color = CHIP_COLORS[self.chip_color_index]

        # Override with status colors
        if self.poo > 75:
            pet_color = (0.5, 0.3, 0.2)
        elif self.hunger < 15:
            pet_color = (0.0, 1.0, 0.0)
        elif self.happiness < 30:
            pet_color = (0.0, 0.5, 1.0)

        ctx.rgb(*pet_color)
        ctx.rectangle(-30, -105, 60, 60)
        ctx.fill()

        self._draw_animated_eyes(ctx, pet_color)

        ctx.restore()

        ctx.rgb(1, 1, 1)
        ctx.font = "Arimo Regular"
        ctx.font_size = 18
        msg_width = ctx.text_width(self.status_message)
        ctx.move_to(-msg_width / 2, -15)
        ctx.text(self.status_message)

        self.draw_stat_bar(ctx, 5, "Hunger:", self.hunger, (1.0, 0.7, 0.0))
        self.draw_stat_bar(ctx, 20, "Happy:", self.happiness, (0.0, 1.0, 0.0))
        self.draw_stat_bar(ctx, 35, "Poo:", self.poo, (0.6, 0.4, 0.2))

        ctx.rgb(0.7, 0.7, 0.7)
        ctx.font_size = 10
        
        ctx.move_to(-30, 65)
        ctx.text("UP=Feed")
        ctx.move_to(-30, 77)
        ctx.text("RIGHT=Play")
        ctx.move_to(-30, 89)
        ctx.text("CONFIRM=Clean")
        ctx.move_to(-30, 101)
        ctx.text("CANCEL=Exit")


__app_export__ = Badgagotchi
