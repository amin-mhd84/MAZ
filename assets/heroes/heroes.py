import pygame
import random
class Sylvanas :
    def init(self , screen , x , y) :
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "Sylvanas Windrunner"
        self.hero_power_name = "Reclaimed Souls"
        self.hero_power_cost = 1
        self.hero_power_description = "Give +2/+1 to your minions that died last combat."
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/BG23_HERO_306_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))

    def draw(self):
        self.screen.blit(self.portrait , (self.x , self.y))
        font = pygame.font.Font(None , 24)
        name_text = font.render(self.name , True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} ({self.hero_power_cost} Gold)", True, (200, 200, 100))
        desc_text = font.render(self.hero_power_description, True, (200, 200, 200))
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        self.screen.blit(desc_text, (self.x, self.y + 150))

    def use_hero_power(self, gold):
        if gold >= self.hero_power_cost:
            print(f"{self.name} used {self.hero_power_name}!")
            return gold - self.hero_power_cost
        else:
            print("Not enough Gold!")
            return gold







class LichKing:
    def init(self, screen, x, y):
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "The Lich King"
        self.hero_power_name = "Reborn Rites"
        self.hero_power_cost = 1
        self.hero_power_description = "Give a friendly minion Reborn for the next combat only."
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_22_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))

    def draw(self):
        self.screen.blit(self.portrait, (self.x, self.y))
        font = pygame.font.Font(None, 24)
        name_text = font.render(self.name, True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} ({self.hero_power_cost} Gold)", True, (200, 200, 100))
        desc_text = font.render(self.hero_power_description, True, (200, 200, 200))
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        self.screen.blit(desc_text, (self.x, self.y + 150))

    def use_hero_power(self, gold, target_minion="Friendly Minion"):
        if gold >= self.hero_power_cost:
            print(f"{self.name} used {self.hero_power_name} on {target_minion}!")
            return gold - self.hero_power_cost
        else:
            print("Not enough Gold!")
            return gold
        





class MillhouseManastorm:
    def __init__(self, screen, x, y) :
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "Millhouse Manastorm"
        self.hero_power_name = "Manastorm"
        self.hero_power_cost = 0 
        self.hero_power_description = "Minions cost 2 Gold. Refreshes cost 2 Gold. Start with 3 Gold. (Tavern upgrades cost 1 more)"
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_49_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))
        self.is_passive = True

    def draw(self):
        self.screen.blit(self.portrait, (self.x, self.y))
        font = pygame.font.Font(None, 24)
        name_text = font.render(self.name, True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} (Passive)", True, (100, 200, 255))
        

        desc_lines = self.hero_power_description.split('. ')
        
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        

        y_offset = 150
        for line in desc_lines:
            if line: 
                desc_text = font.render(line.strip() + ".", True, (200, 200, 200))
                self.screen.blit(desc_text, (self.x, self.y + y_offset))
                y_offset += 20

    def use_hero_power(self, gold):

        print(f"{self.name}'s ability is passive and always active!")
        return gold 

    def apply_passive_effects(self, base_minion_cost, base_refresh_cost, base_upgrade_cost):

        modified_minion_cost = base_minion_cost + 2 
        modified_refresh_cost = base_refresh_cost + 2
        modified_upgrade_cost = base_upgrade_cost + 1
        
        return modified_minion_cost, modified_refresh_cost, modified_upgrade_cost
    





class YoggSaron:
    def __init__(self, screen, x, y):
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "Yogg-Saron"
        self.hero_power_name = "Puzzle Box"
        self.hero_power_cost = 2
        self.hero_power_description = "Add a random minion from your current Tavern Tier to your hand."
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_35_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))
        self.current_tavern_tier = 1

    def draw(self):
        self.screen.blit(self.portrait, (self.x, self.y))
        font = pygame.font.Font(None, 24)
        name_text = font.render(self.name, True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} ({self.hero_power_cost} Gold)", True, (200, 200, 100))
        desc_text = font.render(self.hero_power_description, True, (200, 200, 200))
        

        tavern_tier_text = font.render(f"Current Tavern Tier: {self.current_tavern_tier}", True, (150, 220, 150))
        
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        self.screen.blit(desc_text, (self.x, self.y + 150))
        self.screen.blit(tavern_tier_text, (self.x, self.y + 170))

    def use_hero_power(self, gold):
        if gold >= self.hero_power_cost:
            print(f"{self.name} used {self.hero_power_name}!")
            print(f"Adding a random minion from Tavern Tier {self.current_tavern_tier} to hand...")
            


            random_minion = self.get_random_minion_from_tier(self.current_tavern_tier)
            print(f"Added {random_minion} to your hand!")
            
            return gold - self.hero_power_cost
        else:
            print("Not enough Gold!")
            return gold

    def get_random_minion_from_tier(self, tier):


        minions_by_tier = {
            1: ["Alleycat", "Murloc Tidehunter", "Rockpool Hunter", "Selfless Hero"],
            2: ["Glyph Guardian", "Kaboom Bot", "Murloc Warleader", "Old Murk-Eye"],
            3: ["Crackling Cyclone", "Floating Watcher", "Houndmaster", "Imp Gang Boss"],
            4: ["Cave Hydra", "Defender of Argus", "Menagerie Magician", "Virmen Sensei"],
            5: ["Annihilan Battlemaster", "Baron Rivendare", "Lightfang Enforcer", "Mama Bear"],
            6: ["Ghastcoiler", "Kalecgos", "Maexxna", "Zapp Slywick"]
        }
        
        if tier in minions_by_tier and minions_by_tier[tier]:
            return random.choice(minions_by_tier[tier])
        return "Unknown Minion"

    def upgrade_tavern_tier(self):
        if self.current_tavern_tier < 6:
            self.current_tavern_tier += 1
            print(f"{self.name} upgraded to Tavern Tier {self.current_tavern_tier}!")
        else:
            print("Already at maximum Tavern Tier!")