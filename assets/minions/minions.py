import pygame
import random
import uuid

class Minion:
    def __init__(self, screen, x, y, card_id, name, attack, health, tier, tribe, keywords=None, description=""):
        self.screen = screen
        self.x = x
        self.y = y
        self.width = 80
        self.height = 120
        
      
        self.card_id = card_id
        self.name = name
        self.base_attack = attack
        self.base_health = health
        self.current_attack = attack
        self.current_health = health
        self.tier = tier
        self.tribe = tribe
        self.keywords = keywords or []
        self.description = description
        
        self.golden = False
        self.instance_id = f"minion_{uuid.uuid4().hex[:8]}"
        self.board_slot = None
        self.player_id = None
        
        self.divine_shield_active = "divine_shield" in self.keywords
        self.reborn_available = "reborn" in self.keywords
        self.taunt_active = "taunt" in self.keywords
        self.damage_taken = 0
        self.attacks_this_turn = 0
        
        
        self.highlighted = False
        self.dragging = False
        self.animating = False
        self.glow_alpha = 0
        
       
        try:
            self.image = pygame.image.load(f"./bgknowhow-main/images/minions/{card_id}_render_80.webp")
            self.image = pygame.transform.scale(self.image, (100, 140))
        except:
           
            self.image = pygame.Surface((80, 80))
            self.image.fill((100, 100, 150))
            pygame.draw.rect(self.image, (200, 200, 200), self.image.get_rect(), 2)
            font = pygame.font.Font(None, 14)
            name_parts = self.name.split()
            for i, part in enumerate(name_parts[:2]):
                text = font.render(part, True, (255, 255, 255))
                self.image.blit(text, (5, 10 + i * 15))
        
        # Load keyword icons
        self.keyword_icons = {}
        for keyword in self.keywords:
            try:
                icon = pygame.image.load(f"./bgknowhow-main/images/icons/{keyword}.png")
                self.keyword_icons[keyword] = pygame.transform.scale(icon, (20, 20))
            except:
                pass
        
    
    def draw(self):

        img_rect = self.image.get_rect(center=(self.x + self.width//2, self.y + 60))
        self.screen.blit(self.image, img_rect)
        
        # Name
        font = pygame.font.Font(None, 18)
        name_text = font.render(self.name, True, (255, 255, 255))
        name_rect = name_text.get_rect(center=(self.x + self.width//2, self.y - 15))
        self.screen.blit(name_text, name_rect)
        
        # Tier
        tier_font = pygame.font.Font(None, 16)
        tier_text = tier_font.render(f"T{self.tier}", True, (200, 200, 200))
        self.screen.blit(tier_text, (self.x + 5, self.y + 5))
        
        # Attack and Health circles
        self._draw_stats()
        

        # Damage indicator
        if self.damage_taken > 0:
            damage_font = pygame.font.Font(None, 16)
            damage_text = damage_font.render(f"-{self.damage_taken}", True, (255, 100, 100))
            self.screen.blit(damage_text, (self.x + self.width - 20, self.y + self.height - 40))
    
    def _draw_stats(self):
        # Attack circle 
        attack_center = (self.x + 20, self.y + self.height - 20)
        pygame.draw.circle(self.screen, (50, 50, 50), attack_center, 15)
        pygame.draw.circle(self.screen, (255, 100, 100), attack_center, 15, 2)
        
        attack_font = pygame.font.Font(None, 22)
        attack_text = attack_font.render(str(self.current_attack), True, (255, 255, 255))
        attack_rect = attack_text.get_rect(center=attack_center)
        self.screen.blit(attack_text, attack_rect)
        
        # Health circle 
        health_center = (self.x + self.width - 20, self.y + self.height - 20)
        pygame.draw.circle(self.screen, (50, 50, 50), health_center, 15)
        pygame.draw.circle(self.screen, (100, 255, 100), health_center, 15, 2)
        
        health_font = pygame.font.Font(None, 22)
        health_text = health_font.render(str(self.current_health - self.damage_taken), True, (255, 255, 255))
        health_rect = health_text.get_rect(center=health_center)
        self.screen.blit(health_text, health_rect)
    
    
    def take_damage(self, damage):

        if self.divine_shield_active:
            self.divine_shield_active = False
            return "shield_broken", 0
        
        self.damage_taken += damage
        current_health = self.current_health - self.damage_taken
        
        if current_health <= 0:
            if self.reborn_available:
                return "died_with_reborn", damage
            return "died", damage
        
        return "damaged", damage
    
    def is_alive(self):
        return (self.current_health - self.damage_taken) > 0
    
    def has_taunt(self):
        return self.taunt_active and self.is_alive()
    
    def has_divine_shield(self):
        return self.divine_shield_active and self.is_alive()
    
    def reset_for_new_combat(self):
        self.damage_taken = 0
        self.attacks_this_turn = 0
        
        if "divine_shield" in self.keywords:
            self.divine_shield_active = True
    
    def make_golden(self):
        self.golden = True
        self.current_attack = self.base_attack * 2
        self.current_health = self.base_health * 2
        return self
    
    def add_buff(self, attack_buff, health_buff):
        self.current_attack += attack_buff
        self.current_health += health_buff
    
    def contains_point(self, point):
        rect = pygame.Rect(self.x, self.y, self.width, self.height)
        return rect.collidepoint(point)
    
    def to_dict(self):
        return {
            "card_id": self.card_id,
            "name": self.name,
            "attack": self.current_attack,
            "health": self.current_health,
            "damage_taken": self.damage_taken,
            "tier": self.tier,
            "tribe": self.tribe,
            "keywords": self.keywords,
            "golden": self.golden,
            "instance_id": self.instance_id,
            "board_slot": self.board_slot,
            "player_id": self.player_id
        }

def create_minion(screen, x, y, card_id, golden=False):
    
    minion_database = {

        "BG31_803": {
            "name": "Buzzing Vermin",
            "attack": 2,
            "health": 3,
            "tier": 1,
            "tribe": "beetle",
            "keywords": ["taunt", "deathrattle"],
            "description": "Taunt. Deathrattle: Summon a 1/1 Beetle."
        },
        "BG31_801": {
            "name": "Forest Rover",
            "attack": 3,
            "health": 3,
            "tier": 2,
            "tribe": "beetle",
            "keywords": ["battlecry", "deathrattle"],
            "description": "Battlecry: Give all your Beetles in the game +1/+1. Deathrattle: Summon a 1/1 Beetle."
        },
        "BG27_084": {
            "name": "Sprightly Scarab",
            "attack": 3,
            "health": 3,
            "tier": 3,
            "tribe": "beast",
            "keywords": ["choose_one"],
            "description": "Choose One: Give a Beast +1/+1 and Reborn; or +4 Attack and Windfury."
        },
        "BG31_809": {
            "name": "Turquoise Skitterer",
            "attack": 5,
            "health": 3,
            "tier": 4,
            "tribe": "beetle",
            "keywords": ["deathrattle"],
            "description": "Deathrattle: Give all your Beetles in the game +1/+2. Summon a 1/1 Beetle."
        },
        "BG31_807": {
            "name": "Nest Swarmer",
            "attack": 6,
            "health": 3,
            "tier": 5,
            "tribe": "beetle",
            "keywords": ["deathrattle"],
            "description": "Deathrattle: Summon three 1/1 Beetles."
        },
        "BGS_078": {
            "name": "Monstrous Macaw",
            "attack": 5,
            "health": 3,
            "tier": 6,
            "tribe": "beast",
            "keywords": ["on_attack"],
            "description": "After this attacks, trigger the Deathrattle of your leftmost minion."
        },
        
        "BGS_004": {
            "name": "Wrath Weaver",
            "attack": 1,
            "health": 3,
            "tier": 1,
            "tribe": "demon",
            "keywords": ["on_play"],
            "description": "After you play a Demon, gain +2/+2 and take 1 damage."
        },
        "BGS_044": {
            "name": "Imp Mama",
            "attack": 6,
            "health": 6,
            "tier": 4,
            "tribe": "demon",
            "keywords": ["taunt", "deathrattle"],
            "description": "Taunt. Deathrattle: Summon a random Demon and give it Taunt."
        },
        "BG29_140": {
            "name": "False Implicator",
            "attack": 3,
            "health": 3,
            "tier": 2,
            "tribe": "demon",
            "keywords": ["end_of_turn"],
            "description": "At end of your turn, consume a minion in the Tavern to gain its stats."
        },
        "BG31_874": {
            "name": "Furious Driver",
            "attack": 6,
            "health": 6,
            "tier": 5,
            "tribe": "demon",
            "keywords": ["battlecry"],
            "description": "Battlecry: Your other Demons each consume a minion in the Tavern to gain its stats."
        },
        "BG21_005": {
            "name": "Famished Felbat",
            "attack": 4,
            "health": 6,
            "tier": 6,
            "tribe": "demon",
            "keywords": ["end_of_turn"],
            "description": "At end of your turn, your Demons each consume a minion in the Tavern to gain double its stats."
        },
        
        "BG28_300": {
            "name": "Harmless Bonehead",
            "attack": 1,
            "health": 2,
            "tier": 1,
            "tribe": "undead",
            "keywords": ["deathrattle"],
            "description": "Deathrattle: Summon two 1/1 Skeletons."
        },
        "BG25_010": {
            "name": "Handless Forsaken",
            "attack": 3,
            "health": 2,
            "tier": 2,
            "tribe": "undead",
            "keywords": ["deathrattle"],
            "description": "Deathrattle: Summon a 2/1 Hand with Reborn."
        },
        "BG25_011": {
            "name": "Nerubian Deathswarmer",
            "attack": 2,
            "health": 3,
            "tier": 3,
            "tribe": "undead",
            "keywords": ["battlecry"],
            "description": "Battlecry: Give all your Undead in the game +1 Attack."
        },
        "BG25_008": {
            "name": "Eternal Knight",
            "attack": 3,
            "health": 3,
            "tier": 4,
            "tribe": "undead",
            "keywords": ["start_of_combat"],
            "description": "Start of Combat: Gain +1/+1 for each Eternal Knight that died this game."
        },
        "BG25_009": {
            "name": "Eternal Summoner",
            "attack": 4,
            "health": 4,
            "tier": 5,
            "tribe": "undead",
            "keywords": ["reborn", "deathrattle"],
            "description": "Reborn. Deathrattle: Summon two Eternal Knights."
        },
        "BG30_129": {
            "name": "Catacomb Crasher",
            "attack": 4,
            "health": 6,
            "tier": 6,
            "tribe": "undead",
            "keywords": ["aura"],
            "description": "Whenever you would summon a minion but your board is full, give your minions +1/+1 instead."
        },
        "BG25_354": {
            "name": "Titus Rivendare",
            "attack": 1,
            "health": 7,
            "tier": 5,
            "tribe": "undead",
            "keywords": ["aura"],
            "description": "Aura: Your Deathrattles trigger an extra time."
        }
    }
    
    if card_id not in minion_database:

        return Minion(
            screen, x, y,
            card_id=card_id,
            name="Unknown Minion",
            attack=1,
            health=1,
            tier=1,
            tribe="neutral",
            keywords=[]
        )
    
    data = minion_database[card_id]
    minion = Minion(
        screen, x, y,
        card_id=card_id,
        name=data["name"],
        attack=data["attack"],
        health=data["health"],
        tier=data["tier"],
        tribe=data["tribe"],
        keywords=data["keywords"],
        description=data["description"]
    )
    
    if golden:
        minion.make_golden()
    
    return minion

class MinionManager:
    def __init__(self, screen):
        self.screen = screen
        self.minions = []
        self.selected_minion = None
    
    def add_minion(self, card_id, x, y, golden=False):
        """Add a new minion"""
        minion = create_minion(self.screen, x, y, card_id, golden)
        self.minions.append(minion)
        return minion
    
    def get_minion_at(self, x, y):
        """Get minion at position"""
        for minion in self.minions:
            if minion.contains_point((x, y)):
                return minion
        return None
    
    def remove_minion(self, minion):
        """Remove a minion"""
        if minion in self.minions:
            self.minions.remove(minion)
            if self.selected_minion == minion:
                self.selected_minion = None
    
    def draw_all(self):
        for minion in self.minions:
            minion.draw()
    

if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 700))
    clock = pygame.time.Clock()
    
    manager = MinionManager(screen)
    
    # Add some minions
    manager.add_minion("BG31_803", 50, 60)
    manager.add_minion("BG31_801", 170, 60)  
    manager.add_minion("BG31_809", 290, 60)
    manager.add_minion("BG31_807", 410, 60)
    manager.add_minion("BGS_078", 530, 60)
    manager.add_minion("BGS_004", 650, 60)


    manager.add_minion("BGS_044", 50, 230)   
    manager.add_minion("BG29_140", 170, 230)
    manager.add_minion("BG31_874", 290, 230)
    manager.add_minion("BG21_005", 410, 230)
    manager.add_minion("BG28_300", 530, 230) 
    manager.add_minion("BG25_010", 650, 230)

    manager.add_minion("BG25_011", 50, 400) 
    manager.add_minion("BG25_008", 170, 400)
    manager.add_minion("BG25_009", 290, 400)
    manager.add_minion("BG30_129", 410, 400)
    manager.add_minion("BG25_354", 530, 400)
    manager.add_minion("BG25_354", 650, 400,golden=True)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                minion = manager.get_minion_at(x, y)
                if minion:
                    manager.selected_minion = minion
                    print(f"Selected: {minion.name}")
                    
                    result, damage = minion.take_damage(2)
                    print(f"{minion.name} took {damage} damage: {result}")
        
        screen.fill((30, 30, 50))
        
        manager.draw_all()
        
        font = pygame.font.Font(None, 24)
        text = font.render("Click minions to select and deal 2 damage", True, (255, 255, 255))
        screen.blit(text, (50, 600))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()