import pygame

# --------- hero images ---------
hero_images = {
    "sylvanas": pygame.image.load("./bgknowhow-main/images/heroes/BG23_HERO_306_render_80.webp"),
    "lich_king": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_22_render_80.webp"),
    "millhouse": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_49_render_80.webp"),
    "yogg_saron": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_35_render_80.webp")
}

def show_hero_selection_screen(screen, simple_font, title_font):
    screen.fill((30 , 30 , 60))
    
    selection_title = title_font.render("Choose Your Hero" , True , (255 , 215 , 0))
    title_rect = selection_title.get_rect(center=(400 , 50))
    screen.blit(selection_title, title_rect)
    
    hero_width = 150
    hero_height = 200
    spacing = 50
    start_x = 100
    base_y = 250
    name_y = 350
    
    heroes_data = [
        {"name": "Sylvanas" , "key" : "sylvanas" , "x" : start_x},
        {"name": "Lich King" , "key" : "lich_king" , "x" : start_x + hero_width + spacing},
        {"name": "Millhouse" , "key" : "millhouse" , "x" : start_x + 2 * (hero_width + spacing)},
        {"name": "Yogg-Saron" , "key" : "yogg_saron" , "x" : start_x + 3 * (hero_width + spacing)}
    ]
    
    hero_rects = {}
    for hero in heroes_data:
        hero_scaled = pygame.transform.smoothscale(hero_images[hero["key"]] , (hero_width , hero_height))
        hero_rect = hero_scaled.get_rect(center=(hero["x"] , base_y))
        screen.blit(hero_scaled, hero_rect)
        hero_rects[hero["key"]] = hero_rect
        
        hero_name = simple_font.render(hero["name"] , True , (255, 255, 255))
        hero_name_rect = hero_name.get_rect(center=(hero["x"] , name_y))
        screen.blit(hero_name, hero_name_rect)
    
    instruction = simple_font.render("Click on a hero to select", True, (200, 200, 200))
    instruction_rect = instruction.get_rect(center=(400, 500))
    screen.blit(instruction, instruction_rect)
    
    return hero_rects
