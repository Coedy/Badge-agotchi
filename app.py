import app
from app_components import clear_background 
from events.input import Buttons, BUTTON_TYPES

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


    def background_update(self, delta):
        """
        CRITICAL FIX: Added delta parameter as REQUIRED by badge OS.
        Called every 0.05 seconds when app is minimized.
        """
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0
            # Slower decay for background mode
            self._process_decay(
                hunger_decay=4, 
                happiness_decay=2, 
                poo_growth=6
            )


    def update(self, delta):
        """
        Called every 0.05 seconds while app is in foreground.
        Handles user input and fast decay.
        """
        
        # --- Time-based Decay Logic ---
        self.tick_counter += 1

        if self.tick_counter >= TICK_RATE:
            self.tick_counter = 0

            # Fast decay for foreground mode
            self._process_decay(
                hunger_decay=8, 
                happiness_decay=5, 
                poo_growth=12
            )

            # Update status message
            if self.hunger < 30:
                self.status_message = "I'm hungry!"
            elif self.poo > POO_THRESHOLD:
                self.status_message = "I'm gunna Poo!"
            elif self.happiness < 30:
                self.status_message = "Urgh, I'm Bored!"
            else:
                self.status_message = "This is Great!"

        # Always check for CANCEL button to exit
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.minimise()
            return

        # --- User Actions ---

        # UP button: Feed
        if self.button_states.get(BUTTON_TYPES["UP"]):
            self.button_states.clear()
            self.hunger = min(MAX_STAT, self.hunger + 30)
            self.poo = min(MAX_STAT, self.poo + 5)
            self.status_message = "Yum!"

        # RIGHT button: Play 
        elif self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            self.happiness = min(MAX_STAT, self.happiness + 30)
            self.hunger = max(MIN_STAT, self.hunger - 10) 
            self.status_message = "Haha! Woo!"

        # CONFIRM button: Clean
        elif self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            self.poo = 0
            self.happiness = min(MAX_STAT, self.happiness + 15)
            self.status_message = "Ahhh, clean."


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

        # --- Status Message ---
        ctx.rgb(1, 1, 1)
        ctx.font_size = 18
        # Centered text using move_to only (no text_align)
        ctx.move_to(-40, -15)
        ctx.text(self.status_message)

        # --- Stat Bars ---
        self.draw_stat_bar(ctx, 5, "Hunger:", self.hunger, (1.0, 0.7, 0.0))
        self.draw_stat_bar(ctx, 20, "Happy:", self.happiness, (0.0, 1.0, 0.0))
        self.draw_stat_bar(ctx, 35, "Poo:", self.poo, (0.6, 0.4, 0.2))

        # --- Controls Hint ---
        ctx.rgb(0.7, 0.7, 0.7)
        ctx.font_size = 10
        
        # All centered using move_to only
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
