#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <queue>
#include <memory>
#include <thread>
#include <mutex>
#include <atomic>
#include <chrono>
#include <random>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <functional>
#include <fstream>

#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <boost/beast/websocket.hpp>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using namespace std::chrono;

// ==================== Namespace & Type Aliases ====================
namespace beast = boost::beast;
namespace http = beast::http;
namespace websocket = beast::websocket;
namespace net = boost::asio;
using tcp = boost::asio::ip::tcp;

// ==================== Constants & Enums ====================
const int PORT = 8888;
const int MAX_PLAYERS = 4;
const int START_GOLD = 3;
const int START_HEALTH = 40;
const int SHOP_SIZE = 5;
const float TURN_DURATION = 30.0f;
const float GRACE_PERIOD = 2.0f;
const float HERO_SELECT_TIME = 15.0f;
const float COMBAT_LOG_TIME = 5.0f;
const int MAX_BOARD_SIZE = 7;
const int MAX_HAND_SIZE = 10;
const int CARD_COPIES_PER_POOL = 10;

enum class GamePhase {
    LOBBY,
    HERO_SELECT,
    RECRUIT,
    COMBAT_CALC,
    LOG_REPLAY,
    GAME_OVER
};

enum class HeroType {
    SYLVANAS,
    LICH_KING,
    MILLHOUSE,
    YOGG,
    PATCHES,
    RAGNAROS,
    KELTHUZAD,
    MALGANIS
};

enum class MinionType {
    NEUTRAL,
    BEAST,
    DEMON,
    DRAGON,
    ELEMENTAL,
    MECH,
    MURLOC,
    PIRATE,
    QUILBOAR,
    NAGA
};

enum class Ability {
    NONE,
    TAUNT,
    DIVINE_SHIELD,
    POISONOUS,
    WINDFURY,
    REBORN,
    DEATHRATTLE,
    BATTLE_CRY,
    AURA
};

std::string phaseToString(GamePhase phase) {
    switch(phase) {
        case GamePhase::LOBBY: return "LOBBY";
        case GamePhase::HERO_SELECT: return "HERO_SELECT";
        case GamePhase::RECRUIT: return "RECRUIT";
        case GamePhase::COMBAT_CALC: return "COMBAT_CALC";
        case GamePhase::LOG_REPLAY: return "LOG_REPLAY";
        case GamePhase::GAME_OVER: return "GAME_OVER";
        default: return "UNKNOWN";
    }
}

// ==================== UUID Generator ====================
class UUIDGenerator {
private:
    static std::random_device rd;
    static std::mt19937_64 gen;
    static std::uniform_int_distribution<uint64_t> dis;
    
public:
    static std::string generate() {
        uint64_t part1 = dis(gen);
        uint64_t part2 = dis(gen);
        
        std::stringstream ss;
        ss << std::hex << std::setfill('0')
           << std::setw(16) << part1
           << std::setw(16) << part2;
        
        std::string result = ss.str();
        
        // Format as 8-4-4-4-12
        return result.substr(0, 8) + "-" +
               result.substr(8, 4) + "-" +
               result.substr(12, 4) + "-" +
               result.substr(16, 4) + "-" +
               result.substr(20, 12);
    }
};

std::random_device UUIDGenerator::rd;
std::mt19937_64 UUIDGenerator::gen(UUIDGenerator::rd());
std::uniform_int_distribution<uint64_t> UUIDGenerator::dis;

// ==================== Global Card Pool ====================
class CardPool {
private:
    static std::unordered_map<std::string, int> cardStock;
    static std::mutex poolMutex;
    static bool initialized;
    
    static void initialize() {
        std::lock_guard<std::mutex> lock(poolMutex);
        if (initialized) return;
        
        // Initialize all minions with limited copies
        std::vector<std::string> allMinions = {
            "BG_001", "BG_002", "BG_003", "BG_004", "BG_005",
            "BG_006", "BG_007", "BG_008", "BG_009", "BG_010",
            "BG_011", "BG_012", "BG_013", "BG_014", "BG_015",
            "BG_016", "BG_017", "BG_018", "BG_019", "BG_020",
            "BG_021", "BG_022", "BG_023", "BG_024", "BG_025",
            "BG_026", "BG_027", "BG_028", "BG_029", "BG_030"
        };
        
        for (const auto& cardId : allMinions) {
            cardStock[cardId] = CARD_COPIES_PER_POOL;
        }
        
        initialized = true;
    }
    
public:
    static bool canTakeCard(const std::string& cardId) {
        initialize();
        std::lock_guard<std::mutex> lock(poolMutex);
        auto it = cardStock.find(cardId);
        if (it == cardStock.end()) return false;
        return it->second > 0;
    }
    
    static bool takeCard(const std::string& cardId) {
        initialize();
        std::lock_guard<std::mutex> lock(poolMutex);
        auto it = cardStock.find(cardId);
        if (it == cardStock.end() || it->second <= 0) {
            return false;
        }
        it->second--;
        return true;
    }
    
    static void returnCard(const std::string& cardId) {
        initialize();
        std::lock_guard<std::mutex> lock(poolMutex);
        auto it = cardStock.find(cardId);
        if (it != cardStock.end()) {
            it->second++;
        }
    }
    
    static std::vector<std::string> getAvailableCardsByTier(int tier) {
        initialize();
        std::lock_guard<std::mutex> lock(poolMutex);
        std::vector<std::string> available;
        
        // Simple tier mapping (you should expand this)
        std::vector<std::string> tierCards;
        switch(tier) {
            case 1: tierCards = {"BG_001", "BG_002", "BG_003", "BG_004", "BG_005"}; break;
            case 2: tierCards = {"BG_006", "BG_007", "BG_008", "BG_009", "BG_010"}; break;
            case 3: tierCards = {"BG_011", "BG_012", "BG_013", "BG_014", "BG_015"}; break;
            case 4: tierCards = {"BG_016", "BG_017", "BG_018", "BG_019", "BG_020"}; break;
            case 5: tierCards = {"BG_021", "BG_022", "BG_023", "BG_024", "BG_025"}; break;
            case 6: tierCards = {"BG_026", "BG_027", "BG_028", "BG_029", "BG_030"}; break;
            default: return available;
        }
        
        for (const auto& cardId : tierCards) {
            if (cardStock[cardId] > 0) {
                available.push_back(cardId);
            }
        }
        
        return available;
    }
    
    static void reset() {
        std::lock_guard<std::mutex> lock(poolMutex);
        initialized = false;
        cardStock.clear();
    }
    
    static json toJson() {
        initialize();
        std::lock_guard<std::mutex> lock(poolMutex);
        json j;
        for (const auto& [cardId, count] : cardStock) {
            j[cardId] = count;
        }
        return j;
    }
};

std::unordered_map<std::string, int> CardPool::cardStock;
std::mutex CardPool::poolMutex;
bool CardPool::initialized = false;

// ==================== Minion Class ====================
class Minion {
private:
    std::string minionId;
    std::string name;
    MinionType tribe;
    int attack;
    int health;
    int tier;
    std::vector<Ability> abilities;
    std::string instanceId;
    int playerIndex = -1;
    bool golden = false;
    std::string originalId; // For golden minions
    
public:
    Minion() : minionId(""), name(""), tribe(MinionType::NEUTRAL), 
               attack(0), health(0), tier(1), instanceId(""), originalId("") {}
    
    Minion(const std::string& id, const std::string& n, MinionType t, 
           int a, int h, int tier, std::vector<Ability> ab = {})
        : minionId(id), name(n), tribe(t), attack(a), health(h), 
          tier(tier), abilities(ab), instanceId(UUIDGenerator::generate()),
          playerIndex(-1), golden(false), originalId(id) {}
    
    Minion(const Minion& other)
        : minionId(other.minionId), name(other.name), tribe(other.tribe),
          attack(other.attack), health(other.health), tier(other.tier),
          abilities(other.abilities), instanceId(UUIDGenerator::generate()),
          playerIndex(other.playerIndex), golden(other.golden),
          originalId(other.originalId) {}
    
    // Create golden version
    static std::shared_ptr<Minion> createGolden(const Minion& base) {
        auto golden = std::make_shared<Minion>(base);
        golden->golden = true;
        golden->attack *= 2;
        golden->health *= 2;
        golden->minionId = base.minionId + "_GOLDEN";
        golden->name = "Golden " + base.name;
        return golden;
    }
    
    std::string getId() const { return minionId; }
    std::string getName() const { return name; }
    MinionType getTribe() const { return tribe; }
    int getAttack() const { return attack; }
    int getHealth() const { return health; }
    int getTier() const { return tier; }
    std::vector<Ability> getAbilities() const { return abilities; }
    std::string getInstanceId() const { return instanceId; }
    int getPlayerIndex() const { return playerIndex; }
    bool isGolden() const { return golden; }
    std::string getOriginalId() const { return originalId; }
    
    void setPlayerIndex(int idx) { playerIndex = idx; }
    void setGolden(bool g) { golden = g; }
    void buff(int atk, int hp) { attack += atk; health += hp; }
    void takeDamage(int damage) { health -= damage; }
    bool isDead() const { return health <= 0; }
    
    bool hasAbility(Ability ability) const {
        return std::find(abilities.begin(), abilities.end(), ability) != abilities.end();
    }
    
    void addAbility(Ability ability) {
        if (!hasAbility(ability)) {
            abilities.push_back(ability);
        }
    }
    
    json toJson() const {
        json abilityArray = json::array();
        for (auto& ab : abilities) {
            switch(ab) {
                case Ability::TAUNT: abilityArray.push_back("TAUNT"); break;
                case Ability::DIVINE_SHIELD: abilityArray.push_back("DIVINE_SHIELD"); break;
                case Ability::POISONOUS: abilityArray.push_back("POISONOUS"); break;
                case Ability::WINDFURY: abilityArray.push_back("WINDFURY"); break;
                case Ability::REBORN: abilityArray.push_back("REBORN"); break;
                case Ability::DEATHRATTLE: abilityArray.push_back("DEATHRATTLE"); break;
                case Ability::BATTLE_CRY: abilityArray.push_back("BATTLE_CRY"); break;
                case Ability::AURA: abilityArray.push_back("AURA"); break;
                default: abilityArray.push_back("NONE"); break;
            }
        }
        
        std::string tribeStr;
        switch(tribe) {
            case MinionType::BEAST: tribeStr = "BEAST"; break;
            case MinionType::DEMON: tribeStr = "DEMON"; break;
            case MinionType::DRAGON: tribeStr = "DRAGON"; break;
            case MinionType::ELEMENTAL: tribeStr = "ELEMENTAL"; break;
            case MinionType::MECH: tribeStr = "MECH"; break;
            case MinionType::MURLOC: tribeStr = "MURLOC"; break;
            case MinionType::PIRATE: tribeStr = "PIRATE"; break;
            case MinionType::QUILBOAR: tribeStr = "QUILBOAR"; break;
            case MinionType::NAGA: tribeStr = "NAGA"; break;
            default: tribeStr = "NEUTRAL"; break;
        }
        
        return {
            {"minion_id", minionId},
            {"original_id", originalId},
            {"name", name},
            {"tribe", tribeStr},
            {"attack", attack},
            {"health", health},
            {"tier", tier},
            {"abilities", abilityArray},
            {"instance_id", instanceId},
            {"player_index", playerIndex},
            {"golden", golden}
        };
    }
};

// ==================== Card Database ====================
class CardDatabase {
private:
    static std::unordered_map<std::string, Minion> minions;
    static std::vector<std::string> tier1Minions;
    static std::vector<std::string> tier2Minions;
    static std::vector<std::string> tier3Minions;
    static std::vector<std::string> tier4Minions;
    static std::vector<std::string> tier5Minions;
    static std::vector<std::string> tier6Minions;
    
    static void initialize() {
        // Tier 1 Minions
        minions["BG_001"] = Minion("BG_001", "Alleycat", MinionType::BEAST, 1, 1, 1);
        minions["BG_002"] = Minion("BG_002", "Murloc Tidehunter", MinionType::MURLOC, 2, 1, 1, {Ability::BATTLE_CRY});
        minions["BG_003"] = Minion("BG_003", "Rockpool Hunter", MinionType::MURLOC, 2, 3, 1, {Ability::BATTLE_CRY});
        minions["BG_004"] = Minion("BG_004", "Selfless Hero", MinionType::NEUTRAL, 2, 1, 1, {Ability::DEATHRATTLE});
        minions["BG_005"] = Minion("BG_005", "Vulgar Homunculus", MinionType::DEMON, 2, 4, 1, {Ability::TAUNT});
        
        // Tier 2 Minions
        minions["BG_006"] = Minion("BG_006", "Harvest Golem", MinionType::MECH, 2, 3, 2, {Ability::DEATHRATTLE});
        minions["BG_007"] = Minion("BG_007", "Kaboom Bot", MinionType::MECH, 2, 2, 2, {Ability::DEATHRATTLE});
        minions["BG_008"] = Minion("BG_008", "Murloc Warleader", MinionType::MURLOC, 3, 3, 2, {Ability::AURA});
        minions["BG_009"] = Minion("BG_009", "Nathrezim Overseer", MinionType::DEMON, 2, 3, 2, {Ability::BATTLE_CRY});
        minions["BG_010"] = Minion("BG_010", "Old Murk-Eye", MinionType::MURLOC, 3, 4, 2);
        
        // Tier 3 Minions
        minions["BG_011"] = Minion("BG_011", "Cobalt Guardian", MinionType::MECH, 6, 3, 3);
        minions["BG_012"] = Minion("BG_012", "Floating Watcher", MinionType::DEMON, 4, 4, 3);
        minions["BG_013"] = Minion("BG_013", "Soul Juggler", MinionType::DEMON, 3, 3, 3, {Ability::DEATHRATTLE});
        minions["BG_014"] = Minion("BG_014", "Imp Gang Boss", MinionType::DEMON, 2, 4, 3);
        minions["BG_015"] = Minion("BG_015", "Murloc Knight", MinionType::MURLOC, 3, 4, 3);
        
        // Tier 4 Minions
        minions["BG_016"] = Minion("BG_016", "Cave Hydra", MinionType::BEAST, 2, 4, 4);
        minions["BG_017"] = Minion("BG_017", "Defender of Argus", MinionType::NEUTRAL, 2, 3, 4, {Ability::BATTLE_CRY});
        minions["BG_018"] = Minion("BG_018", "Menagerie Magician", MinionType::NEUTRAL, 4, 4, 4, {Ability::BATTLE_CRY});
        minions["BG_019"] = Minion("BG_019", "Sated Threshadon", MinionType::BEAST, 5, 7, 4, {Ability::DEATHRATTLE});
        minions["BG_020"] = Minion("BG_020", "Virmen Sensei", MinionType::BEAST, 4, 5, 4, {Ability::BATTLE_CRY});
        
        // Tier 5 Minions
        minions["BG_021"] = Minion("BG_021", "Baron Rivendare", MinionType::NEUTRAL, 1, 7, 5, {Ability::AURA});
        minions["BG_022"] = Minion("BG_022", "Brann Bronzebeard", MinionType::NEUTRAL, 2, 4, 5, {Ability::AURA});
        minions["BG_023"] = Minion("BG_023", "Lightfang Enforcer", MinionType::NEUTRAL, 2, 2, 5, {Ability::AURA});
        minions["BG_024"] = Minion("BG_024", "Mythrax", MinionType::NEUTRAL, 4, 4, 5);
        minions["BG_025"] = Minion("BG_025", "Strongshell Scavenger", MinionType::BEAST, 2, 3, 5, {Ability::BATTLE_CRY});
        
        // Tier 6 Minions
        minions["BG_026"] = Minion("BG_026", "Ghastcoiler", MinionType::BEAST, 7, 7, 6, {Ability::DEATHRATTLE});
        minions["BG_027"] = Minion("BG_027", "Kangor's Apprentice", MinionType::MECH, 3, 6, 6, {Ability::DEATHRATTLE});
        minions["BG_028"] = Minion("BG_028", "Mama Bear", MinionType::BEAST, 5, 5, 6, {Ability::AURA});
        minions["BG_029"] = Minion("BG_029", "Zapp Slywick", MinionType::NEUTRAL, 7, 10, 6);
        minions["BG_030"] = Minion("BG_030", "Holy Mackerel", MinionType::MURLOC, 8, 4, 6, {Ability::DIVINE_SHIELD});
        
        // Initialize tier lists
        tier1Minions = {"BG_001", "BG_002", "BG_003", "BG_004", "BG_005"};
        tier2Minions = {"BG_006", "BG_007", "BG_008", "BG_009", "BG_010"};
        tier3Minions = {"BG_011", "BG_012", "BG_013", "BG_014", "BG_015"};
        tier4Minions = {"BG_016", "BG_017", "BG_018", "BG_019", "BG_020"};
        tier5Minions = {"BG_021", "BG_022", "BG_023", "BG_024", "BG_025"};
        tier6Minions = {"BG_026", "BG_027", "BG_028", "BG_029", "BG_030"};
    }
    
public:
    static const Minion& getMinion(const std::string& id) {
        static bool initialized = false;
        if (!initialized) {
            initialize();
            initialized = true;
        }
        auto it = minions.find(id);
        if (it == minions.end()) {
            throw std::runtime_error("Minion not found: " + id);
        }
        return it->second;
    }
    
    static std::vector<std::string> getMinionsByTier(int tier) {
        static bool initialized = false;
        if (!initialized) {
            initialize();
            initialized = true;
        }
        
        switch(tier) {
            case 1: return tier1Minions;
            case 2: return tier2Minions;
            case 3: return tier3Minions;
            case 4: return tier4Minions;
            case 5: return tier5Minions;
            case 6: return tier6Minions;
            default: return {};
        }
    }
    
    static std::vector<std::string> getAllMinionIds() {
        static bool initialized = false;
        if (!initialized) {
            initialize();
            initialized = true;
        }
        
        std::vector<std::string> ids;
        for (const auto& pair : minions) {
            ids.push_back(pair.first);
        }
        return ids;
    }
};

std::unordered_map<std::string, Minion> CardDatabase::minions;
std::vector<std::string> CardDatabase::tier1Minions;
std::vector<std::string> CardDatabase::tier2Minions;
std::vector<std::string> CardDatabase::tier3Minions;
std::vector<std::string> CardDatabase::tier4Minions;
std::vector<std::string> CardDatabase::tier5Minions;
std::vector<std::string> CardDatabase::tier6Minions;

// ==================== Hero Class ====================
class Hero {
private:
    HeroType type;
    std::string name;
    int powerCost;
    std::string powerDescription;
    bool powerUsedThisTurn = false;
    bool passive = false;
    
public:
    Hero(HeroType t) : type(t) {
        switch(t) {
            case HeroType::SYLVANAS:
                name = "Sylvanas Windrunner";
                powerCost = 1;
                powerDescription = "Give +2/+1 to your minions that died last combat.";
                passive = false;
                break;
            case HeroType::LICH_KING:
                name = "The Lich King";
                powerCost = 1;
                powerDescription = "Give a friendly minion Reborn for the next combat only.";
                passive = false;
                break;
            case HeroType::MILLHOUSE:
                name = "Millhouse Manastorm";
                powerCost = 0;
                powerDescription = "Minions cost 2 Gold. Refreshes cost 2 Gold. Start with 3 Gold. (Passive)";
                passive = true;
                break;
            case HeroType::YOGG:
                name = "Yogg-Saron";
                powerCost = 2;
                powerDescription = "Add a random minion from your current Tavern Tier to your hand.";
                passive = false;
                break;
            case HeroType::PATCHES:
                name = "Patches the Pirate";
                powerCost = 0;
                powerDescription = "After you buy a Pirate, give it +1/+1.";
                passive = true;
                break;
            case HeroType::RAGNAROS:
                name = "Ragnaros the Firelord";
                powerCost = 2;
                powerDescription = "Deal 8 damage to two random enemy minions.";
                passive = false;
                break;
            case HeroType::KELTHUZAD:
                name = "Kel'Thuzad";
                powerCost = 1;
                powerDescription = "Give a friendly minion 'Deathrattle: Summon a 1/1 Skeleton.'";
                passive = false;
                break;
            case HeroType::MALGANIS:
                name = "Mal'Ganis";
                powerCost = 1;
                powerDescription = "Give a friendly Demon +2/+2.";
                passive = false;
                break;
        }
    }
    
    HeroType getType() const { return type; }
    std::string getName() const { return name; }
    int getPowerCost() const { return powerCost; }
    std::string getPowerDescription() const { return powerDescription; }
    bool isPassive() const { return passive; }
    
    void resetTurn() {
        if (!passive) {
            powerUsedThisTurn = false;
        }
    }
    
    bool canUsePower(int gold) const {
        return !passive && !powerUsedThisTurn && gold >= powerCost;
    }
    
    void markUsed() {
        if (!passive) {
            powerUsedThisTurn = true;
        }
    }
    
    bool isPowerUsed() const { return powerUsedThisTurn; }
    
    json toJson() const {
        return {
            {"type", static_cast<int>(type)},
            {"name", name},
            {"power_cost", powerCost},
            {"power_description", powerDescription},
            {"power_used", powerUsedThisTurn},
            {"passive", passive}
        };
    }
};

// ==================== Player Board ====================
class PlayerBoard {
private:
    std::vector<std::shared_ptr<Minion>> minions;
    int maxSize = MAX_BOARD_SIZE;
    
public:
    bool addMinion(std::shared_ptr<Minion> minion) {
        if (minions.size() >= maxSize) return false;
        minions.push_back(minion);
        return true;
    }
    
    bool removeMinion(const std::string& instanceId) {
        for (auto it = minions.begin(); it != minions.end(); ++it) {
            if ((*it)->getInstanceId() == instanceId) {
                minions.erase(it);
                return true;
            }
        }
        return false;
    }
    
    std::shared_ptr<Minion> getMinion(const std::string& instanceId) {
        for (auto& minion : minions) {
            if (minion->getInstanceId() == instanceId) {
                return minion;
            }
        }
        return nullptr;
    }
    
    std::shared_ptr<Minion> getMinionByIndex(size_t index) {
        if (index < minions.size()) {
            return minions[index];
        }
        return nullptr;
    }
    
    size_t size() const { return minions.size(); }
    bool isFull() const { return minions.size() >= maxSize; }
    
    std::vector<std::shared_ptr<Minion>>& getMinionsRef() { return minions; }
    const std::vector<std::shared_ptr<Minion>>& getMinions() const { return minions; }
    
    void clear() { minions.clear(); }
    
    json toJson() const {
        json minionArray = json::array();
        for (const auto& minion : minions) {
            minionArray.push_back(minion->toJson());
        }
        return minionArray;
    }
};

// ==================== Player Hand ====================
class PlayerHand {
private:
    std::vector<std::shared_ptr<Minion>> minions;
    int maxSize = MAX_HAND_SIZE;
    
public:
    bool addMinion(std::shared_ptr<Minion> minion) {
        if (minions.size() >= maxSize) return false;
        minions.push_back(minion);
        return true;
    }
    
    bool removeMinion(const std::string& instanceId) {
        for (auto it = minions.begin(); it != minions.end(); ++it) {
            if ((*it)->getInstanceId() == instanceId) {
                minions.erase(it);
                return true;
            }
        }
        return false;
    }
    
    std::shared_ptr<Minion> getMinion(const std::string& instanceId) {
        for (auto& minion : minions) {
            if (minion->getInstanceId() == instanceId) {
                return minion;
            }
        }
        return nullptr;
    }
    
    size_t size() const { return minions.size(); }
    bool isFull() const { return minions.size() >= maxSize; }
    
    std::vector<std::shared_ptr<Minion>>& getMinionsRef() { return minions; }
    const std::vector<std::shared_ptr<Minion>>& getMinions() const { return minions; }
    
    json toJson() const {
        json minionArray = json::array();
        for (const auto& minion : minions) {
            minionArray.push_back(minion->toJson());
        }
        return minionArray;
    }
};

// ==================== Shop ====================
class Shop {
private:
    std::vector<std::shared_ptr<Minion>> slots;
    bool frozen = false;
    int tavernTier = 1;
    
public:
    Shop() : slots(SHOP_SIZE) {}
    
    void refresh(std::mt19937& rng) {
        if (frozen) {
            // Only refresh non-frozen slots or slots that are nullptr
            for (size_t i = 0; i < slots.size(); i++) {
                if (slots[i] == nullptr) {
                    refreshSlot(i, rng);
                }
            }
            return;
        }
        
        slots.clear();
        int availableSlots = (tavernTier == 1 ? 3 : SHOP_SIZE);
        
        for (int i = 0; i < availableSlots; i++) {
            refreshSlot(i, rng);
        }
        
        // Fill remaining slots if tavern tier > 1 but less than max slots
        while (slots.size() < SHOP_SIZE) {
            slots.push_back(nullptr);
        }
    }
    
    void refreshSlot(int slotIndex, std::mt19937& rng) {
        if (slotIndex < 0 || slotIndex >= SHOP_SIZE) return;
        
        auto availableCards = CardPool::getAvailableCardsByTier(tavernTier);
        if (availableCards.empty()) {
            slots[slotIndex] = nullptr;
            return;
        }
        
        std::uniform_int_distribution<> dist(0, availableCards.size() - 1);
        std::string minionId = availableCards[dist(rng)];
        
        // Check if we can take this card from pool
        if (CardPool::takeCard(minionId)) {
            slots[slotIndex] = std::make_shared<Minion>(CardDatabase::getMinion(minionId));
        } else {
            slots[slotIndex] = nullptr;
        }
    }
    
    std::shared_ptr<Minion> buySlot(int slotIndex) {
        if (slotIndex < 0 || slotIndex >= slots.size()) return nullptr;
        if (slots[slotIndex] == nullptr) return nullptr;
        
        auto minion = slots[slotIndex];
        slots[slotIndex] = nullptr;
        return minion;
    }
    
    void freeze() { frozen = true; }
    void unfreeze() { frozen = false; }
    void toggleFreeze() { frozen = !frozen; }
    bool isFrozen() const { return frozen; }
    
    void setTavernTier(int tier) { 
        tavernTier = std::min(6, std::max(1, tier)); 
    }
    int getTavernTier() const { return tavernTier; }
    
    int getUpgradeCost() const {
        switch(tavernTier) {
            case 1: return 5;
            case 2: return 7;
            case 3: return 8;
            case 4: return 9;
            case 5: return 10;
            case 6: return 0; // Max tier
            default: return 999;
        }
    }
    
    json toJson() const {
        json slotArray = json::array();
        for (const auto& slot : slots) {
            if (slot) {
                slotArray.push_back(slot->toJson());
            } else {
                slotArray.push_back(nullptr);
            }
        }
        
        return {
            {"slots", slotArray},
            {"frozen", frozen},
            {"tavern_tier", tavernTier},
            {"upgrade_cost", getUpgradeCost()}
        };
    }
};

// Forward declarations
class GameState;
class GameServer;

// ==================== Player Class ====================
class Player {
private:
    std::string token;
    std::string name;
    int gold;
    int health;
    int version;
    bool isZombie;
    bool isReady;
    int playerIndex;
    int wins;
    int losses;
    int damageDealt;
    
    std::shared_ptr<Hero> hero;
    Shop shop;
    PlayerBoard board;
    PlayerHand hand;
    
    // For tracking triples
    std::unordered_map<std::string, int> cardCounts; // cardId -> count
    // For Sylvanas: track minions that died last combat
    std::vector<std::shared_ptr<Minion>> lastCombatDead;
    
public:
    Player(const std::string& t, int idx)
        : token(t), gold(START_GOLD), health(START_HEALTH), version(0), 
          isZombie(false), isReady(false), playerIndex(idx),
          wins(0), losses(0), damageDealt(0) {}
    
    // Getters
    const std::string& getToken() const { return token; }
    const std::string& getName() const { return name; }
    int getGold() const { return gold; }
    int getHealth() const { return health; }
    int getVersion() const { return version; }
    bool zombie() const { return isZombie; }
    bool ready() const { return isReady; }
    int getPlayerIndex() const { return playerIndex; }
    int getWins() const { return wins; }
    int getLosses() const { return losses; }
    int getDamageDealt() const { return damageDealt; }
    
    std::shared_ptr<Hero> getHero() const { return hero; }
    Shop& getShop() { return shop; }
    const Shop& getShop() const { return shop; }
    PlayerBoard& getBoard() { return board; }
    const PlayerBoard& getBoard() const { return board; }
    PlayerHand& getHand() { return hand; }
    const PlayerHand& getHand() const { return hand; }
    std::vector<std::shared_ptr<Minion>>& getLastCombatDead() { return lastCombatDead; }
    
    // Setters
    void setName(const std::string& n) { 
        name = n; 
        version++; 
    }
    
    void setReady(bool r) { 
        isReady = r; 
        version++; 
    }
    
    void markZombie(bool z) { 
        isZombie = z; 
        version++; 
    }
    
    void setHero(std::shared_ptr<Hero> h) { 
        hero = h; 
        version++; 
    }
    
    // Economy
    bool spendGold(int amount) {
        if (gold < amount) return false;
        gold -= amount;
        version++;
        return true;
    }
    
    void gainGold(int amount) {
        gold += amount;
        version++;
    }
    
    void addGold(int amount) {
        gold = std::min(10, gold + amount);
        version++;
    }
    
    void setGold(int amount) {
        gold = std::min(10, amount);
        version++;
    }
    
    // Health
    void takeDamage(int damage) {
        health = std::max(0, health - damage);
        version++;
    }
    
    void heal(int amount) {
        health += amount;
        version++;
    }
    
    bool isDead() const {
        return health <= 0;
    }
    
    // Combat stats
    void addWin() { wins++; version++; }
    void addLoss() { losses++; version++; }
    void addDamageDealt(int damage) { damageDealt += damage; version++; }
    
    // Version management
    void incrementVersion() { version++; }
    
    // Card count tracking for triples
    void trackCard(const std::string& cardId) {
        cardCounts[cardId]++;
    }
    
    void untrackCard(const std::string& cardId) {
        if (cardCounts[cardId] > 0) {
            cardCounts[cardId]--;
        }
    }
    
    int getCardCount(const std::string& cardId) const {
        auto it = cardCounts.find(cardId);
        return it != cardCounts.end() ? it->second : 0;
    }
    
    std::string checkForTriple(const std::string& cardId) {
        if (getCardCount(cardId) >= 3) {
            return cardId;
        }
        return "";
    }
    
    // Minion management
    bool buyMinion(int shopSlot, std::mt19937& rng) {
        auto minion = shop.buySlot(shopSlot);
        if (!minion) return false;
        
        minion->setPlayerIndex(playerIndex);
        
        // Track for triple
        trackCard(minion->getOriginalId());
        
        if (hand.addMinion(minion)) {
            version++;
            
            // Check for triple
            std::string tripleCardId = checkForTriple(minion->getOriginalId());
            if (!tripleCardId.empty()) {
                // This would trigger triple logic (to be handled by GameState)
            }
            
            return true;
        }
        
        // If hand is full, return card to pool
        CardPool::returnCard(minion->getOriginalId());
        untrackCard(minion->getOriginalId());
        return false;
    }
    
    bool sellMinion(const std::string& instanceId) {
        // Check board first
        auto boardMinion = board.getMinion(instanceId);
        if (boardMinion) {
            if (board.removeMinion(instanceId)) {
                CardPool::returnCard(boardMinion->getOriginalId());
                untrackCard(boardMinion->getOriginalId());
                gainGold(1);
                version++;
                return true;
            }
        }
        
        // Check hand
        auto handMinion = hand.getMinion(instanceId);
        if (handMinion) {
            if (hand.removeMinion(instanceId)) {
                CardPool::returnCard(handMinion->getOriginalId());
                untrackCard(handMinion->getOriginalId());
                gainGold(1);
                version++;
                return true;
            }
        }
        
        return false;
    }
    
    bool playMinion(const std::string& instanceId, int boardPosition = -1) {
        auto minion = hand.getMinion(instanceId);
        if (!minion) return false;
        
        if (!board.addMinion(minion)) return false;
        
        hand.removeMinion(instanceId);
        version++;
        return true;
    }
    
    void refreshShop(std::mt19937& rng) {
        // Return current shop cards to pool
        for (auto& slot : shop.getMinionsRef()) {
            if (slot) {
                CardPool::returnCard(slot->getOriginalId());
                untrackCard(slot->getOriginalId());
            }
        }
        
        shop.refresh(rng);
        version++;
    }
    
    bool upgradeTavern() {
        int cost = shop.getUpgradeCost();
        if (cost == 0 || gold < cost) return false;
        
        spendGold(cost);
        shop.setTavernTier(shop.getTavernTier() + 1);
        version++;
        return true;
    }
    
    void startTurn() {
        if (hero) {
            hero->resetTurn();
        }
        addGold(1); // Start of turn gold
        version++;
    }
    
    bool removeTwoInstances(const std::string& cardId) {
        std::vector<std::string> instancesToRemove;
        
        // Search in hand
        const auto& handMinions = hand.getMinions();
        for (const auto& minion : handMinions) {
            if (minion->getOriginalId() == cardId) {
                instancesToRemove.push_back(minion->getInstanceId());
                if (instancesToRemove.size() >= 2) {
                    break;
                }
            }
        }
        
        // If still need more, search in board
        if (instancesToRemove.size() < 2) {
            const auto& boardMinions = board.getMinions();
            for (const auto& minion : boardMinions) {
                if (minion->getOriginalId() == cardId) {
                    instancesToRemove.push_back(minion->getInstanceId());
                    if (instancesToRemove.size() >= 2) {
                        break;
                    }
                }
            }
        }
        
        // Actually remove
        int removed = 0;
        for (const auto& instanceId : instancesToRemove) {
            if (hand.removeMinion(instanceId) || board.removeMinion(instanceId)) {
                CardPool::returnCard(cardId);
                untrackCard(cardId);
                removed++;
            }
        }
        
        return removed >= 2;
    }
    
    json toJson(bool full = false) const {
        json j{
            {"token", token},
            {"name", name},
            {"gold", gold},
            {"health", health},
            {"version", version},
            {"is_zombie", isZombie},
            {"is_ready", isReady},
            {"player_index", playerIndex},
            {"wins", wins},
            {"losses", losses},
            {"damage_dealt", damageDealt}
        };
        
        if (hero) {
            j["hero"] = hero->toJson();
        }
        
        if (full) {
            j["shop"] = shop.toJson();
            j["board"] = board.toJson();
            j["hand"] = hand.toJson();
            j["tavern_tier"] = shop.getTavernTier();
            j["card_counts"] = cardCounts;
        }
        
        return j;
    }
};

// ==================== Combat System ====================
class CombatLog {
public:
    struct Event {
        std::string type;
        std::string attackerId;
        std::string defenderId;
        int damage;
        std::string description;
        int step;
    };
    
private:
    std::vector<Event> events;
    int currentStep = 0;
    uint64_t seed;
    
public:
    CombatLog(uint64_t s) : seed(s) {}
    
    void addEvent(const std::string& type, const std::string& attackerId, 
                  const std::string& defenderId, int damage, const std::string& desc) {
        events.push_back({type, attackerId, defenderId, damage, desc, ++currentStep});
    }
    
    void addEvent(const std::string& type, const std::string& desc) {
        events.push_back({type, "", "", 0, desc, ++currentStep});
    }
    
    json toJson() const {
        json eventArray = json::array();
        for (const auto& event : events) {
            eventArray.push_back({
                {"type", event.type},
                {"step", event.step},
                {"attacker", event.attackerId},
                {"defender", event.defenderId},
                {"damage", event.damage},
                {"description", event.description}
            });
        }
        
        return {
            {"seed", seed},
            {"events", eventArray},
            {"total_steps", currentStep}
        };
    }
};

class CombatSimulator {
private:
    std::shared_ptr<Player> player1;
    std::shared_ptr<Player> player2;
    CombatLog log;
    std::mt19937 rng;
    
public:
    CombatSimulator(std::shared_ptr<Player> p1, std::shared_ptr<Player> p2, uint64_t seed)
        : player1(p1), player2(p2), log(seed), rng(seed) {}
    
    struct Result {
        std::shared_ptr<Player> winner;
        std::shared_ptr<Player> loser;
        int damage;
        CombatLog log;
        std::vector<std::shared_ptr<Minion>> p1Dead;
        std::vector<std::shared_ptr<Minion>> p2Dead;
    };
    
    Result simulate() {
        log.addEvent("COMBAT_START", "Combat between " + player1->getName() + " and " + player2->getName());
        
        // Get minions in attack order (left to right)
        auto p1Minions = player1->getBoard().getMinions();
        auto p2Minions = player2->getBoard().getMinions();
        
        // Determine first attacker (more minions, or random if equal)
        bool p1AttacksFirst = determineFirstAttacker(p1Minions.size(), p2Minions.size());
        
        log.addEvent("FIRST_ATTACKER", p1AttacksFirst ? player1->getName() + " attacks first" : player2->getName() + " attacks first");
        
        // Simple combat simulation (this should be expanded with actual game rules)
        while (!p1Minions.empty() && !p2Minions.empty()) {
            if (p1AttacksFirst) {
                simulateAttack(p1Minions, p2Minions, player1, player2);
            } else {
                simulateAttack(p2Minions, p1Minions, player2, player1);
            }
            
            // Check for dead minions
            p1Minions = player1->getBoard().getMinions();
            p2Minions = player2->getBoard().getMinions();
            
            // Alternate attacker
            p1AttacksFirst = !p1AttacksFirst;
        }
        
        // Determine winner
        Result result;
        result.p1Dead = getDeadMinions(player1, p1Minions);
        result.p2Dead = getDeadMinions(player2, p2Minions);
        
        if (p1Minions.empty() && p2Minions.empty()) {
            // Draw
            result.winner = nullptr;
            result.loser = nullptr;
            result.damage = 0;
            log.addEvent("DRAW", "Combat ended in a draw");
        } else if (p1Minions.empty()) {
            // Player 2 wins
            result.winner = player2;
            result.loser = player1;
            result.damage = calculateDamage(player2);
            log.addEvent("WINNER", player2->getName() + " wins combat");
        } else {
            // Player 1 wins
            result.winner = player1;
            result.loser = player2;
            result.damage = calculateDamage(player1);
            log.addEvent("WINNER", player1->getName() + " wins combat");
        }
        
        result.log = log;
        return result;
    }
    
private:
    bool determineFirstAttacker(size_t p1Count, size_t p2Count) {
        if (p1Count > p2Count) return true;
        if (p2Count > p1Count) return false;
        
        // Equal, random decision
        std::uniform_int_distribution<> dist(0, 1);
        return dist(rng) == 0;
    }
    
    void simulateAttack(std::vector<std::shared_ptr<Minion>>& attackers,
                        std::vector<std::shared_ptr<Minion>>& defenders,
                        std::shared_ptr<Player> attackerPlayer,
                        std::shared_ptr<Player> defenderPlayer) {
        if (attackers.empty() || defenders.empty()) return;
        
        // Simple attack: first attacker attacks first defender
        auto& attacker = attackers[0];
        auto& defender = defenders[0];
        
        log.addEvent("ATTACK", attacker->getInstanceId(), defender->getInstanceId(), 
                     attacker->getAttack(), attacker->getName() + " attacks " + defender->getName());
        
        // Apply damage
        defender->takeDamage(attacker->getAttack());
        
        // Check if defender died
        if (defender->isDead()) {
            log.addEvent("DEATH", defender->getInstanceId(), "", 0, defender->getName() + " dies");
            // Remove from board
            defenderPlayer->getBoard().removeMinion(defender->getInstanceId());
        }
    }
    
    std::vector<std::shared_ptr<Minion>> getDeadMinions(std::shared_ptr<Player> player, 
                                                         const std::vector<std::shared_ptr<Minion>>& currentMinions) {
        std::vector<std::shared_ptr<Minion>> dead;
        // This is simplified - in real implementation, track which minions died during combat
        return dead;
    }
    
    int calculateDamage(std::shared_ptr<Player> winner) {
        // Damage = sum of tiers of alive minions + tavern tier
        int damage = winner->getShop().getTavernTier();
        for (const auto& minion : winner->getBoard().getMinions()) {
            damage += minion->getTier();
        }
        return damage;
    }
};

// ==================== Game State ====================
class GameState {
private:
    GamePhase phase;
    std::unordered_map<std::string, std::shared_ptr<Player>> players;
    std::vector<std::string> playerOrder;
    std::queue<json> actionQueue;
    std::string gameId;
    float phaseTimer;
    float graceTimer;
    bool inGracePeriod;
    int turnNumber;
    
    std::mt19937 rng;
    std::vector<HeroType> availableHeroes;
    std::unordered_map<std::string, std::vector<HeroType>> heroOffers;
    
    mutable std::mutex stateMutex;
    mutable std::mutex actionQueueMutex;
    
    // For tracking game events
    std::vector<CombatSimulator::Result> combatResults;
    std::unordered_map<std::string, std::shared_ptr<websocket::stream<tcp::socket>>> playerSockets;
    
public:
    GameState() 
        : phase(GamePhase::LOBBY), 
          phaseTimer(0),
          graceTimer(0),
          inGracePeriod(false),
          turnNumber(0) {
        gameId = UUIDGenerator::generate();
        
        std::random_device rd;
        rng.seed(rd());
        
        // Initialize available heroes
        availableHeroes = {
            HeroType::SYLVANAS,
            HeroType::LICH_KING,
            HeroType::MILLHOUSE,
            HeroType::YOGG,
            HeroType::PATCHES,
            HeroType::RAGNAROS,
            HeroType::KELTHUZAD,
            HeroType::MALGANIS
        };
        
        std::shuffle(availableHeroes.begin(), availableHeroes.end(), rng);
        
        // Reset card pool
        CardPool::reset();
    }
    
    // Locking
    std::unique_lock<std::mutex> lock() const {
        return std::unique_lock<std::mutex>(stateMutex);
    }
    
    std::unique_lock<std::mutex> lockActionQueue() const {
        return std::unique_lock<std::mutex>(actionQueueMutex);
    }
    
    // Phase management
    GamePhase getPhase() const { 
        auto lock = this->lock();
        return phase; 
    }
    
    void setPhase(GamePhase p) { 
        auto lock = this->lock();
        phase = p; 
        phaseTimer = 0;
        graceTimer = 0;
        inGracePeriod = false;
    }
    
    // Timer management
    float getPhaseTimer() const { 
        auto lock = this->lock();
        return phaseTimer; 
    }
    
    void setPhaseTimer(float timer) { 
        auto lock = this->lock();
        phaseTimer = timer; 
    }
    
    void updatePhaseTimer(float delta) { 
        auto lock = this->lock();
        phaseTimer -= delta; 
    }
    
    float getGraceTimer() const { 
        auto lock = this->lock();
        return graceTimer; 
    }
    
    void setGraceTimer(float timer) { 
        auto lock = this->lock();
        graceTimer = timer; 
    }
    
    void updateGraceTimer(float delta) { 
        auto lock = this->lock();
        graceTimer -= delta; 
    }
    
    bool isInGracePeriod() const { 
        auto lock = this->lock();
        return inGracePeriod; 
    }
    
    void setGracePeriod(bool grace) { 
        auto lock = this->lock();
        inGracePeriod = grace; 
    }
    
    // Player management
    bool addPlayer(const std::string& token, const std::string& name) {
        auto lock = this->lock();
        
        if (players.size() >= MAX_PLAYERS) return false;
        if (players.find(token) != players.end()) return false;
        
        int playerIndex = players.size();
        auto player = std::make_shared<Player>(token, playerIndex);
        player->setName(name);
        
        players[token] = player;
        playerOrder.push_back(token);
        
        return true;
    }
    
    std::shared_ptr<Player> getPlayer(const std::string& token) {
        auto lock = this->lock();
        auto it = players.find(token);
        return (it != players.end()) ? it->second : nullptr;
    }
    
    std::shared_ptr<Player> getPlayerByIndex(int index) {
        auto lock = this->lock();
        if (index < 0 || index >= playerOrder.size()) return nullptr;
        
        auto it = players.find(playerOrder[index]);
        return (it != players.end()) ? it->second : nullptr;
    }
    
    std::vector<std::shared_ptr<Player>> getAllPlayers() const {
        auto lock = this->lock();
        std::vector<std::shared_ptr<Player>> result;
        for (const auto& token : playerOrder) {
            auto it = players.find(token);
            if (it != players.end()) {
                result.push_back(it->second);
            }
        }
        return result;
    }
    
    std::vector<std::shared_ptr<Player>> getAlivePlayers() const {
        auto lock = this->lock();
        std::vector<std::shared_ptr<Player>> result;
        for (const auto& token : playerOrder) {
            auto it = players.find(token);
            if (it != players.end() && !it->second->isDead() && !it->second->zombie()) {
                result.push_back(it->second);
            }
        }
        return result;
    }
    
    size_t getPlayerCount() const {
        auto lock = this->lock();
        return players.size();
    }
    
    size_t getAlivePlayerCount() const {
        auto lock = this->lock();
        size_t count = 0;
        for (const auto& [_, player] : players) {
            if (!player->isDead() && !player->zombie()) {
                count++;
            }
        }
        return count;
    }
    
    size_t getReadyPlayerCount() const {
        auto lock = this->lock();
        size_t count = 0;
        for (const auto& [_, player] : players) {
            if (player->ready()) {
                count++;
            }
        }
        return count;
    }
    
    // Player order
    const std::vector<std::string>& getPlayerOrder() const { 
        auto lock = this->lock();
        return playerOrder; 
    }
    
    // Game info
    std::string getGameId() const { return gameId; }
    int getTurnNumber() const { 
        auto lock = this->lock();
        return turnNumber; 
    }
    
    void incrementTurn() { 
        auto lock = this->lock();
        turnNumber++; 
    }
    
    // Hero selection
    std::vector<HeroType> generateHeroOffer() {
        auto lock = this->lock();
        
        std::vector<HeroType> offer;
        std::vector<HeroType> tempHeroes = availableHeroes;
        
        std::shuffle(tempHeroes.begin(), tempHeroes.end(), rng);
        
        for (int i = 0; i < 3 && i < tempHeroes.size(); i++) {
            offer.push_back(tempHeroes[i]);
        }
        
        return offer;
    }
    
    void assignHeroOffer(const std::string& token, const std::vector<HeroType>& offer) {
        auto lock = this->lock();
        heroOffers[token] = offer;
    }
    
    std::vector<HeroType> getHeroOffer(const std::string& token) const {
        auto lock = this->lock();
        auto it = heroOffers.find(token);
        return (it != heroOffers.end()) ? it->second : std::vector<HeroType>();
    }
    
    bool selectHero(const std::string& token, HeroType heroType) {
        auto lock = this->lock();
        
        auto player = getPlayer(token);
        if (!player) return false;
        
        auto offer = getHeroOffer(token);
        if (std::find(offer.begin(), offer.end(), heroType) == offer.end()) {
            return false;
        }
        
        player->setHero(std::make_shared<Hero>(heroType));
        heroOffers.erase(token);
        
        // Remove hero from available pool
        availableHeroes.erase(
            std::remove(availableHeroes.begin(), availableHeroes.end(), heroType),
            availableHeroes.end()
        );
        
        return true;
    }
    
    bool areAllHeroesSelected() const {
        auto lock = this->lock();
        
        for (const auto& token : playerOrder) {
            auto player = players.at(token);
            if (!player->getHero()) {
                return false;
            }
        }
        
        return true;
    }
    
    // Action queue
    void pushAction(const json& action) {
        auto lock = lockActionQueue();
        actionQueue.push(action);
    }
    
    bool popAction(json& action) {
        auto lock = lockActionQueue();
        if (actionQueue.empty()) return false;
        
        action = actionQueue.front();
        actionQueue.pop();
        return true;
    }
    
    bool hasActions() const {
        auto lock = lockActionQueue();
        return !actionQueue.empty();
    }
    
    // Random number generation
    std::mt19937& getRNG() { return rng; }
    
    // Shop refresh for all players
    void refreshAllShops() {
        auto lock = this->lock();
        
        for (auto& player : getAllPlayers()) {
            if (!player->isDead() && !player->zombie()) {
                player->refreshShop(rng);
            }
        }
    }
    
    // Start turn for all players
    void startTurnForAll() {
        auto lock = this->lock();
        
        for (auto& player : getAllPlayers()) {
            if (!player->isDead() && !player->zombie()) {
                player->startTurn();
            }
        }
    }
    
    // Combat pairing
    std::vector<std::pair<std::string, std::string>> generateCombatPairs() const {
        auto lock = this->lock();
        
        std::vector<std::pair<std::string, std::string>> pairs;
        auto alivePlayers = getAlivePlayers();
        
        if (alivePlayers.size() < 2) return pairs;
        
        // Create a copy and shuffle
        std::vector<std::shared_ptr<Player>> shuffled = alivePlayers;
        std::shuffle(shuffled.begin(), shuffled.end(), const_cast<std::mt19937&>(rng));
        
        // Pair players
        for (size_t i = 0; i + 1 < shuffled.size(); i += 2) {
            pairs.emplace_back(shuffled[i]->getToken(), shuffled[i+1]->getToken());
        }
        
        // If odd number, last player gets a bye (fights a ghost)
        if (shuffled.size() % 2 == 1) {
            pairs.emplace_back(shuffled.back()->getToken(), "");
        }
        
        return pairs;
    }
    
    // Run combat for all pairs
    std::vector<CombatSimulator::Result> runAllCombats() {
        auto lock = this->lock();
        
        std::vector<CombatSimulator::Result> results;
        auto pairs = generateCombatPairs();
        
        for (const auto& [token1, token2] : pairs) {
            auto player1 = getPlayer(token1);
            if (!player1 || player1->isDead()) continue;
            
            if (token2.empty()) {
                // Player gets a bye (no combat)
                CombatSimulator::Result byeResult;
                byeResult.winner = player1;
                byeResult.loser = nullptr;
                byeResult.damage = 0;
                results.push_back(byeResult);
                continue;
            }
            
            auto player2 = getPlayer(token2);
            if (!player2 || player2->isDead()) continue;
            
            // Generate combat seed
            std::uniform_int_distribution<uint64_t> dist;
            uint64_t combatSeed = dist(rng);
            
            CombatSimulator simulator(player1, player2, combatSeed);
            auto result = simulator.simulate();
            results.push_back(result);
            
            // Apply combat results
            if (result.winner && result.loser) {
                result.winner->addWin();
                result.loser->addLoss();
                result.loser->takeDamage(result.damage);
                result.winner->addDamageDealt(result.damage);
            }
        }
        
        combatResults = results;
        return results;
    }
    
    json toJson() const {
        auto lock = this->lock();
        
        json playersJson = json::array();
        for (const auto& player : getAllPlayers()) {
            playersJson.push_back(player->toJson(true));
        }
        
        return {
            {"game_id", gameId},
            {"phase", phaseToString(phase)},
            {"phase_timer", phaseTimer},
            {"grace_timer", graceTimer},
            {"in_grace_period", inGracePeriod},
            {"turn_number", turnNumber},
            {"players", playersJson},
            {"card_pool", CardPool::toJson()}
        };
    }
};

// ==================== Game Server Declaration ====================
class GameServer : public std::enable_shared_from_this<GameServer> {
private:
    net::io_context ioc;
    std::unique_ptr<tcp::acceptor> acceptor;
    
    std::unordered_map<std::string, std::shared_ptr<class Session>> sessions;
    std::mutex sessionsMutex;
    
    std::shared_ptr<GameState> gameState;
    
    std::queue<json> actionQueue;
    std::mutex actionMutex;
    
    std::atomic<bool> running{false};
    std::thread gameLoopThread;
    
public:
    GameServer() 
        : gameState(std::make_shared<GameState>()) {}
    
    ~GameServer() {
        stop();
    }
    
    void run(int port);
    void stop();
    
    void enqueueAction(const json& action);
    
    void addSession(std::shared_ptr<class Session> session);
    void removeSession(const std::string& token);
    
    void broadcast(const json& msg);
    
    void sendToPlayer(const std::string& token, const json& msg);
    
    std::shared_ptr<GameState> getGameState() { return gameState; }
    
private:
    void doAccept();
    void gameLoop();
    void updateGameState(float delta);
    void processActions();
    void handleAction(const json& action);
    
    // Game phase methods
    void updateLobbyPhase(float delta);
    void updateHeroSelectPhase(float delta);
    void updateRecruitPhase(float delta);
    void updateCombatPhase(float delta);
    void updateLogReplayPhase(float delta);

    void enterHeroSelectPhase();
    void enterRecruitPhase();
    void enterCombatPhase();
    void enterLogReplayPhase();
    void enterGameOverPhase();
    
    // Action handlers
    void handleJoin(const json& action);
    void handleReady(const json& action, std::shared_ptr<Player> player);
    void handleSelectHero(const json& action, std::shared_ptr<Player> player);
    void handleBuyMinion(const json& action, std::shared_ptr<Player> player);
    void handleSellMinion(const json& action, std::shared_ptr<Player> player);
    void handlePlayMinion(const json& action, std::shared_ptr<Player> player);
    void handleRefreshShop(const json& action, std::shared_ptr<Player> player);
    void handleUpgradeTavern(const json& action, std::shared_ptr<Player> player);
    void handleFreezeShop(const json& action, std::shared_ptr<Player> player);
    void handleEndTurn(const json& action, std::shared_ptr<Player> player);
    void handleUseHeroPower(const json& action, std::shared_ptr<Player> player);
    void handleReconnect(const json& action);
};

// ==================== Session Class ====================
class Session : public std::enable_shared_from_this<Session> {
private:
    websocket::stream<tcp::socket> ws;
    std::weak_ptr<GameServer> server;
    std::string token;
    std::string playerName;
    
public:
    Session(tcp::socket socket, std::shared_ptr<GameServer> srv)
        : ws(std::move(socket)), server(srv) {}
    
    ~Session();
    
    void run();
    
    void send(const json& msg);
    
    void setToken(const std::string& t) { token = t; }
    std::string getToken() const { return token; }
    void setName(const std::string& name) { playerName = name; }
    std::string getName() const { return playerName; }
    
private:
    void onAccept(beast::error_code ec);
    void doRead();
    void onRead(std::shared_ptr<beast::flat_buffer> buffer, beast::error_code ec, std::size_t);
};

// ==================== GameServer Method Implementations ====================
void GameServer::run(int port) {
    running = true;
    
    tcp::endpoint ep(tcp::v4(), port);
    acceptor = std::make_unique<tcp::acceptor>(ioc, ep);
    
    std::cout << "========================================" << std::endl;
    std::cout << "        🎮 MAW GAME SERVER C++         " << std::endl;
    std::cout << "        Port: " << port << std::endl;
    std::cout << "        Max Players: " << MAX_PLAYERS << std::endl;
    std::cout << "========================================" << std::endl;
    
    doAccept();
    
    gameLoopThread = std::thread(&GameServer::gameLoop, this);
    
    ioc.run();
}

void GameServer::stop() {
    running = false;
    ioc.stop();
    
    if (gameLoopThread.joinable()) {
        gameLoopThread.join();
    }
}

void GameServer::enqueueAction(const json& action) {
    std::lock_guard<std::mutex> lock(actionMutex);
    actionQueue.push(action);
}

void GameServer::addSession(std::shared_ptr<Session> session) {
    std::lock_guard<std::mutex> lock(sessionsMutex);
    sessions[session->getToken()] = session;
    
    std::cout << "🔗 Player connected: " << session->getToken() 
              << " (" << session->getName() << ")" << std::endl;
}

void GameServer::removeSession(const std::string& token) {
    std::lock_guard<std::mutex> lock(sessionsMutex);
    auto it = sessions.find(token);
    if (it != sessions.end()) {
        std::cout << "🔌 Player disconnected: " << token << std::endl;
        sessions.erase(it);
    }
    
    // Mark player as zombie
    if (auto player = gameState->getPlayer(token)) {
        player->markZombie(true);
    }
}

void GameServer::broadcast(const json& msg) {
    std::lock_guard<std::mutex> lock(sessionsMutex);
    for (const auto& [_, session] : sessions) {
        session->send(msg);
    }
}

void GameServer::sendToPlayer(const std::string& token, const json& msg) {
    std::lock_guard<std::mutex> lock(sessionsMutex);
    auto it = sessions.find(token);
    if (it != sessions.end()) {
        it->second->send(msg);
    }
}

void GameServer::doAccept() {
    acceptor->async_accept(
        [self = shared_from_this()](beast::error_code ec, tcp::socket socket) {
            if (!ec) {
                std::make_shared<Session>(std::move(socket), self)->run();
            } else {
                std::cerr << "Accept error: " << ec.message() << std::endl;
            }
            self->doAccept();
        }
    );
}

void GameServer::gameLoop() {
    auto lastTime = high_resolution_clock::now();
    
    while (running) {
        auto currentTime = high_resolution_clock::now();
        float delta = duration_cast<milliseconds>(currentTime - lastTime).count() / 1000.0f;
        lastTime = currentTime;
        
        updateGameState(delta);
        processActions();
        
        std::this_thread::sleep_for(milliseconds(50));
    }
}

void GameServer::updateGameState(float delta) {
    auto phase = gameState->getPhase();
    
    switch (phase) {
        case GamePhase::LOBBY:
            updateLobbyPhase(delta);
            break;
            
        case GamePhase::HERO_SELECT:
            updateHeroSelectPhase(delta);
            break;
            
        case GamePhase::RECRUIT:
            updateRecruitPhase(delta);
            break;
            
        case GamePhase::COMBAT_CALC:
            updateCombatPhase(delta);
            break;
            
        case GamePhase::LOG_REPLAY:
            updateLogReplayPhase(delta);
            break;
            
        case GamePhase::GAME_OVER:
            // Do nothing, game is over
            break;
    }
}

void GameServer::updateLobbyPhase(float delta) {
    // Check if we have enough players and all are ready
    if (gameState->getPlayerCount() == MAX_PLAYERS && 
        gameState->getReadyPlayerCount() == MAX_PLAYERS) {
        
        // Start hero selection
        enterHeroSelectPhase();
    }
}

void GameServer::updateHeroSelectPhase(float delta) {
    gameState->updatePhaseTimer(delta);
    
    if (gameState->getPhaseTimer() <= 0 || gameState->areAllHeroesSelected()) {
        // Start the game
        enterRecruitPhase();
    }
}

void GameServer::updateRecruitPhase(float delta) {
    gameState->updatePhaseTimer(delta);
    
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        gameState->setGracePeriod(true);
        gameState->setGraceTimer(GRACE_PERIOD);
        
        broadcast({
            {"type", "GRACE_PERIOD"},
            {"message", "Grace period started! You have 2 seconds to finish your actions."}
        });
        
        std::cout << "⏰ Grace period started" << std::endl;
    }
    
    if (gameState->isInGracePeriod()) {
        gameState->updateGraceTimer(delta);
        
        if (gameState->getGraceTimer() <= 0) {
            enterCombatPhase();
        }
    }
}

void GameServer::updateCombatPhase(float delta) {
    // Combat is processed immediately, so we move to log replay
    auto results = gameState->runAllCombats();
    
    // Send combat logs to players
    for (const auto& result : results) {
        if (result.winner && result.loser) {
            sendToPlayer(result.winner->getToken(), {
                {"type", "COMBAT_RESULT"},
                {"result", "WIN"},
                {"damage_dealt", result.damage},
                {"log", result.log.toJson()}
            });
            
            sendToPlayer(result.loser->getToken(), {
                {"type", "COMBAT_RESULT"},
                {"result", "LOSE"},
                {"damage_taken", result.damage},
                {"log", result.log.toJson()}
            });
        } else if (result.winner && !result.loser) {
            // Bye (no opponent)
            sendToPlayer(result.winner->getToken(), {
                {"type", "COMBAT_RESULT"},
                {"result", "BYE"},
                {"message", "No opponent this round"}
            });
        }
    }
    
    std::cout << "⚔️ Combat Phase Complete" << std::endl;
    
    // Move to log replay
    enterLogReplayPhase();
}

void GameServer::updateLogReplayPhase(float delta) {
    gameState->updatePhaseTimer(delta);
    
    if (gameState->getPhaseTimer() <= 0) {
        // Check for game over
        if (gameState->getAlivePlayerCount() <= 1) {
            enterGameOverPhase();
        } else {
            // Start next turn
            gameState->incrementTurn();
            enterRecruitPhase();
        }
    }
}

void GameServer::enterHeroSelectPhase() {
    gameState->setPhase(GamePhase::HERO_SELECT);
    gameState->setPhaseTimer(HERO_SELECT_TIME);
    
    // Generate hero offers for each player
    for (const auto& player : gameState->getAllPlayers()) {
        auto offer = gameState->generateHeroOffer();
        gameState->assignHeroOffer(player->getToken(), offer);
        
        // Convert HeroType to string for JSON
        json heroesJson = json::array();
        for (auto heroType : offer) {
            heroesJson.push_back(static_cast<int>(heroType));
        }
        
        sendToPlayer(player->getToken(), {
            {"type", "HERO_OFFER"},
            {"heroes", heroesJson},
            {"time", HERO_SELECT_TIME}
        });
    }
    
    broadcast({
        {"type", "PHASE_CHANGE"},
        {"phase", "HERO_SELECT"},
        {"time", HERO_SELECT_TIME}
    });
    
    std::cout << "🎭 Entered Hero Selection Phase" << std::endl;
}

void GameServer::enterRecruitPhase() {
    gameState->setPhase(GamePhase::RECRUIT);
    gameState->setPhaseTimer(TURN_DURATION);
    gameState->setGracePeriod(false);
    
    // Start turn for all players
    gameState->startTurnForAll();
    
    // Refresh shops for all players
    gameState->refreshAllShops();
    
    // Send full state to all players
    broadcast({
        {"type", "FULL_STATE"},
        {"data", gameState->toJson()}
    });
    
    broadcast({
        {"type", "PHASE_CHANGE"},
        {"phase", "RECRUIT"},
        {"turn", gameState->getTurnNumber()},
        {"time", TURN_DURATION}
    });
    
    std::cout << "🛒 Entered Recruit Phase (Turn " << gameState->getTurnNumber() << ")" << std::endl;
}

void GameServer::enterCombatPhase() {
    gameState->setPhase(GamePhase::COMBAT_CALC);
    
    broadcast({
        {"type", "PHASE_CHANGE"},
        {"phase", "COMBAT_CALC"},
        {"message", "Combat calculation in progress..."}
    });
    
    std::cout << "⚔️ Entered Combat Calculation Phase" << std::endl;
}

void GameServer::enterLogReplayPhase() {
    gameState->setPhase(GamePhase::LOG_REPLAY);
    gameState->setPhaseTimer(COMBAT_LOG_TIME);
    
    broadcast({
        {"type", "PHASE_CHANGE"},
        {"phase", "LOG_REPLAY"},
        {"time", COMBAT_LOG_TIME}
    });
    
    std::cout << "📜 Entered Log Replay Phase" << std::endl;
}

void GameServer::enterGameOverPhase() {
    gameState->setPhase(GamePhase::GAME_OVER);
    
    // Find winner
    std::shared_ptr<Player> winner = nullptr;
    for (const auto& player : gameState->getAlivePlayers()) {
        winner = player;
        break;
    }
    
    json playersJson = json::array();
    for (const auto& player : gameState->getAllPlayers()) {
        playersJson.push_back({
            {"name", player->getName()},
            {"health", player->getHealth()},
            {"wins", player->getWins()},
            {"losses", player->getLosses()},
            {"damage_dealt", player->getDamageDealt()},
            {"hero", player->getHero() ? player->getHero()->getName() : "None"}
        });
    }
    
    broadcast({
        {"type", "GAME_OVER"},
        {"winner", winner ? winner->getName() : "None"},
        {"winner_hero", winner && winner->getHero() ? winner->getHero()->getName() : "None"},
        {"players", playersJson}
    });
    
    std::cout << "🏆 Game Over! Winner: " 
              << (winner ? winner->getName() : "None") << std::endl;
}

void GameServer::processActions() {
    json action;
    while (true) {
        {
            std::lock_guard<std::mutex> lock(actionMutex);
            if (actionQueue.empty()) break;
            action = actionQueue.front();
            actionQueue.pop();
        }
        
        handleAction(action);
    }
}

void GameServer::handleAction(const json& action) {
    try {
        std::string type = action.value("type", "");
        std::string token = action.value("token", "");
        
        if (token.empty()) {
            std::cerr << "⚠️ Action without token: " << type << std::endl;
            return;
        }
        
        auto player = gameState->getPlayer(token);
        
        if (type == "JOIN") {
            handleJoin(action);
        } else if (type == "RECONNECT") {
            handleReconnect(action);
        } else if (!player) {
            sendToPlayer(token, {
                {"type", "ERROR"},
                {"message", "Player not found. Please reconnect."}
            });
            return;
        } else if (type == "READY") {
            handleReady(action, player);
        } else if (type == "SELECT_HERO") {
            handleSelectHero(action, player);
        } else if (type == "BUY_MINION") {
            handleBuyMinion(action, player);
        } else if (type == "SELL_MINION") {
            handleSellMinion(action, player);
        } else if (type == "PLAY_MINION") {
            handlePlayMinion(action, player);
        } else if (type == "REFRESH_SHOP") {
            handleRefreshShop(action, player);
        } else if (type == "UPGRADE_TAVERN") {
            handleUpgradeTavern(action, player);
        } else if (type == "FREEZE_SHOP") {
            handleFreezeShop(action, player);
        } else if (type == "END_TURN") {
            handleEndTurn(action, player);
        } else if (type == "USE_HERO_POWER") {
            handleUseHeroPower(action, player);
        } else if (type == "PING") {
            // Just acknowledge ping
            sendToPlayer(token, {{"type", "PONG"}});
        } else {
            sendToPlayer(token, {
                {"type", "ERROR"},
                {"message", "Unknown action type: " + type}
            });
            std::cerr << "⚠️ Unknown action type: " << type << " from " << token << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "💥 Error handling action: " << e.what() << std::endl;
    }
}

void GameServer::handleJoin(const json& action) {
    std::string token = action["token"];
    std::string name = action.value("name", "Player");
    
    // Check if game is in lobby
    if (gameState->getPhase() != GamePhase::LOBBY) {
        sendToPlayer(token, {
            {"type", "ERROR"},
            {"message", "Game already in progress. Please wait for next game."}
        });
        return;
    }
    
    // Check if max players reached
    if (gameState->getPlayerCount() >= MAX_PLAYERS) {
        sendToPlayer(token, {
            {"type", "ERROR"},
            {"message", "Game is full (max " + std::to_string(MAX_PLAYERS) + " players)"}
        });
        return;
    }
    
    // Add player
    if (gameState->addPlayer(token, name)) {
        // Send player info
        sendToPlayer(token, {
            {"type", "JOIN_SUCCESS"},
            {"token", token},
            {"name", name},
            {"player_count", (int)gameState->getPlayerCount()},
            {"max_players", MAX_PLAYERS}
        });
        
        // Broadcast to all players
        broadcast({
            {"type", "PLAYER_JOINED"},
            {"name", name},
            {"player_count", (int)gameState->getPlayerCount()}
        });
        
        std::cout << "👤 Player joined: " << name << " (" << token << ")" << std::endl;
    } else {
        sendToPlayer(token, {
            {"type", "ERROR"},
            {"message", "Failed to join game"}
        });
    }
}

void GameServer::handleReconnect(const json& action) {
    std::string token = action["token"];
    std::string name = action.value("name", "");
    
    auto player = gameState->getPlayer(token);
    if (!player) {
        // Player doesn't exist, treat as new join
        handleJoin(action);
        return;
    }
    
    // Update name if provided
    if (!name.empty() && name != player->getName()) {
        player->setName(name);
    }
    
    // Remove zombie status
    player->markZombie(false);
    
    // Send full state
    sendToPlayer(token, {
        {"type", "RECONNECT_SUCCESS"},
        {"full_state", gameState->toJson()},
        {"player_state", player->toJson(true)}
    });
    
    std::cout << "🔁 Player reconnected: " << player->getName() << " (" << token << ")" << std::endl;
}

void GameServer::handleReady(const json& action, std::shared_ptr<Player> player) {
    bool ready = action.value("ready", true);
    player->setReady(ready);
    
    broadcast({
        {"type", "PLAYER_READY"},
        {"name", player->getName()},
        {"ready", ready}
    });
    
    std::cout << "✅ Player ready: " << player->getName() 
              << " (ready: " << ready << ")" << std::endl;
}

void GameServer::handleSelectHero(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::HERO_SELECT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in hero selection phase"}
        });
        return;
    }
    
    int heroTypeInt = action.value("hero", -1);
    if (heroTypeInt < 0 || heroTypeInt >= 8) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Invalid hero selection"}
        });
        return;
    }
    
    HeroType heroType = static_cast<HeroType>(heroTypeInt);
    
    if (gameState->selectHero(player->getToken(), heroType)) {
        sendToPlayer(player->getToken(), {
            {"type", "HERO_SELECTED"},
            {"hero", heroTypeInt}
        });
        
        broadcast({
            {"type", "PLAYER_HERO_SELECTED"},
            {"name", player->getName()},
            {"hero", heroTypeInt}
        });
        
        std::cout << "🎭 Player selected hero: " << player->getName() 
                  << " -> " << static_cast<int>(heroType) << std::endl;
    } else {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Hero not available or already selected"}
        });
    }
}

void GameServer::handleBuyMinion(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    int slot = action.value("slot", -1);
    if (slot < 0 || slot >= SHOP_SIZE) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Invalid slot: " + std::to_string(slot)}
        });
        return;
    }
    
    // Check cost based on hero
    int minionCost = 3;
    if (player->getHero() && player->getHero()->getType() == HeroType::MILLHOUSE) {
        minionCost = 2;
    }
    
    if (player->getGold() < minionCost) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not enough gold. Need " + std::to_string(minionCost) + ", have " + std::to_string(player->getGold())}
        });
        return;
    }
    
    if (player->getHand().isFull()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Hand is full (max " + std::to_string(MAX_HAND_SIZE) + " cards)"}
        });
        return;
    }
    
    if (player->buyMinion(slot, gameState->getRNG())) {
        player->spendGold(minionCost);
        
        // Check for triple
        std::string tripleCardId = ""; // This should check for triple
        // TODO: Implement triple logic
        
        // Send update to player
        json response = {
            {"type", "BUY_SUCCESS"},
            {"slot", slot},
            {"gold", player->getGold()},
            {"hand", player->getHand().toJson()},
            {"shop", player->getShop().toJson()}
        };
        
        if (!tripleCardId.empty()) {
            response["triple"] = tripleCardId;
        }
        
        sendToPlayer(player->getToken(), response);
        
        std::cout << "🛒 " << player->getName() << " bought minion from slot " << slot 
                  << " (gold: " << player->getGold() << ")" << std::endl;
    } else {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Failed to buy minion (slot empty or card not available)"}
        });
    }
}

void GameServer::handleSellMinion(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    std::string instanceId = action.value("instance_id", "");
    if (instanceId.empty()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "No instance ID provided"}
        });
        return;
    }
    
    if (player->sellMinion(instanceId)) {
        sendToPlayer(player->getToken(), {
            {"type", "SELL_SUCCESS"},
            {"instance_id", instanceId},
            {"gold", player->getGold()},
            {"board", player->getBoard().toJson()},
            {"hand", player->getHand().toJson()}
        });
        
        std::cout << "💰 " << player->getName() << " sold minion " 
                  << instanceId << " (gold: " << player->getGold() << ")" << std::endl;
    } else {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Minion not found in hand or board"}
        });
    }
}

void GameServer::handlePlayMinion(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    std::string instanceId = action.value("instance_id", "");
    if (instanceId.empty()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "No instance ID provided"}
        });
        return;
    }
    
    int position = action.value("position", -1);
    
    if (player->playMinion(instanceId, position)) {
        sendToPlayer(player->getToken(), {
            {"type", "PLAY_SUCCESS"},
            {"instance_id", instanceId},
            {"board", player->getBoard().toJson()},
            {"hand", player->getHand().toJson()}
        });
        
        std::cout << "🎮 " << player->getName() << " played minion " 
                  << instanceId << " (board size: " << player->getBoard().size() << ")" << std::endl;
    } else {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Failed to play minion (board full or minion not found in hand)"}
        });
    }
}

void GameServer::handleRefreshShop(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    // Check cost based on hero
    int refreshCost = 1;
    if (player->getHero() && player->getHero()->getType() == HeroType::MILLHOUSE) {
        refreshCost = 2;
    }
    
    if (player->getGold() < refreshCost) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not enough gold for refresh. Need " + std::to_string(refreshCost)}
        });
        return;
    }
    
    player->spendGold(refreshCost);
    player->refreshShop(gameState->getRNG());
    
    sendToPlayer(player->getToken(), {
        {"type", "REFRESH_SUCCESS"},
        {"gold", player->getGold()},
        {"shop", player->getShop().toJson()}
    });
    
    std::cout << "🔄 " << player->getName() << " refreshed shop" 
              << " (gold: " << player->getGold() << ")" << std::endl;
}

void GameServer::handleUpgradeTavern(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    if (player->upgradeTavern()) {
        sendToPlayer(player->getToken(), {
            {"type", "UPGRADE_SUCCESS"},
            {"gold", player->getGold()},
            {"tavern_tier", player->getShop().getTavernTier()},
            {"shop", player->getShop().toJson()}
        });
        
        std::cout << "📈 " << player->getName() << " upgraded tavern to tier " 
                  << player->getShop().getTavernTier() 
                  << " (gold: " << player->getGold() << ")" << std::endl;
    } else {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Cannot upgrade tavern (not enough gold or already at max tier)"}
        });
    }
}

void GameServer::handleFreezeShop(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    player->getShop().toggleFreeze();
    
    sendToPlayer(player->getToken(), {
        {"type", "FREEZE_SUCCESS"},
        {"frozen", player->getShop().isFrozen()},
        {"shop", player->getShop().toJson()}
    });
    
    std::cout << "❄️ " << player->getName() << " toggled freeze" 
              << " (frozen: " << player->getShop().isFrozen() << ")" << std::endl;
}

void GameServer::handleEndTurn(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Player ends their turn early
    sendToPlayer(player->getToken(), {
        {"type", "TURN_ENDED"},
        {"message", "Turn ended successfully"}
    });
    
    std::cout << "⏹️ " << player->getName() << " ended turn early" << std::endl;
}

void GameServer::handleUseHeroPower(const json& action, std::shared_ptr<Player> player) {
    if (gameState->getPhase() != GamePhase::RECRUIT) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Not in recruit phase"}
        });
        return;
    }
    
    // Check if in grace period
    if (gameState->getPhaseTimer() <= 0 && !gameState->isInGracePeriod()) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Recruit phase has ended"}
        });
        return;
    }
    
    auto hero = player->getHero();
    if (!hero) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "No hero selected"}
        });
        return;
    }
    
    if (!hero->canUsePower(player->getGold())) {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Cannot use hero power (not enough gold or already used this turn)"}
        });
        return;
    }
    
    // Handle different hero powers
    HeroType heroType = hero->getType();
    bool success = false;
    
    switch (heroType) {
        case HeroType::SYLVANAS: {
            // Give +2/+1 to minions that died last combat
            auto& deadMinions = player->getLastCombatDead();
            for (auto& minion : deadMinions) {
                minion->buff(2, 1);
            }
            success = !deadMinions.empty();
            break;
        }
        case HeroType::YOGG: {
            // Add a random minion from current Tavern Tier to hand
            int tier = player->getShop().getTavernTier();
            auto availableCards = CardPool::getAvailableCardsByTier(tier);
            if (!availableCards.empty()) {
                std::uniform_int_distribution<> dist(0, availableCards.size() - 1);
                std::string cardId = availableCards[dist(gameState->getRNG())];
                
                if (CardPool::takeCard(cardId)) {
                    auto minion = std::make_shared<Minion>(CardDatabase::getMinion(cardId));
                    minion->setPlayerIndex(player->getPlayerIndex());
                    player->trackCard(cardId);
                    
                    if (player->getHand().addMinion(minion)) {
                        success = true;
                    } else {
                        CardPool::returnCard(cardId);
                        player->untrackCard(cardId);
                    }
                }
            }
            break;
        }
        default:
            // For other heroes, just mark as used
            success = true;
            break;
    }
    
    if (success) {
        // Use hero power
        player->spendGold(hero->getPowerCost());
        hero->markUsed();
        
        sendToPlayer(player->getToken(), {
            {"type", "HERO_POWER_USED"},
            {"gold", player->getGold()},
            {"hero", hero->toJson()}
        });
        
        std::cout << "✨ " << player->getName() << " used hero power: " 
                  << hero->getName() << std::endl;
    } else {
        sendToPlayer(player->getToken(), {
            {"type", "ERROR"},
            {"message", "Failed to use hero power"}
        });
    }
}

// ==================== Session Method Implementations ====================
Session::~Session() {
    if (!token.empty()) {
        if (auto srv = server.lock()) {
            srv->removeSession(token);
        }
    }
}

void Session::run() {
    ws.async_accept(
        beast::bind_front_handler(
            &Session::onAccept,
            shared_from_this()
        )
    );
}

void Session::send(const json& msg) {
    try {
        auto msgStr = msg.dump();
        ws.async_write(
            net::buffer(msgStr),
            [self = shared_from_this(), msgStr](beast::error_code ec, std::size_t) {
                if (ec) {
                    std::cerr << "📤 Send error to " << self->getToken() 
                              << ": " << ec.message() << std::endl;
                }
            }
        );
    } catch (const std::exception& e) {
        std::cerr << "💥 Error sending message to " << token 
                  << ": " << e.what() << std::endl;
    }
}

void Session::onAccept(beast::error_code ec) {
    if (ec) {
        std::cerr << "🤝 Accept error: " << ec.message() << std::endl;
        return;
    }
    
    // Generate token for this session
    token = UUIDGenerator::generate();
    
    // Register with server
    if (auto srv = server.lock()) {
        srv->addSession(shared_from_this());
    }
    
    // Send welcome message
    send({
        {"type", "WELCOME"},
        {"token", token},
        {"max_players", MAX_PLAYERS},
        {"message", "Welcome to MAW Game Server! Use your token to reconnect if disconnected."}
    });
    
    doRead();
}

void Session::doRead() {
    auto buffer = std::make_shared<beast::flat_buffer>();
    
    ws.async_read(
        *buffer,
        beast::bind_front_handler(
            &Session::onRead,
            shared_from_this(),
            buffer
        )
    );
}

void Session::onRead(std::shared_ptr<beast::flat_buffer> buffer, beast::error_code ec, std::size_t) {
    if (ec == websocket::error::closed) {
        // Normal closure
        return;
    }
    
    if (ec) {
        std::cerr << "📥 Read error from " << token << ": " << ec.message() << std::endl;
        return;
    }
    
    try {
        std::string msg = beast::buffers_to_string(buffer->data());
        json data = json::parse(msg);
        data["token"] = token;
        
        if (auto srv = server.lock()) {
            srv->enqueueAction(data);
        }
    } catch (const std::exception& e) {
        send({
            {"type", "ERROR"},
            {"message", "Invalid JSON: " + std::string(e.what())}
        });
        std::cerr << "❌ Invalid JSON from " << token << ": " << e.what() << std::endl;
    }
    
    doRead();
}

// ==================== Main Function ====================
int main() {
    try {
        std::cout << "========================================" << std::endl;
        std::cout << "        🚀 Starting MAW Server         " << std::endl;
        std::cout << "========================================" << std::endl;
        
        auto server = std::make_shared<GameServer>();
        server->run(PORT);
        
        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "💥 Fatal error: " << e.what() << std::endl;
        return 1;
    }
}