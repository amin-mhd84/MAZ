#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <queue>
#include <memory>
#include <thread>
#include <mutex>
#include <atomic>
#include <chrono>
#include <random>
#include <sstream>
#include <iomanip>



#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <boost/beast/websocket.hpp>
#include <nlohmann/json.hpp>


#include "json.hpp"
class Session;
class GameServer;

namespace beast = boost::beast;
namespace http = beast::http;
namespace websocket = beast::websocket;
namespace net = boost::asio;
using tcp = boost::asio::ip::tcp;
using json = nlohmann::json;
using namespace std::chrono;

// ==================== Constants & Enums ====================
const int PORT = 8888;
const int MAX_PLAYERS = 4;
const int START_GOLD = 3;
const int SHOP_SIZE = 5;
const float TURN_DURATION = 30.0f;
const float GRACE_PERIOD = 2.0f;

enum class GamePhase {
    LOBBY,
    HERO_SELECT,
    RECRUIT,
    COMBAT_CALC,
    LOG_REPLAY,
    GAME_OVER
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


#pragma once
#include <string>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

enum class HeroType {
    SYLVANAS,
    LICH_KING,
    MILLHOUSE,
    YOGG
};

class Hero {
private:
    HeroType type;
    std::string name;
    int powerCost;
    bool powerUsedThisTurn = false;

public:
    Hero(HeroType t) : type(t) {
        switch(t) {
            case HeroType::SYLVANAS:
                name = "Sylvanas Windrunner";
                powerCost = 1;
                break;
            case HeroType::LICH_KING:
                name = "The Lich King";
                powerCost = 1;
                break;
            case HeroType::MILLHOUSE:
                name = "Millhouse Manastorm";
                powerCost = 0;   // passive
                break;
            case HeroType::YOGG:
                name = "Yogg-Saron";
                powerCost = 2;
                break;
        }
    }

    HeroType getType() const { return type; }
    std::string getName() const { return name; }
    int getPowerCost() const { return powerCost; }

    void resetTurn() {
        powerUsedThisTurn = false;
    }

    bool canUsePower() const {
        return !powerUsedThisTurn && powerCost > 0;
    }

    void markUsed() {
        powerUsedThisTurn = true;
    }

    json toJson() const {
        return {
            {"name", name},
            {"power_cost", powerCost}
        };
    }
};



#pragma once
#include <algorithm>

class TavernEconomy {
private:
    int tavernLevel = 1;
    int upgradeCost = 5;
    int minCost = 2;

public:
    int getLevel() const { return tavernLevel; }
    int getUpgradeCost() const { return upgradeCost; }

    void onTurnStart(int& gold) {
        gold = std::min(10, gold + 1);
        if (upgradeCost > minCost)
            upgradeCost--;
    }

    bool tryUpgrade(int& gold) {
        if (gold < upgradeCost) return false;

        gold -= upgradeCost;
        tavernLevel++;

        switch(tavernLevel) {
            case 2: upgradeCost = 7; minCost = 4; break;
            case 3: upgradeCost = 8; minCost = 5; break;
            case 4: upgradeCost = 9; minCost = 6; break;
            default: break;
        }

        return true;
    }
};



#pragma once
#include <vector>
#include <string>
#include <random>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

class ShopState {
private:
    int tavernLevel = 1;
    bool frozen = false;
    std::vector<std::string> slots;

public:
    ShopState() {}

    void setLevel(int lvl) { tavernLevel = lvl; }

    bool isFrozen() const { return frozen; }

    void toggleFreeze() {
        frozen = !frozen;
    }

    const std::vector<std::string>& getSlots() const {
        return slots;
    }


    void roll(const std::vector<std::string>& pool, std::mt19937& rng) {
        if (frozen) return;

        slots.clear();

        int size = (tavernLevel == 1 ? 3 :
                    tavernLevel == 2 ? 4 :
                    tavernLevel >= 4 ? 5 : 4);

        std::uniform_int_distribution<> d(0, (int)pool.size()-1);

        for (int i=0;i<size;i++)
            slots.push_back(pool[d(rng)]);
    }

    void clearSlot(int idx) {
        if (idx>=0 && idx<slots.size())
            slots[idx] = "";
    }

    json toJson() const {
        return {
            {"level", tavernLevel},
            {"frozen", frozen},
            {"slots", slots}
        };
    }
};




#pragma once
#include <memory>
#include "Hero.hpp"
#include "TavernEconomy.hpp"
#include "ShopState.hpp"

class PlayerExtended {
public:
    std::shared_ptr<Player> base;     
    std::shared_ptr<Hero> hero;
    TavernEconomy economy;
    ShopState shop;

    PlayerExtended(std::shared_ptr<Player> p)
        : base(p) {}

    void assignHero(HeroType h) {
        hero = std::make_shared<Hero>(h);
    }

    void onTurnStart() {
        int g = base->getGold();
        economy.onTurnStart(g);
        base->gainGold(0);
    }
};





#pragma once
#include <nlohmann/json.hpp>
using json = nlohmann::json;

class GameProtocol {
public:

    static json welcome(const std::string& token) {
        return {
            {"type","WELCOME"},
            {"token", token}
        };
    }

    static json fullState(const GameState& gs) {
        json players = json::array();

        for (auto p : gs.getAllPlayers())
            players.push_back(p->toJson(true));

        return {
            {"type","FULL_STATE"},
            {"phase", phaseToString(gs.getPhase())},
            {"players", players}
        };
    }

    static json heroOffer(const std::vector<HeroType>& hs) {
        json a = json::array();
        for (auto h : hs)
            a.push_back((int)h);

        return {
            {"type","HERO_OFFER"},
            {"heroes", a}
        };
    }

    static json shopUpdate(const PlayerExtended& px) {
        return {
            {"type","SHOP_UPDATE"},
            {"shop", px.shop.toJson()},
            {"gold", px.base->getGold()}
        };
    }
};

// ==================== UUID Generator ====================
class UUIDGenerator {
public:
    static std::string generate() {
        static std::random_device rd;
        static std::mt19937 gen(rd());
        static std::uniform_int_distribution<> dis(0, 15);
        static std::uniform_int_distribution<> dis2(8, 11);
        
        std::stringstream ss;
        ss << std::hex;
        
        for (int i = 0; i < 8; i++) ss << dis(gen);
        ss << "-";
        for (int i = 0; i < 4; i++) ss << dis(gen);
        ss << "-4";
        for (int i = 0; i < 3; i++) ss << dis(gen);
        ss << "-";
        ss << dis2(gen);
        for (int i = 0; i < 3; i++) ss << dis(gen);
        ss << "-";
        for (int i = 0; i < 12; i++) ss << dis(gen);
        
        return ss.str();
    }
};

// ==================== Card Class ====================
class Card {
private:
    std::string cardId;
    std::string name;
    int cost;
    std::string instanceId;
    
public:
    Card(const std::string& id, const std::string& n, int c)
        : cardId(id), name(n), cost(c), instanceId(UUIDGenerator::generate()) {}
    
    std::string getCardId() const { return cardId; }
    std::string getName() const { return name; }
    int getCost() const { return cost; }
    std::string getInstanceId() const { return instanceId; }
    
    json toJson() const {
        return {
            {"card_id", cardId},
            {"name", name},
            {"cost", cost},
            {"instance_id", instanceId}
        };
    }
};

// ==================== Player Class ====================

class Player {
private:
    std::string token;
    std::string name;
    int gold;
    int version;
    bool isZombie;

    std::vector<std::shared_ptr<Card>> hand;
    std::vector<std::string> shop;

public:
    Player(const std::string& t)
        : token(t), gold(START_GOLD), version(0), isZombie(false) {}

    // --- getters ---
    const std::string& getToken() const { return token; }
    const std::string& getName() const { return name; }
    int getGold() const { return gold; }
    int getVersion() const { return version; }
    bool zombie() const { return isZombie; }

    // --- setters ---
    void setName(const std::string& n) { name = n; }
    void markZombie(bool z) { isZombie = z; }

    // --- economy ---
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

    void addToHand(std::shared_ptr<Card> card) {
        hand.push_back(card);
        version++;
    }

    bool removeFromHand(const std::string& instanceId, std::string& outCardId) {
        for (auto it = hand.begin(); it != hand.end(); ++it) {
            if ((*it)->getInstanceId() == instanceId) {
                outCardId = (*it)->getCardId();
                hand.erase(it);
                version++;
                return true;
            }
        }
        return false;
    }


    void setShop(const std::vector<std::string>& cards) {
        shop = cards;
        version++;
    }

    std::string getShopCard(int index) const {
        if (index < 0 || index >= (int)shop.size()) return "";
        return shop[index];
    }

    void removeShopCard(int index) {
        if (index < 0 || index >= (int)shop.size()) return;
        shop[index] = "";
        version++;
    }


    json toJson(bool full = false) const {
        json j{
            {"token", token},
            {"name", name},
            {"gold", gold},
            {"version", version},
            {"is_zombie", isZombie}
        };

        if (full) {
            json handJson = json::array();
            for (auto& c : hand)
                handJson.push_back(c->toJson());

            j["hand"] = handJson;
            j["shop"] = shop;
        }

        return j;
    }
};



// ==================== Game State ====================
class GameState {
private:
    GamePhase phase;
    std::unordered_map<std::string, std::shared_ptr<Player>> players;
    std::unordered_map<std::string, int> cardPool;
    std::queue<json> actionQueue;
    std::string gameId;
    float turnTimer;
    long long turnStartTime;
    std::mutex stateMutex;
    
    void initializeCardPool() {

        cardPool = {
            {"BG_001", 10},  
            {"BG_002", 10},  
            {"BG_003", 10},
            {"BG_004", 10},
            {"BG_005", 10},
            {"BG_006", 10},
            {"BG_007", 10},
        };
    }
    
public:
    GameState() : phase(GamePhase::LOBBY), turnTimer(0), turnStartTime(0) {
        gameId = UUIDGenerator::generate();
        initializeCardPool();
    }
    
    std::unique_lock<std::mutex> lock() {
        return std::unique_lock<std::mutex>(stateMutex);
    }
    

    GamePhase getPhase() const { return phase; }
    void setPhase(GamePhase p) { phase = p; }
    
    // Player management
    bool addPlayer(const std::string& token, std::shared_ptr<Player> player) {
        auto lock = this->lock();
        if (players.size() >= MAX_PLAYERS) return false;
        
        players[token] = player;
        return true;
    }
    
    std::shared_ptr<Player> getPlayer(const std::string& token) {
        auto lock = this->lock();
        auto it = players.find(token);
        return (it != players.end()) ? it->second : nullptr;
    }
    
    std::vector<std::shared_ptr<Player>> getAllPlayers() {
        auto lock = this->lock();
        std::vector<std::shared_ptr<Player>> result;
        for (const auto& [_, player] : players) {
            result.push_back(player);
        }
        return result;
    }
    
    size_t getPlayerCount() const {
        return players.size();
    }
    
    // Card pool management
    bool takeCardFromPool(const std::string& cardId) {
        auto lock = this->lock();
        auto it = cardPool.find(cardId);
        if (it != cardPool.end() && it->second > 0) {
            it->second--;
            return true;
        }
        return false;
    }
    
    void returnCardToPool(const std::string& cardId) {
        auto lock = this->lock();
        cardPool[cardId]++;
    }
    
    std::vector<std::string> getAvailableCards() {
        auto lock = this->lock();
        std::vector<std::string> result;
        for (const auto& [cardId, count] : cardPool) {
            if (count > 0) result.push_back(cardId);
        }
        return result;
    }
    
    // Action queue
    void pushAction(const json& action) {
        auto lock = this->lock();
        actionQueue.push(action);
    }
    
    bool popAction(json& action) {
        auto lock = this->lock();
        if (actionQueue.empty()) return false;
        
        action = actionQueue.front();
        actionQueue.pop();
        return true;
    }
    
    bool hasActions() {
        auto lock = this->lock();
        return !actionQueue.empty();
    }
    
    // Timer management
    void setTurnTimer(float timer) { turnTimer = timer; }
    float getTurnTimer() const { return turnTimer; }
    void updateTurnTimer(float delta) { turnTimer -= delta; }
    
    void setTurnStartTime(long long time) { turnStartTime = time; }
    long long getTurnStartTime() const { return turnStartTime; }
    
    std::string getGameId() const { return gameId; }
};


class Session : public std::enable_shared_from_this<Session> {
private:
    websocket::stream<tcp::socket> ws;
    GameServer* server;
    std::string token;

public:
    Session(tcp::socket socket, GameServer* srv);
    ~Session();

    void run();
    void send(const json& msg);

private:
    void onAccept();
    void doRead();
    void onRead(const std::string& msg);
};



// ==================== Game Server ====================
class GameServer {
private:
    net::io_context ioc;
    std::unique_ptr<tcp::acceptor> acceptor;

    std::unordered_map<std::string, std::weak_ptr<Session>> sessions;
    std::mutex sessionsMutex;

    std::shared_ptr<GameState> gameState;

    std::queue<json> actionQueue;
    std::mutex actionMutex;

    std::atomic<bool> running{false};
    std::thread gameLoopThread;

    float phaseTimer = 0.f;
    float graceTimer = 0.f;
    bool inGrace = false;

    uint32_t combatSeed = 0;
    int combatRound = 0;
    std::mt19937 combatRng;

public:
    GameServer() {
        gameState = std::make_shared<GameState>();
    }

    ~GameServer() {
        stop();
    }

    void run(int port) {
        running = true;
        tcp::endpoint ep(tcp::v4(), port);
        acceptor = std::make_unique<tcp::acceptor>(ioc, ep);

        doAccept();
        gameLoopThread = std::thread(&GameServer::gameLoop, this);
        ioc.run();
    }

    void stop() {
        running = false;
        ioc.stop();
        if (gameLoopThread.joinable())
            gameLoopThread.join();
    }

private:
    void doAccept() {
        acceptor->async_accept(
            [this](boost::system::error_code ec, tcp::socket socket) {
                if (!ec)
                    std::make_shared<Session>(std::move(socket), this)->run();
                doAccept();
            }
        );
    }

    void gameLoop() {
        auto last = high_resolution_clock::now();

        while (running) {
            auto now = high_resolution_clock::now();
            float delta =
                duration_cast<milliseconds>(now - last).count() / 1000.f;
            last = now;

            // ❗ GAME OVER = stop advancing game state
            if (gameState->getPhase() != GamePhase::GAME_OVER) {
                updatePhase(delta);
                processActions();
            }

            std::this_thread::sleep_for(milliseconds(50));
        }
    }

    void processActions() {
        json action;
        while (true) {
            {
                std::lock_guard<std::mutex> lock(actionMutex);
                if (actionQueue.empty())
                    break;
                action = actionQueue.front();
                actionQueue.pop();
            }
            handleAction(action);
        }
    }

public:
    void enqueueAction(const json& action) {
        std::lock_guard<std::mutex> lock(actionMutex);
        actionQueue.push(action);
    }

    void addSession(const std::string& token, std::shared_ptr<Session> session) {
        std::lock_guard<std::mutex> lock(sessionsMutex);
        sessions.erase(token);
        sessions[token] = session;
    }

    void removeSession(const std::string& token) {
        {
            std::lock_guard<std::mutex> lock(sessionsMutex);
            sessions.erase(token);
        }
        if (auto p = gameState->getPlayer(token))
            p->markZombie(true);
    }

private:
    void updatePhase(float delta) {
        switch (gameState->getPhase()) {

        case GamePhase::LOBBY:
            if (gameState->getPlayerCount() == MAX_PLAYERS)
                enterHeroSelect();
            break;

        case GamePhase::HERO_SELECT:
            phaseTimer -= delta;
            if (phaseTimer <= 0)
                enterRecruit();
            break;

        case GamePhase::RECRUIT:
            phaseTimer -= delta;
            if (phaseTimer <= 0 && !inGrace) {
                inGrace = true;
                graceTimer = GRACE_PERIOD;
            }
            if (inGrace) {
                graceTimer -= delta;
                if (graceTimer <= 0)
                    enterCombat();
            }
            break;

        case GamePhase::COMBAT_CALC:
            break;

        case GamePhase::LOG_REPLAY:
            phaseTimer -= delta;
            if (phaseTimer <= 0)
                enterRecruit();
            break;

        case GamePhase::GAME_OVER:
            // terminal state
            break;
        }
    }

    void enterHeroSelect() {
        gameState->setPhase(GamePhase::HERO_SELECT);
        phaseTimer = 10.f;
        broadcast({{"type","phase_change"},{"phase","HERO_SELECT"}});
    }

    void enterRecruit() {
        gameState->setPhase(GamePhase::RECRUIT);
        phaseTimer = TURN_DURATION;
        inGrace = false;
        broadcast({{"type","phase_change"},{"phase","RECRUIT"}});
    }

    void enterCombat() {
        gameState->setPhase(GamePhase::COMBAT_CALC);
        runCombat();
    }

    void runCombat() {
        std::vector<std::shared_ptr<Player>> alive;
        for (auto& p : gameState->getAllPlayers())
            if (!p->zombie())
                alive.push_back(p);

        if (alive.size() <= 1) {
            gameState->setPhase(GamePhase::GAME_OVER);
            broadcast({
                {"type","game_over"},
                {"winner", alive.empty() ? "none" : alive[0]->getName()}
            });
            return;
        }

        combatSeed =
            std::hash<std::string>{}(gameState->getGameId()) ^
            std::hash<int>{}(combatRound++);

        combatRng.seed(combatSeed);

        json log = json::array();
        for (size_t i = 0; i + 1 < alive.size(); i += 2) {
            int dmg = combatRng() % 10 + 1;
            log.push_back({
                {"p1", alive[i]->getName()},
                {"p2", alive[i+1]->getName()},
                {"damage", dmg}
            });
        }

        broadcast({{"type","combat_log"},{"seed",combatSeed},{"log",log}});

        gameState->setPhase(GamePhase::LOG_REPLAY);
        phaseTimer = 5.f;
    }

    void handleAction(const json& action) {
        const std::string type = action.value("action","");
        const std::string token = action.value("token","");

        auto player = gameState->getPlayer(token);
        if (!player) return;

        if (action.value("version",-1) != player->getVersion()) {
            sendToPlayer(token,{
                {"type","error"},
                {"message","StateMismatch"}
            });
            return;
        }

        if (type == "END_TURN" &&
            gameState->getPhase() == GamePhase::RECRUIT) {
            phaseTimer = 0;
        }
    }

    void broadcast(const json& msg) {
        std::vector<std::shared_ptr<Session>> targets;
        {
            std::lock_guard<std::mutex> lock(sessionsMutex);
            for (auto& [_, w] : sessions)
                if (auto s = w.lock())
                    targets.push_back(s);
        }
        for (auto& s : targets)
            s->send(msg);
    }

    void sendToPlayer(const std::string& token, const json& msg) {
        std::shared_ptr<Session> s;
        {
            std::lock_guard<std::mutex> lock(sessionsMutex);
            auto it = sessions.find(token);
            if (it == sessions.end()) return;
            s = it->second.lock();
        }
        if (s) s->send(msg);
    }
};



    // ==================== Session Class ====================


Session::Session(tcp::socket socket, GameServer* srv)
    : ws(std::move(socket)), server(srv) {}

Session::~Session() {
    if (!token.empty()) {
        server->removeSession(token);
    }
}

void Session::run() {
    ws.async_accept(
        [self = shared_from_this()](boost::system::error_code ec) {
            if (!ec) {
                self->onAccept();
            }
        }
    );
}

void Session::send(const json& msg) {
    boost::system::error_code ec;
    ws.write(net::buffer(msg.dump()), ec);
}

void Session::onAccept() {
    token = UUIDGenerator::generate();
    server->addSession(token, shared_from_this());
    doRead();
}

void Session::doRead() {
    auto buffer = std::make_shared<beast::flat_buffer>();

    ws.async_read(
        *buffer,
        [self = shared_from_this(), buffer]
        (boost::system::error_code ec, std::size_t) {

            if (!ec) {
                self->onRead(beast::buffers_to_string(buffer->data()));
                self->doRead();
                return;
            }

            if (ec == websocket::error::closed) {
                return;
            }

            std::cerr << "❌ WebSocket error: " << ec.message() << std::endl;
        }
    );
}

void Session::onRead(const std::string& msg) {
    try {
        json data = json::parse(msg);


        data["token"] = token;

        server->enqueueAction(data);
    }
    catch (...) {
        send({
            {"type", "error"},
            {"message", "Invalid JSON"}
        });
    }
}


// ==================== Main Function ====================
int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "        🎮 MAW GAME SERVER C++         " << std::endl;
    std::cout << "========================================" << std::endl;
    
    try {
        GameServer server;
        server.run(PORT);
        

        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "💥 Fatal error: " << e.what() << std::endl;
        return 1;
    }
}