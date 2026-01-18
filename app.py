import app
from app_components import clear_background 
from events.input import Buttons, BUTTON_TYPES
from tildagonos import tildagonos
from system.eventbus import eventbus
from system.patterndisplay.events import PatternDisable, PatternEnable
import math

# --- Badgagotchi Constants ---
MAX_STAT = 100
MIN_STAT = 0
TICK_RATE = 50  # 50 * 0.05s = 2.5 seconds between updates
POO_THRESHOLD = 50

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
        
        # Intro screen state
        self.show_intro = True
        
        # LED control
        self.led_brightness = 0
        self.led_direction = 1


    def _check_game_over(self):
        """Check if any stat has reached a critical failure state."""
        if self.hunger <= MIN_STAT:
            self.game_over = True
            self.death_reason = "Died of Hunger"
            self._start_game_over_leds()
            return True
        elif self.hunger >= MAX_STAT:
            self.game_over = True
            self.death_reason = "Oof That's too much food"
            self._start_game_over_leds()
            return True
        elif self.happiness <= MIN_STAT:
            self.game_over = True
            self.death_reason = "Got too sad"
            self._start_game_over_leds()
            return True
        elif self.happiness >= MAX_STAT:
            self.game_over = True
            self.death_reason = "Died of exhaustion"
            self._start_game_over_leds()
            return True
        elif self.poo >= MAX_STAT:
            self.game_over = True
            self.death_reason = "Covered in poo"
            self._start_game_over_leds()
            return True
        return False


    def _start_game_over_leds(self):
        """Start red breathing LED pattern for game over."""
        try:
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
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0
            # Slower decay for background mode
            self._process_decay(
                hunger_decay=1, 
                happiness_decay=1, 
                poo_growth=2
            )


    def update(self, delta):
        """
        Called every 0.05 seconds while app is in foreground.
        Handles user input and fast decay.
        """
        
        # Always check for CANCEL button to exit
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.minimise()
            return
        
        # Handle intro screen
        if self.show_intro:
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.show_intro = False
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

        # --- User Actions (only if not game over) ---

        # UP button: Feed
        if self.button_states.get(BUTTON_TYPES["UP"]):
            self.button_states.clear()
            self.hunger = self.hunger + 30
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
            self.happiness = self.happiness + 30
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
            # Title
            ctx.rgb(1, 0.5, 0.8)  # Pink
            ctx.font_size = 28
            ctx.move_to(-75, -80)
            ctx.text("Badgagotchi")
            
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
            
            # Introduction text - FIXED: moved RIGHT (positive direction)
            ctx.rgb(1, 1, 1)
            ctx.font_size = 14
            ctx.move_to(-50, 25)
            ctx.text("This is Chip the")
            ctx.move_to(-43, 43)
            ctx.text("Badge Pet.")
            
            ctx.font_size = 16
            ctx.move_to(-50, 65)
            ctx.text("Look after it!")
            
            # Continue prompt - FIXED: moved RIGHT
            ctx.rgb(0.7, 0.7, 0.7)
            ctx.font_size = 12
            ctx.move_to(-65, 95)
            ctx.text("CONFIRM to Continue")
            
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
            
            # Game Over text (centered)
            ctx.rgb(1, 0, 0)
            ctx.font_size = 24
            ctx.move_to(-60, -20)
            ctx.text("GAME OVER")
            
            # Death reason text (centered)
            ctx.rgb(1, 1, 1)
            ctx.font_size = 14
            # Calculate approximate center based on text length
            reason_offset = -len(self.death_reason) * 3.5
            ctx.move_to(reason_offset, 10)
            ctx.text(self.death_reason)
            
            # Restart instruction (centered)
            ctx.rgb(0.7, 0.7, 0.7)
            ctx.font_size = 12
            ctx.move_to(-65, 50)
            ctx.text("CONFIRM to restart")
            ctx.move_to(-50, 70)
            ctx.text("CANCEL to exit")
            
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

        # Draw eyes (black squares)
        ctx.rgb(0, 0, 0)
        eye_size = 10
        # Right eye
        ctx.rectangle(15 - eye_size/2, -85 - eye_size/2, eye_size, eye_size)
        ctx.fill()
        # Left eye
        ctx.rectangle(-15 - eye_size/2, -85 - eye_size/2, eye_size, eye_size)
        ctx.fill()

        ctx.restore()

        # --- Status Message (centered) ---
        ctx.rgb(1, 1, 1)
        ctx.font_size = 18
        # Calculate approximate center based on text length
        msg_offset = -len(self.status_message) * 4.5
        ctx.move_to(msg_offset, -15)
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
