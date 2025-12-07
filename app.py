import app
import random
from events.input import Buttons, BUTTON_TYPES

# --- Badgagotchi Constants ---
MAX_STAT = 100
MIN_STAT = 0
# Update logic every 50 * 0.05s = 2.5 seconds (Faster Decay)
TICK_RATE = 50 
POO_THRESHOLD = 50 # Threshold for the "Needs cleaning" warning

class Badgagotchi(app.App):
    """
    A prototype for a Tamagotchi-style app for the EMF Tildagon Badge.
    It tracks Hunger, Happiness, and Poo levels, simulating time-based decay.
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

        # REMOVED: print("Badgagotchi initialized.") for maximum stability on physical badge


    def _process_decay(self, hunger_decay, happiness_decay, poo_growth):
        """Helper to apply decay/growth and status checks."""
        # Use max(MIN_STAT, ...) to ensure the stat never goes below 0.
        self.hunger = max(MIN_STAT, self.hunger - hunger_decay)
        self.happiness = max(MIN_STAT, self.happiness - happiness_decay)
        self.poo = min(MAX_STAT, self.poo + poo_growth) 

        # 2. Check current status and apply negative feedback
        # NOTE: Status message update only happens in the foreground (update) 
        # but the logic for happiness decay due to status runs in both.
        if self.hunger < 30:
            # Hungry pet is unhappy, clamped to MIN_STAT
            self.happiness = max(MIN_STAT, self.happiness - 5) 
        
        if self.poo > POO_THRESHOLD:
            # Dirty pet is unhappy, clamped to MIN_STAT
            self.happiness = max(MIN_STAT, self.happiness - 5) 
        
        # Clamp all stats to ensure they stay between MIN_STAT and MAX_STAT
        self.hunger = max(MIN_STAT, min(MAX_STAT, self.hunger))
        self.happiness = max(MIN_STAT, min(MAX_STAT, self.happiness))
        self.poo = max(MIN_STAT, min(MAX_STAT, self.poo))


    # --- Logic Updates (Background/Foreground) ---

    def background_update(self):
        """
        Called every 0.05 seconds when the app is minimized (background).
        Uses a slower decay rate.
        """
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0
            # Slower Decay Rates for background mode
            self._process_decay(
                hunger_decay=4, 
                happiness_decay=2, 
                poo_growth=6
            )


    def update(self, delta):
        """
        Called every 0.05 seconds while the app is in the foreground.
        Handles user input (button presses) and fast decay.
        """
        
        # --- Time-based Decay Logic (Foreground - Fast Decay) ---
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0

            # Fast Decay Rates for foreground mode
            self._process_decay(
                hunger_decay=8, 
                happiness_decay=5, 
                poo_growth=12
            )

            # Update status message for the user in the foreground
            if self.hunger < 30:
                self.status_message = "I'm hungry!"
            elif self.poo > POO_THRESHOLD:
                self.status_message = "I'm gunna Poo!"
            elif self.happiness < 30:
                self.status_message = "Urgh, I'm Bored!"
            else:
                self.status_message = "This is Great!"
        # --- End Decay Logic ---

        # Always check for the CANCEL button to exit the app
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.minimise()
            return

        # --- User Actions ---

        # UP button: Feed
        if self.button_states.get(BUTTON_TYPES["UP"]):
            self.button_states.clear() # Process once per press
            self.hunger = min(MAX_STAT, self.hunger + 30)
            self.poo = min(MAX_STAT, self.poo + 5) # Feeding increases poo slightly
            self.status_message = "Yum!"

        # RIGHT button: Play 
        elif self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            self.happiness = min(MAX_STAT, self.happiness + 30)
            # Fix in V0.0.1: Ensure hunger decrease does not go below MIN_STAT (0)
            self.hunger = max(MIN_STAT, self.hunger - 10) 
            self.status_message = "Haha! Woo!"

        # CONFIRM button: Clean
        elif self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            self.poo = 0 # Clean the environment
            self.happiness = min(MAX_STAT, self.happiness + 15) # Pet is happier in a clean space
            self.status_message = "Ahhh, clean and fresh."


    # --- Drawing/Visuals ---

    def draw_stat_bar(self, ctx, y_pos, label, value, color_rgb):
        """Helper function to draw a single stat bar on the ctx canvas."""
        bar_width = 130 # Total width
        bar_height = 12 # Total height
        
        # V0.0.7 FIX: Explicitly cast fill_width to int to avoid floating-point/NaN errors
        fill_width = int((float(value) / MAX_STAT) * bar_width)
        
        # Horizontal shift offset
        X_OFFSET = 10 

        # Background bar (Gray/Dark) - Shifted right
        ctx.rgb(0.2, 0.2, 0.2).rectangle(-bar_width/2 + X_OFFSET, y_pos, bar_width, bar_height).fill()
        
        # Foreground bar (Colored based on stat type) - Shifted right
        ctx.rgb(*color_rgb).rectangle(-bar_width/2 + X_OFFSET, y_pos, fill_width, bar_height).fill()

        # Text label - Shifted right
        ctx.font_size = 12
        ctx.rgb(1, 1, 1)
        # Horizontal position adjusted: -bar_width/2 - 5 + 10 (shifted right)
        # Center text vertically: y_pos + (12 / 2) + 3 = y_pos + 9
        ctx.move_to(-bar_width/2 + 5, y_pos + 9) 
        ctx.text_align = "right" 
        ctx.text(label)


    def draw(self, ctx):
        """
        Called roughly every 0.05 seconds to update the screen display.
        """
        # --- FIX: Ensure full screen clear ---
        ctx.rgb(0, 0, 0).rectangle(-150, -150, 300, 300).fill()
        
        # --- Pet Critical Status Check ---
        is_critical = (self.poo == MAX_STAT or 
                       self.happiness == MIN_STAT or 
                       self.hunger == MIN_STAT)

        # --- 1. Draw Pet Visual (Simple Square) ---
        pet_color = (1, 0.5, 0.8) # Default Pink/Purple

        # Priority 1: High Poo (Brown)
        if self.poo > 75:
            pet_color = (0.5, 0.3, 0.2) 
        
        # Priority 2: Very Hungry (Green)
        if self.hunger < 15:
            pet_color = (0.0, 1.0, 0.0)
        
        # Priority 3: Low Happiness (Blue), only if not currently overriding for poo/hunger
        if self.happiness < 30 and self.hunger >= 15 and self.poo <= 75:
             pet_color = (0.0, 0.5, 1.0) # Blue (Sad)

        # V0.0.8 FIX: Use explicit begin/close path for filled rectangle drawing
        # to ensure robust drawing on low-level graphics context, replacing .rectangle().fill()
        ctx.rgb(*pet_color)
        ctx.begin_path()
        # Drawing the 60x60 square centered horizontally at 0, with top edge at -105
        # Coordinates: (-30, -105) to (30, -45)
        ctx.move_to(-30, -105)
        ctx.line_to(30, -105)
        ctx.line_to(30, -45)
        ctx.line_to(-30, -45)
        ctx.close_path()
        ctx.fill()
        # --- End V0.0.8 Fix ---

        # --- Draw Eyes ---
        eye_size = 10
        ctx.rgb(0, 0, 0)
        
        if is_critical:
            # Draw X eyes for critical state
            line_width = 2
            # Set line width
            ctx.line_width = line_width
            
            # Right X (centered near 15, -85)
            ctx.move_to(15 - eye_size/2, -85 - eye_size/2).line_to(15 + eye_size/2, -85 + eye_size/2).stroke()
            ctx.move_to(15 - eye_size/2, -85 + eye_size/2).line_to(15 + eye_size/2, -85 - eye_size/2).stroke()
            
            # Left X (centered near -15, -85)
            ctx.move_to(-15 - eye_size/2, -85 - eye_size/2).line_to(-15 + eye_size/2, -85 + eye_size/2).stroke()
            ctx.move_to(-15 - eye_size/2, -85 + eye_size/2).line_to(-15 + eye_size/2, -85 - eye_size/2).stroke()
        else:
            # Draw square eyes (normal)
            # Right Eye (centered near 15, -85)
            ctx.rectangle(15 - eye_size/2, -85 - eye_size/2, eye_size, eye_size).fill()
            # Left Eye (centered near -15, -85)
            ctx.rectangle(-15 - eye_size/2, -85 - eye_size/2, eye_size, eye_size).fill()

        # FIX (V0.0.5): Explicitly reset line_width to prevent crash during subsequent text/fill calls
        ctx.line_width = 1 

        # --- 2. Display Status Message ---
        ctx.font_size = 18
        ctx.rgb(1, 1, 1)
        ctx.move_to(0, -15) # Shifted up from Y=0 to Y=-15
        ctx.text_align = "center" 
        ctx.text(self.status_message)


        # --- 3. Draw Stat Bars ---
        self.draw_stat_bar(ctx, 5, "Hunger:", self.hunger, (1.0, 0.7, 0.0)) # Y=5 
        self.draw_stat_bar(ctx, 20, "Happy:", self.happiness, (0.0, 1.0, 0.0)) # Y=20 
        self.draw_stat_bar(ctx, 35, "Poo:", self.poo, (0.6, 0.4, 0.2)) # Y=35 

        # --- 4. Draw Controls Hint ---
        ctx.font_size = 10 
        ctx.rgb(0.7, 0.7, 0.7)
        ctx.text_align = "center"
        
        # Line 1 (UP action) 
        ctx.move_to(0, 65) 
        ctx.text("UP=Feed")

        # Line 2 (RIGHT action) 
        ctx.move_to(0, 77) 
        ctx.text("RIGHT=Play")
        
        # Line 3 (CONFIRM action) 
        ctx.move_to(0, 89) 
        ctx.text("CONFIRM=Clean")
        
        # Line 4 (CANCEL action) 
        ctx.move_to(0, 101) 
        ctx.text("CANCEL=Exit")


# This is the standard export line for Tildagon OS apps
__app_export__ = Badgagotchi
