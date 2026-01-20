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
SAVE_FILE = "highscore.json"  # Saved in app's own directory

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
        
        # High score tracking
        self.high_score_seconds = 0
        self.game_start_time = None
        self.time_alive_seconds = 0
        self.is_new_high_score = False
        self._load_high_score()


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
            # For each stat pair (low/high), calculate a "danger level" 0-1
            hunger_danger = max(
                max(0, 20 - self.hunger) / 20,  # 0-20 range
                max(0, self.hunger - 80) / 20   # 80-100 range
            )
            happiness_danger = max(
                max(0, 20 - self.happiness) / 20,  # 0-20 range
                max(0, self.happiness - 80) / 20   # 80-100 range
            )
            poo_danger = max(0, self.poo - 80) / 20  # 80-100 range
            
            # Use the highest danger level across all stats
            danger_level = max(hunger_danger, happiness_danger, poo_danger)
            
            if danger_level == 0:
                # No danger, turn off LEDs
                for i in range(1, 13):
                    tildagonos.leds[i] = (0, 0, 0)
            elif danger_level <= 0.5:  # 0-50% danger: dim orange-red
                # At 0% danger: dim (50, 20, 0), at 50% danger: brighter (200, 100, 0)
                red = int(50 + danger_level * 2 * 150)
                green = int(20 + danger_level * 2 * 80)
                for i in range(1, 13):
                    tildagonos.leds[i] = (red, green, 0)
            else:  # 50-100% danger: fade from orange-red to bright red
                # At 50% danger: orange-red (200, 100, 0)
                # At 100% danger: bright red (255, 0, 0)
                fade_progress = (danger_level - 0.5) * 2  # 0-1 from 50-100%
                red = int(200 + fade_progress * 55)
                green = int(100 * (1 - fade_progress))
                for i in range(1, 13):
                    tildagonos.leds[i] = (red, green, 0)
            
            tildagonos.leds.write()
            
            # Stop warning if no danger detected
            if danger_level == 0:
                self.led_warning_active = False
                # Re-enable default pattern
                eventbus.emit(PatternEnable())
        except:
            pass


    def _update_eye_animation(self):
        """Update eye animation state (looking direction and blinking)."""
        # Blink animation
        if self.blink_active:
            self.blink_counter += 1
            if self.blink_counter >= self.blink_duration:
                self.blink_active = False
                self.blink_counter = 0
        else:
            # Random chance to blink (1 in 40 frames)
            if random.randint(1, 40) == 1:
                self.blink_active = True
        
        # Eye looking direction animation
        self.eye_look_counter += 1
        if self.eye_look_counter >= self.eye_look_duration:
            self.eye_look_counter = 0
            # Randomly pick a new direction: -1 (left), 0 (center), or 1 (right)
            self.eye_look_direction = random.randint(-1, 1)


    def _load_high_score(self):
        """Load high score from persistent storage."""
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                self.high_score_seconds = data.get('high_score_seconds', 0)
        except (OSError, ValueError):
            # File doesn't exist or is invalid
            self.high_score_seconds = 0


    def _save_high_score(self, seconds):
        """Save high score to persistent storage."""
        try:
            data = {'high_score_seconds': seconds}
            with open(SAVE_FILE, 'w') as f:
                json.dump(data, f)
        except OSError:
            # Silently fail if we can't write (badge storage issue)
            pass


    def _seconds_to_readable(self, seconds):
        """Convert seconds to human-readable format (e.g., '1d 2h 30m 45s')."""
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
        if secs > 0 or not parts:  # Always show seconds if no other units
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
        
        # Handle high score tracking
        if game_over and self.game_start_time is not None:
            self.time_alive_seconds = time.time() - self.game_start_time
            if self.time_alive_seconds > self.high_score_seconds:
                self.is_new_high_score = True
                self._save_high_score(self.time_alive_seconds)
                self.high_score_seconds = self.time_alive_seconds
        
        return game_over


    def _start_game_over_leds(self):
        """Start red breathing LED pattern for game over."""
        try:
            # Stop any active warning LED pattern to prevent strobe effect
            if self.led_warning_active:
                self.led_warning_active = False
                self.led_warning_counter = 0
            # Disable the default pattern
            eventbus.emit(PatternDisable())
            self.led_brightness = 0
            self.led_direction = 1
        except:
            pass


    def _update_game_over_leds(self):
        """Update breathing red LEDs during game over."""
        try:
            # Breathe effect
            self.led_brightness += self.led_direction * 5
            if self.led_brightness >= 255:
                self.led_brightness = 255
                self.led_direction = -1
            elif self.led_brightness <= 0:
                self.led_brightness = 0
                self.led_direction = 1
            
            # Set all LEDs to red with breathing brightness
            for i in range(1, 13):
                tildagonos.leds[i] = (int(self.led_brightness), 0, 0)
            tildagonos.leds.write()
        except:
            pass


    def _stop_game_over_leds(self):
        """Stop the red breathing LED pattern."""
        try:
            # Explicitly turn off all LEDs first
            for i in range(1, 13):
                tildagonos.leds[i] = (0, 0, 0)
            tildagonos.leds.write()
            # Re-enable the default pattern
            eventbus.emit(PatternEnable())
        except:
            pass


    def _process_decay(self, hunger_decay, happiness_decay, poo_growth):
        """Helper to apply decay/growth and status checks."""
        # Apply decay/growth with clamping
        self.hunger = max(MIN_STAT, self.hunger - hunger_decay)
        self.happiness = max(MIN_STAT, self.happiness - happiness_decay)
        self.poo = min(MAX_STAT, self.poo + poo_growth) 

        # Check current status and apply negative feedback
        if self.hunger < 30:
            self.happiness = max(MIN_STAT, self.happiness - 5) 
        
        if self.poo > POO_THRESHOLD:
            self.happiness = max(MIN_STAT, self.happiness - 5) 
        
        # Final clamp all stats to ensure valid range
        self.hunger = max(MIN_STAT, min(MAX_STAT, self.hunger))
        self.happiness = max(MIN_STAT, min(MAX_STAT, self.happiness))
        self.poo = max(MIN_STAT, min(MAX_STAT, self.poo))
        
        # Check for game over conditions
        self._check_game_over()


    def background_update(self, delta):
        """
        Called every 0.05 seconds when app is minimized.
        """
        # If the app should be completely closed, stop background updates
        if self.app_should_close:
            return
        
        # Update LED warning flash if active
        if self.led_warning_active:
            self._update_led_warning()
        
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0
            # Slower decay for background mode
            self._process_decay(
                hunger_decay=1, 
                happiness_decay=1, 
                poo_growth=2
            )
            
            # Check if we should warn the user
            self._check_for_warnings()


    def update(self, delta):
        """
        Called every 0.05 seconds while app is in foreground.
        Handles user input and fast decay.
        """
        
        # Always check for CANCEL button to exit
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            # Stop LEDs if game over when exiting
            if self.game_over:
                self._stop_game_over_leds()
            # Stop warning LEDs if active
            if self.led_warning_active:
                self.led_warning_active = False
                eventbus.emit(PatternEnable())
            self.minimise()
            return
        
        # Handle intro screen
        if self.show_intro:
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.show_intro = False
                # Start the game timer
                self.game_start_time = time.time()
                self.is_new_high_score = False
            elif self.button_states.get(BUTTON_TYPES["CANCEL"]):
                self.button_states.clear()
                # Mark app for complete closure (no background updates)
                self.app_should_close = True
                self.minimise()
            return  # Don't process game logic during intro
        
        # If game over, allow restart with CONFIRM button
        if self.game_over:
            # Update breathing LED effect
            self._update_game_over_leds()
            
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                # Stop game over LEDs
                self._stop_game_over_leds()
                # Reset game state
                self.hunger = 70
                self.happiness = 70
                self.poo = 0
                self.game_over = False
                self.death_reason = ""
                self.status_message = "Hi There!"
                self.tick_counter = 0
                # Restart the game timer
                self.game_start_time = time.time()
                self.time_alive_seconds = 0
                self.is_new_high_score = False
            elif self.button_states.get(BUTTON_TYPES["CANCEL"]):
                self.button_states.clear()
                # Stop game over LEDs
                self._stop_game_over_leds()
                # Mark app for complete closure (no background updates)
                self.app_should_close = True
                self.minimise()
            return  # Don't process normal updates if game over
        
        # --- Time-based Decay Logic ---
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0

            # Fast decay for foreground mode
            self._process_decay(
                hunger_decay=2, 
                happiness_decay=2, 
                poo_growth=3
            )

            # Update status message (only if not game over)
            if not self.game_over:
                if self.hunger < 30:
                    self.status_message = "I'm hungry!"
                elif self.poo > POO_THRESHOLD:
                    self.status_message = "I'm gunna Poo!"
                elif self.happiness < 30:
                    self.status_message = "Urgh, I'm Bored!"
                else:
                    self.status_message = "This is Great!"

        # Update eye animation (only during normal gameplay)
        self._update_eye_animation()

        # --- User Actions (only if not game over) ---

        # UP button: Feed
        if self.button_states.get(BUTTON_TYPES["UP"]):
            self.button_states.clear()
            self.hunger = self.hunger + 15
            # Check for overfeed BEFORE clamping
            if self.hunger >= MAX_STAT:
                self.hunger = MAX_STAT
                self._check_game_over()
            self.poo = min(MAX_STAT, self.poo + 5)
            if not self.game_over:
                self.status_message = "Yum!"

        # RIGHT button: Play 
        elif self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            self.happiness = self.happiness + 15
            # Check for over-playing BEFORE clamping
            if self.happiness >= MAX_STAT:
                self.happiness = MAX_STAT
                self._check_game_over()
            self.hunger = max(MIN_STAT, self.hunger - 10)
            if not self.game_over:
                self.status_message = "Haha! Woo!"

        # CONFIRM button: Clean
        elif self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            
            # Only reward cleaning if poo is over half (50)
            if self.poo > POO_THRESHOLD:
                # Pet is happy to be cleaned when dirty
                self.happiness = min(MAX_STAT, self.happiness + 10)
                self.status_message = "Ahhh, clean."
            else:
                # Pet is annoyed by unnecessary cleaning
                self.happiness = max(MIN_STAT, self.happiness - 5)
                self.status_message = "Already clean!"
            
            # Always reset poo regardless
            self.poo = 0


    def _draw_animated_eyes(self, ctx, pet_color):
        """Draw animated eyes with looking direction and blinking."""
        ctx.rgb(0, 0, 0)
        eye_size = 10
        eye_x_offset = 15  # Distance from center
        eye_y = -85
        
        # If blinking, draw small horizontal line instead of square
        if self.blink_active:
            # Blink: draw horizontal line
            line_height = 2
            # Right eye
            ctx.rectangle(eye_x_offset - 5, eye_y - line_height/2, 10, line_height)
            ctx.fill()
            # Left eye
            ctx.rectangle(-eye_x_offset - 5, eye_y - line_height/2, 10, line_height)
            ctx.fill()
        else:
            # Normal eyes with looking direction
            # Eye offset based on looking direction (-1, 0, 1)
            look_offset = self.eye_look_direction * 3
            
            # Right eye
            ctx.rectangle(eye_x_offset - eye_size/2 + look_offset, eye_y - eye_size/2, eye_size, eye_size)
            ctx.fill()
            # Left eye
            ctx.rectangle(-eye_x_offset - eye_size/2 + look_offset, eye_y - eye_size/2, eye_size, eye_size)
            ctx.fill()


    def draw_stat_bar(self, ctx, y_pos, label, value, color_rgb):
        """Draw a single stat bar. SAFE version with extra validation."""
        bar_width = 130
        bar_height = 12
        
        # Safety: Ensure value is valid
        if value is None or value < MIN_STAT:
            value = MIN_STAT
        if value > MAX_STAT:
            value = MAX_STAT
        
        # Calculate fill width safely
        fill_ratio = float(value) / float(MAX_STAT)
        fill_width = int(fill_ratio * bar_width)
        
        X_OFFSET = 10 

        # Background bar (dark gray)
        ctx.rgb(0.2, 0.2, 0.2)
        ctx.rectangle(-bar_width/2 + X_OFFSET, y_pos, bar_width, bar_height)
        ctx.fill()
        
        # Foreground bar (colored)
        if fill_width > 0:
            ctx.rgb(*color_rgb)
            ctx.rectangle(-bar_width/2 + X_OFFSET, y_pos, fill_width, bar_height)
            ctx.fill()

        # Label text - positioned to the left of the bar
        ctx.rgb(1, 1, 1)
        ctx.font_size = 12
        ctx.move_to(-bar_width/2 + X_OFFSET - 50, y_pos + 9)
        ctx.text(label)


    def draw(self, ctx):
        """
        Called roughly every 0.05 seconds to update screen display.
        """
        # Clear screen
        clear_background(ctx)
        
        # --- INTRO SCREEN ---
        if self.show_intro:
            ctx.save()
            
            # Title - properly centered using text_width
            ctx.rgb(1, 0.5, 0.8)  # Pink
            ctx.font = "Arimo Bold"
            ctx.font_size = 28
            title = "Badgagotchi"
            title_width = ctx.text_width(title)
            ctx.move_to(-title_width / 2, -65)
            ctx.text(title)
            
            # Draw happy pet with ^ eyes
            ctx.rgb(1, 0.5, 0.8)  # Pink
            ctx.rectangle(-30, -50, 60, 60)
            ctx.fill()
            
            # Happy eyes (^ shape using small rectangles)
            ctx.rgb(0, 0, 0)
            # Left eye ^
            ctx.rectangle(-20, -28, 3, 8)
            ctx.fill()
            ctx.rectangle(-17, -31, 3, 8)
            ctx.fill()
            ctx.rectangle(-14, -28, 3, 8)
            ctx.fill()
            # Right eye ^
            ctx.rectangle(10, -28, 3, 8)
            ctx.fill()
            ctx.rectangle(13, -31, 3, 8)
            ctx.fill()
            ctx.rectangle(16, -28, 3, 8)
            ctx.fill()
            
            # Introduction text - properly centered
            ctx.rgb(1, 1, 1)
            ctx.font = "Arimo Regular"
            ctx.font_size = 14
            line1 = "This is Chip the"
            line1_width = ctx.text_width(line1)
            ctx.move_to(-line1_width / 2, 25)
            ctx.text(line1)
            
            line2 = "Badge Pet."
            line2_width = ctx.text_width(line2)
            ctx.move_to(-line2_width / 2, 43)
            ctx.text(line2)
            
            ctx.font_size = 16
            line3 = "Look after it!"
            line3_width = ctx.text_width(line3)
            ctx.move_to(-line3_width / 2, 65)
            ctx.text(line3)
            
            # High score display (above prompt)
            if self.high_score_seconds > 0:
                ctx.rgb(1, 1, 0)  # Yellow
                ctx.font_size = 12
                high_score_text = f"High Score: {self._seconds_to_readable(self.high_score_seconds)}"
                high_score_width = ctx.text_width(high_score_text)
                ctx.move_to(-high_score_width / 2, 85)
                ctx.text(high_score_text)
            
            # Continue prompt - properly centered
            ctx.rgb(0.7, 0.7, 0.7)
            ctx.font_size = 12
            prompt = "CONFIRM to Continue"
            prompt_width = ctx.text_width(prompt)
            ctx.move_to(-prompt_width / 2, 100)
            ctx.text(prompt)
            
            ctx.restore()
            return  # Don't draw game UI during intro
        
        # --- GAME OVER SCREEN ---
        if self.game_over:
            # Draw dead pet (gray/faded)
            ctx.rgb(0.3, 0.3, 0.3)
            ctx.rectangle(-30, -105, 60, 60)
            ctx.fill()
            
            # Draw X eyes using rectangles
            ctx.rgb(1, 0, 0)
            # Left eye X (simple cross shape)
            ctx.rectangle(-18, -88, 8, 2)
            ctx.fill()
            ctx.rectangle(-15, -91, 2, 8)
            ctx.fill()
            # Right eye X
            ctx.rectangle(12, -88, 8, 2)
            ctx.fill()
            ctx.rectangle(15, -91, 2, 8)
            ctx.fill()
            
            # Game Over text (properly centered using text_width)
            ctx.rgb(1, 0, 0)
            ctx.font_size = 24
            game_over_text = "GAME OVER"
            game_over_width = ctx.text_width(game_over_text)
            ctx.move_to(-game_over_width / 2, -20)
            ctx.text(game_over_text)
            
            # Death reason text (properly centered using text_width)
            ctx.rgb(1, 1, 1)
            ctx.font_size = 18
            reason_width = ctx.text_width(self.death_reason)
            ctx.move_to(-reason_width / 2, 10)
            ctx.text(self.death_reason)
            
            # Time alive display
            ctx.rgb(0.8, 0.8, 0.8)
            ctx.font_size = 14
            time_text = f"Chip lived: {self._seconds_to_readable(self.time_alive_seconds)}"
            time_width = ctx.text_width(time_text)
            ctx.move_to(-time_width / 2, 30)
            ctx.text(time_text)
            
            # High score display
            ctx.rgb(1, 1, 0)  # Yellow
            high_score_text = f"Best: {self._seconds_to_readable(self.high_score_seconds)}"
            high_score_width = ctx.text_width(high_score_text)
            ctx.move_to(-high_score_width / 2, 43)
            ctx.text(high_score_text)
            
            # Draw "HIGH SCORE!" diagonally if new record
            if self.is_new_high_score:
                ctx.save()
                ctx.rgb(1, 1, 0)  # Yellow
                ctx.font_size = 20
                ctx.font = "Arimo Bold"
                high_score_label = "HIGH SCORE!"
                ctx.rotate(0.3)  # Rotate ~17 degrees
                ctx.move_to(-70, -60)  # Positioned to cover dead chip
                ctx.text(high_score_label)
                ctx.restore()
            
            # Restart instruction (properly centered using text_width)
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
            
            return  # Exit early - don't draw normal game UI
        
        # --- NORMAL GAME SCREEN ---
        # Save graphics state
        ctx.save()

        # --- Draw Pet Body ---
        pet_color = (1, 0.5, 0.8)  # Default pink

        # Change color based on stats (priority order)
        if self.poo > 75:
            pet_color = (0.5, 0.3, 0.2)  # Brown (dirty)
        elif self.hunger < 15:
            pet_color = (0.0, 1.0, 0.0)  # Green (hungry)
        elif self.happiness < 30:
            pet_color = (0.0, 0.5, 1.0)  # Blue (sad)

        # Draw pet square
        ctx.rgb(*pet_color)
        ctx.rectangle(-30, -105, 60, 60)
        ctx.fill()

        # Draw animated eyes
        self._draw_animated_eyes(ctx, pet_color)

        ctx.restore()

        # --- Status Message (properly centered) ---
        ctx.rgb(1, 1, 1)
        ctx.font = "Arimo Regular"
        ctx.font_size = 18
        msg_width = ctx.text_width(self.status_message)
        ctx.move_to(-msg_width / 2, -15)
        ctx.text(self.status_message)

        # --- Stat Bars ---
        self.draw_stat_bar(ctx, 5, "Hunger:", self.hunger, (1.0, 0.7, 0.0))
        self.draw_stat_bar(ctx, 20, "Happy:", self.happiness, (0.0, 1.0, 0.0))
        self.draw_stat_bar(ctx, 35, "Poo:", self.poo, (0.6, 0.4, 0.2))

        # --- Controls Hint ---
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


# Standard export for Tildagon OS apps
__app_export__ = Badgagotchi
