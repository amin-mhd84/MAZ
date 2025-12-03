import pygame

class Sylvanas :
    def __init__(self , screen , x , y) :
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
    def __init__(self, screen, x, y):
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